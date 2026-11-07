"""从业务库聚合用户画像，注入 Agent System Prompt。"""

from core.models import ChatHistory, ChatSession, Checkin, QuizScore


def build_user_profile(user_id: int) -> dict:
    """打卡地标、答题概况、近期对话关注点。"""
    if not user_id:
        return {}

    checkins = (
        Checkin.query.filter_by(user_id=user_id, status=1)
        .order_by(Checkin.id.desc())
        .limit(8)
        .all()
    )
    sites = [c.site_name for c in checkins if c.site_name]

    scores = (
        QuizScore.query.filter_by(user_id=user_id)
        .order_by(QuizScore.created_at.desc())
        .limit(5)
        .all()
    )
    quiz_weak = []
    if scores:
        avg_rate = sum((s.correct or 0) / max(s.total or 5, 1) for s in scores) / len(scores)
        if avg_rate < 0.6:
            quiz_weak.append('非遗综合知识（近期正确率偏低）')

    recent_topics = []
    sessions = (
        ChatSession.query.filter_by(user_id=user_id)
        .order_by(ChatSession.id.desc())
        .limit(3)
        .all()
    )
    for sess in sessions:
        rows = (
            ChatHistory.query.filter_by(session_id=sess.id, role='user')
            .order_by(ChatHistory.id.desc())
            .limit(2)
            .all()
        )
        for row in rows:
            text = (row.content or '').strip()
            if text and not text.startswith('[') and len(text) > 4:
                recent_topics.append(text[:80])

    recent_focus = recent_topics[0] if recent_topics else ''

    return {
        'checkin_sites': sites[:6],
        'quiz_weak': quiz_weak,
        'recent_topics': recent_topics[:3],
        'recent_focus': recent_focus,
    }


def format_user_profile_block(profile: dict) -> str:
    if not profile:
        return ''
    lines = ['【用户画像（请自然融入回答，勿生硬罗列）】']
    if profile.get('checkin_sites'):
        lines.append(f"- 打卡过的非遗地标：{', '.join(profile['checkin_sites'])}")
    if profile.get('quiz_weak'):
        lines.append(f"- 答题弱项：{', '.join(profile['quiz_weak'])}")
    if profile.get('recent_focus'):
        lines.append(f"- 最近关注：{profile['recent_focus']}")
    if len(lines) == 1:
        return ''
    return '\n'.join(lines)
