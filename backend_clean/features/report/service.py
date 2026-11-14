"""研学报告：聚合用户行为数据并由 LLM 生成结构化总结。"""

import json
import logging
from datetime import datetime, timedelta

from core.exts import db
from core.models import ChatHistory, ChatSession, Checkin, QuizScore, StudyReport, UserArtwork
from features.revive.artwork import list_user_artworks
from shared.utils import sync_llm_call

logger = logging.getLogger(__name__)

REPORT_CACHE_HOURS = 24


def ensure_study_reports_schema():
    """已有表 content_json 若为 TEXT，升级为 LONGTEXT。"""
    from sqlalchemy import inspect, text

    try:
        insp = inspect(db.engine)
        if 'study_reports' not in insp.get_table_names():
            return
        cols = {c['name']: c for c in insp.get_columns('study_reports')}
        col = cols.get('content_json')
        if not col:
            return
        type_str = str(col.get('type', '')).upper()
        if 'LONGTEXT' in type_str or 'MEDIUMTEXT' in type_str:
            return
        db.session.execute(
            text('ALTER TABLE study_reports MODIFY COLUMN content_json LONGTEXT NOT NULL')
        )
        db.session.commit()
        logger.info('study_reports.content_json 已升级为 LONGTEXT')
    except Exception as exc:
        db.session.rollback()
        logger.warning('study_reports 表结构升级跳过: %s', exc)


def slim_artwork_for_storage(item: dict) -> dict:
    """报告缓存不存 base64 图，展示时按 id 从 user_artworks 回填。"""
    return {
        'id': item.get('id'),
        'prompt': (item.get('prompt') or '')[:500],
        'analysis': (item.get('analysis') or '')[:2000],
        'source': item.get('source'),
        'created_at': item.get('created_at'),
    }


def strip_report_for_storage(report: dict) -> dict:
    """生成可入库的精简报告副本。"""
    slim = dict(report)
    slim['artworks'] = [slim_artwork_for_storage(a) for a in (report.get('artworks') or [])]
    return slim


def hydrate_report_artworks(report: dict) -> dict:
    """从作品表补全图片，供缓存报告展示。"""
    arts = report.get('artworks') or []
    if not arts:
        return report
    ids = [a['id'] for a in arts if a.get('id')]
    if not ids:
        return report
    rows = UserArtwork.query.filter(UserArtwork.id.in_(ids)).all()
    by_id = {r.id: r.to_dict() for r in rows}
    out = dict(report)
    out['artworks'] = [by_id.get(a.get('id'), a) for a in arts]
    return out


def _collect_user_data(user_id: int) -> dict:
    """汇总对话、答题、打卡等行为数据。"""
    sessions = ChatSession.query.filter_by(user_id=user_id).order_by(ChatSession.created_at.desc()).limit(10).all()
    chat_lines = []
    for sess in sessions:
        rows = (
            ChatHistory.query.filter_by(session_id=sess.id)
            .order_by(ChatHistory.id.desc())
            .limit(8)
            .all()
        )
        for row in reversed(rows):
            prefix = '用户' if row.role == 'user' else '向导'
            text = (row.content or '')[:120]
            if text and not text.startswith('[发送'):
                chat_lines.append(f'{prefix}：{text}')

    quiz_rows = (
        QuizScore.query.filter_by(user_id=user_id)
        .order_by(QuizScore.created_at.desc())
        .limit(5)
        .all()
    )
    quiz_stats = [
        {
            'score': r.score,
            'correct': r.correct,
            'total': r.total,
            'time_used': r.time_used,
            'date': r.created_at.strftime('%Y-%m-%d'),
        }
        for r in quiz_rows
    ]

    checkins = (
        Checkin.query.filter_by(user_id=user_id, status=1)
        .order_by(Checkin.created_at.desc())
        .limit(10)
        .all()
    )
    checkin_sites = [
        {'site': c.site_name, 'address': c.site_address or '', 'date': c.created_at.strftime('%Y-%m-%d')}
        for c in checkins
    ]

    artworks = list_user_artworks(user_id, limit=6)

    return {
        'chat_samples': chat_lines[-30:],
        'quiz_stats': quiz_stats,
        'checkin_sites': checkin_sites,
        'session_count': len(sessions),
        'artworks': artworks,
    }


def has_enough_data(data: dict) -> bool:
    """新用户数据过少时不生成报告。"""
    return bool(
        data.get('chat_samples')
        or data.get('quiz_stats')
        or data.get('checkin_sites')
        or data.get('artworks')
    )


def build_report_payload(user_id: int, username: str) -> dict:
    """调用 LLM 生成研学报告 JSON 结构。"""
    data = _collect_user_data(user_id)
    if not has_enough_data(data):
        return {
            'ok': False,
            'msg': '研学数据不足，请先完成对话、答题或打卡后再生成报告。',
            'data': None,
        }

    prompt = f"""你是非遗研学导师。根据以下用户学习行为，生成一份 JSON 对象（不要 Markdown），字段如下：
{{
  "overview": "学习概览，2-3句话",
  "knowledge": "知识掌握分析，含答题表现与薄弱点",
  "footprint": "探索足迹总结，提及打卡地点",
  "recommendation": "下一步学习建议，具体可执行",
  "keywords": ["词1","词2","词3","词4","词5"]
}}

用户名：{username}
对话摘录（最近）：
{chr(10).join(data['chat_samples'][:15]) or '（暂无）'}

答题记录：
{json.dumps(data['quiz_stats'], ensure_ascii=False) or '（暂无）'}

打卡足迹：
{json.dumps(data['checkin_sites'], ensure_ascii=False) or '（暂无）'}

数字焕新创作（{len(data.get('artworks') or [])} 件）：
{json.dumps([{'prompt': a.get('prompt'), 'date': a.get('created_at')} for a in (data.get('artworks') or [])], ensure_ascii=False) or '（暂无）'}
"""
    raw = sync_llm_call(prompt, temperature=0.3, max_tokens=2048) or ''
    try:
        cleaned = raw.strip()
        if '```' in cleaned:
            import re
            cleaned = re.sub(r'```(?:json)?', '', cleaned).strip('` \n')
        report = json.loads(cleaned)
        report['generated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M')
        report['stats'] = {
            'sessions': data['session_count'],
            'quiz_count': len(data['quiz_stats']),
            'checkin_count': len(data['checkin_sites']),
            'artwork_count': len(data.get('artworks') or []),
        }
        report['artworks'] = data.get('artworks') or []
        report['creations_summary'] = (
            f'共完成 {len(report["artworks"])} 件非遗数字焕新创作。'
            if report['artworks'] else '尚未生成数字焕新作品，可前往「非遗数字焕新」或对话中请 Agent 创作。'
        )
        return {'ok': True, 'msg': '', 'data': report}
    except Exception as exc:
        logger.error('报告 JSON 解析失败: %s', exc)
        return {
            'ok': True,
            'msg': '',
            'data': {
                'overview': f'{username}，你已开启非遗研学之旅。',
                'knowledge': f'已完成 {len(data["quiz_stats"])} 次闯关答题。',
                'footprint': f'已打卡 {len(data["checkin_sites"])} 处文化地标。',
                'recommendation': '可继续查看地图非遗地标，或向智能向导提问。',
                'keywords': ['非遗', '传承', '探索', '研学', '文化'],
                'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'stats': {
                    'sessions': data['session_count'],
                    'quiz_count': len(data['quiz_stats']),
                    'checkin_count': len(data['checkin_sites']),
                    'artwork_count': len(data.get('artworks') or []),
                },
                'artworks': data.get('artworks') or [],
                'creations_summary': (
                    f'共完成 {len(data.get("artworks") or [])} 件数字焕新创作。'
                    if data.get('artworks') else '暂无数字创作，推荐体验非遗焕新功能。'
                ),
            },
        }


def get_cached_report(user_id: int):
    """返回 24 小时内最近一份报告。"""
    since = datetime.now() - timedelta(hours=REPORT_CACHE_HOURS)
    row = (
        StudyReport.query.filter_by(user_id=user_id)
        .filter(StudyReport.created_at >= since)
        .order_by(StudyReport.created_at.desc())
        .first()
    )
    if not row:
        return None
    try:
        data = json.loads(row.content_json)
    except json.JSONDecodeError:
        return None
    return hydrate_report_artworks(data)


def save_report(user_id: int, payload: dict) -> StudyReport:
    """持久化研学报告；入库前剥离体积较大的创作集图片。"""
    stored = strip_report_for_storage(payload)
    row = StudyReport(
        user_id=user_id,
        content_json=json.dumps(stored, ensure_ascii=False),
    )
    db.session.add(row)
    db.session.commit()
    return row
