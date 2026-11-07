"""研学报告 API。"""

import json
import logging

from flask import Blueprint, jsonify, Response, stream_with_context

from core.auth_utils import auth_required, get_current_user_id
from core.models import User
from features.report.service import (
    build_report_payload,
    get_cached_report,
    save_report,
)

logger = logging.getLogger(__name__)

report_bp = Blueprint('report', __name__, url_prefix='/api')


@report_bp.route('/report/latest', methods=['GET'])
@auth_required
def report_latest():
    """获取 24 小时内最近一份研学报告。"""
    uid = get_current_user_id()
    cached = get_cached_report(uid)
    if not cached:
        return jsonify({'status': 'empty', 'report': None})
    return jsonify({'status': 'success', 'report': cached})


@report_bp.route('/report/generate', methods=['POST'])
@auth_required
def report_generate():
    """生成研学报告并缓存。"""
    uid = get_current_user_id()
    user = User.query.get(uid)
    if not user:
        return jsonify({'status': 'error', 'msg': '用户不存在'}), 404

    result = build_report_payload(uid, user.username)
    if not result['ok']:
        return jsonify({'status': 'error', 'msg': result['msg']}), 400

    save_report(uid, result['data'])
    return jsonify({'status': 'success', 'report': result['data']})


@report_bp.route('/report/generate/stream', methods=['POST'])
@auth_required
def report_generate_stream():
    """SSE 流式返回报告各模块（生成后一次性切片推送）。"""
    uid = get_current_user_id()
    user = User.query.get(uid)

    def gen():
        if not user:
            yield f"data: {json.dumps({'type': 'error', 'text': '用户不存在'}, ensure_ascii=False)}\n\n"
            return
        result = build_report_payload(uid, user.username)
        if not result['ok']:
            yield f"data: {json.dumps({'type': 'error', 'text': result['msg']}, ensure_ascii=False)}\n\n"
            return
        report = result['data']
        sections = [
            ('overview', '学习概览', report.get('overview', '')),
            ('knowledge', '知识掌握', report.get('knowledge', '')),
            ('footprint', '探索足迹', report.get('footprint', '')),
            ('creations', '数字创作集', report.get('creations_summary', '')),
            ('recommendation', '学习建议', report.get('recommendation', '')),
        ]
        if report.get('artworks'):
            yield f"data: {json.dumps({'type': 'artworks', 'items': report['artworks']}, ensure_ascii=False)}\n\n"
        for key, title, content in sections:
            yield f"data: {json.dumps({'type': 'section', 'key': key, 'title': title, 'content': content}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'keywords', 'words': report.get('keywords', [])}, ensure_ascii=False)}\n\n"
        try:
            save_report(uid, report)
        except Exception as exc:
            logger.exception('研学报告入库失败 user_id=%s: %s', uid, exc)
            yield f"data: {json.dumps({'type': 'save_warning', 'text': '报告已生成但暂未能写入缓存，刷新后需重新生成。'}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'report': report}, ensure_ascii=False)}\n\n"

    return Response(
        stream_with_context(gen()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )
