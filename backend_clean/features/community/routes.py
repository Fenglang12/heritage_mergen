"""社区模块：用户反馈、打卡广场、管理员后台。"""

import logging
from datetime import datetime

from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash

from core.auth_utils import auth_required, admin_required, get_current_user
from core.exts import db
from core.models import User, Feedback, Checkin, CheckinComment

logger = logging.getLogger(__name__)

community_bp = Blueprint('community', __name__, url_prefix='/api')


# ================================================================
# A. 用户反馈模块
# ================================================================

@community_bp.route('/feedback/submit', methods=['POST'])
@auth_required
def submit_feedback():
    """用户提交反馈"""
    user = get_current_user()
    data  = request.get_json(silent=True) or {}

    title   = (data.get('title') or '').strip()
    content = (data.get('content') or '').strip()
    ftype   = data.get('type', 'general')

    if not title:
        return jsonify({'status': 'error', 'msg': '反馈标题不能为空'})
    if not content:
        return jsonify({'status': 'error', 'msg': '反馈内容不能为空'})
    if len(title) > 100:
        return jsonify({'status': 'error', 'msg': '标题不能超过100个字符'})
    if ftype not in ('general', 'bug', 'suggestion', 'other'):
        ftype = 'general'

    fb = Feedback(user_id=user.id, type=ftype, title=title, content=content)
    db.session.add(fb)
    db.session.commit()
    return jsonify({'status': 'success', 'msg': '反馈已提交，感谢您的建议！'})


@community_bp.route('/feedback/my', methods=['GET'])
@auth_required
def my_feedbacks():
    """用户查看自己的反馈列表"""
    user = get_current_user()
    page = request.args.get('page', 1, type=int)
    per  = 10
    q    = (Feedback.query
            .filter_by(user_id=user.id)
            .order_by(Feedback.created_at.desc())
            .paginate(page=page, per_page=per, error_out=False))
    return jsonify({
        'status': 'success',
        'data':   [f.to_dict() for f in q.items],
        'total':  q.total,
        'pages':  q.pages,
    })


# ================================================================
# B. 社区打卡模块（用户端）
# ================================================================

@community_bp.route('/checkin/submit', methods=['POST'])
@auth_required
def submit_checkin():
    """用户提交打卡（含照片，待审核）"""
    user = get_current_user()
    data = request.get_json(silent=True) or {}

    site_name   = (data.get('site_name') or '').strip()
    description = (data.get('description') or '').strip()
    photo_data  = data.get('photo_data', None)   # base64
    longitude   = data.get('longitude', None)
    latitude    = data.get('latitude', None)
    site_address = (data.get('site_address') or '').strip()

    if not site_name:
        return jsonify({'status': 'error', 'msg': '打卡地点名称不能为空'})
    if not photo_data:
        return jsonify({'status': 'error', 'msg': '请上传打卡照片'})

    checkin = Checkin(
        user_id      = user.id,
        site_name    = site_name,
        site_address = site_address or None,
        description  = description or None,
        photo_data   = photo_data,
        longitude    = longitude,
        latitude     = latitude,
        status       = 0,   # 待审核
    )
    db.session.add(checkin)
    db.session.commit()
    return jsonify({'status': 'success', 'msg': '打卡已提交，等待管理员审核！', 'id': checkin.id})


@community_bp.route('/checkin/list', methods=['GET'])
@auth_required
def list_checkins():
    """社区广场：展示已通过的打卡（可按地点筛选）"""
    user      = get_current_user()
    page      = request.args.get('page', 1, type=int)
    per       = 12
    site_filter = request.args.get('site', '').strip()

    q = Checkin.query.filter_by(status=1)   # 已通过
    if site_filter:
        q = q.filter(Checkin.site_name.like(f'%{site_filter}%'))

    result = q.order_by(Checkin.created_at.desc()).paginate(page=page, per_page=per, error_out=False)
    return jsonify({
        'status': 'success',
        'data':   [c.to_dict(current_user_id=user.id) for c in result.items],
        'total':  result.total,
        'pages':  result.pages,
    })


@community_bp.route('/checkin/map_pins', methods=['GET'])
@auth_required
def checkin_map_pins():
    """获取通过审核的打卡地图坐标点"""
    pins = (Checkin.query
            .filter_by(status=1)
            .filter(Checkin.longitude.isnot(None))
            .with_entities(Checkin.id, Checkin.site_name, Checkin.longitude,
                           Checkin.latitude, Checkin.site_address, Checkin.description)
            .all())
    data = [{'id': p.id, 'site_name': p.site_name,
              'lng': float(p.longitude), 'lat': float(p.latitude),
              'address': p.site_address,
              'description': p.description or ''} for p in pins]
    return jsonify({'status': 'success', 'pins': data})


@community_bp.route('/checkin/my', methods=['GET'])
@auth_required
def my_checkins():
    """用户查看自己的所有打卡（含待审核 / 已拒绝）"""
    user = get_current_user()
    page = request.args.get('page', 1, type=int)
    per  = 10
    q    = (Checkin.query
            .filter_by(user_id=user.id)
            .order_by(Checkin.created_at.desc())
            .paginate(page=page, per_page=per, error_out=False))
    return jsonify({
        'status': 'success',
        'data':   [c.to_dict(current_user_id=user.id) for c in q.items],
        'total':  q.total,
        'pages':  q.pages,
    })


# ================================================================
# C. 打卡评论模块
# ================================================================

@community_bp.route('/checkin/<int:cid>/comments', methods=['GET'])
@auth_required
def get_comments(cid):
    """获取打卡评论列表"""
    user    = get_current_user()
    checkin = Checkin.query.get_or_404(cid)
    if checkin.status != 1:
        return jsonify({'status': 'error', 'msg': '该打卡尚未通过审核'}), 403

    comments = (CheckinComment.query
                .filter_by(checkin_id=cid)
                .order_by(CheckinComment.created_at.asc())
                .all())
    is_admin = (user.role == 1)
    return jsonify({
        'status': 'success',
        'data':   [c.to_dict(current_user_id=user.id, is_admin=is_admin) for c in comments],
    })


@community_bp.route('/checkin/<int:cid>/comment', methods=['POST'])
@auth_required
def add_comment(cid):
    """添加评论"""
    user    = get_current_user()
    checkin = Checkin.query.get_or_404(cid)
    if checkin.status != 1:
        return jsonify({'status': 'error', 'msg': '该打卡尚未通过审核'}), 403

    data    = request.get_json(silent=True) or {}
    content = (data.get('content') or '').strip()
    if not content:
        return jsonify({'status': 'error', 'msg': '评论内容不能为空'})
    if len(content) > 500:
        return jsonify({'status': 'error', 'msg': '评论不能超过500字'})

    c = CheckinComment(checkin_id=cid, user_id=user.id, content=content)
    db.session.add(c)
    db.session.commit()
    return jsonify({'status': 'success', 'comment': c.to_dict(current_user_id=user.id)})


@community_bp.route('/comment/<int:comment_id>/delete', methods=['DELETE'])
@auth_required
def delete_comment(comment_id):
    """删除评论（评论作者 or 管理员）"""
    user    = get_current_user()
    comment = CheckinComment.query.get_or_404(comment_id)

    if user.role != 1 and comment.user_id != user.id:
        return jsonify({'status': 'error', 'msg': '无权删除此评论'}), 403

    db.session.delete(comment)
    db.session.commit()
    return jsonify({'status': 'success', 'msg': '评论已删除'})


# ================================================================
# D. 管理员功能模块
# ================================================================

# ── D1. 用户管理 ──────────────────────────────────────────────

@community_bp.route('/admin/users', methods=['GET'])
@admin_required
def admin_list_users():
    """管理员：获取用户列表"""
    page    = request.args.get('page', 1, type=int)
    per     = 20
    keyword = request.args.get('keyword', '').strip()

    q = User.query
    if keyword:
        q = q.filter(User.username.like(f'%{keyword}%'))

    result = q.order_by(User.created_at.desc()).paginate(page=page, per_page=per, error_out=False)
    return jsonify({
        'status': 'success',
        'data':   [u.to_dict() for u in result.items],
        'total':  result.total,
        'pages':  result.pages,
    })


@community_bp.route('/admin/user/<int:uid>/ban', methods=['POST'])
@admin_required
def admin_ban_user(uid):
    """管理员：封禁用户"""
    data   = request.get_json(silent=True) or {}
    reason = (data.get('reason') or '违反社区规范').strip()
    user   = User.query.get_or_404(uid)

    if user.role == 1:
        return jsonify({'status': 'error', 'msg': '无法封禁管理员账号'})

    user.is_banned     = 1
    user.banned_reason = reason
    db.session.commit()
    logger.info('管理员封禁用户 %s，原因：%s', user.username, reason)
    return jsonify({'status': 'success', 'msg': f'用户 {user.username} 已被封禁'})


@community_bp.route('/admin/user/<int:uid>/unban', methods=['POST'])
@admin_required
def admin_unban_user(uid):
    """管理员：解封用户"""
    user               = User.query.get_or_404(uid)
    user.is_banned     = 0
    user.banned_reason = None
    db.session.commit()
    return jsonify({'status': 'success', 'msg': f'用户 {user.username} 已解封'})


# ── D2. 反馈管理 ──────────────────────────────────────────────

@community_bp.route('/admin/feedbacks', methods=['GET'])
@admin_required
def admin_list_feedbacks():
    """管理员：获取所有反馈"""
    page   = request.args.get('page', 1, type=int)
    per    = 15
    status = request.args.get('status', None, type=int)

    q = Feedback.query
    if status is not None:
        q = q.filter_by(status=status)

    result = q.order_by(Feedback.created_at.desc()).paginate(page=page, per_page=per, error_out=False)
    return jsonify({
        'status': 'success',
        'data':   [f.to_dict() for f in result.items],
        'total':  result.total,
        'pages':  result.pages,
    })


@community_bp.route('/admin/feedback/<int:fid>/reply', methods=['POST'])
@admin_required
def admin_reply_feedback(fid):
    """管理员：回复 / 处理反馈"""
    fb     = Feedback.query.get_or_404(fid)
    data   = request.get_json(silent=True) or {}
    reply  = (data.get('reply') or '').strip()
    status = data.get('status', 1)   # 1=已处理 2=已忽略

    if reply:
        fb.admin_reply = reply
        fb.replied_at  = datetime.now()
    fb.status = status
    db.session.commit()
    return jsonify({'status': 'success', 'msg': '已处理'})


# ── D3. 打卡审核 ──────────────────────────────────────────────

@community_bp.route('/admin/checkins', methods=['GET'])
@admin_required
def admin_list_checkins():
    """管理员：获取待审核 / 全部打卡"""
    page   = request.args.get('page', 1, type=int)
    per    = 15
    status = request.args.get('status', 0, type=int)   # 默认查待审核

    result = (Checkin.query
              .filter_by(status=status)
              .order_by(Checkin.created_at.asc())
              .paginate(page=page, per_page=per, error_out=False))
    return jsonify({
        'status': 'success',
        'data':   [c.to_dict() for c in result.items],
        'total':  result.total,
        'pages':  result.pages,
    })


@community_bp.route('/admin/checkin/<int:cid>/review', methods=['POST'])
@admin_required
def admin_review_checkin(cid):
    """管理员：审核打卡（通过 or 拒绝）"""
    admin   = get_current_user()
    checkin = Checkin.query.get_or_404(cid)
    data    = request.get_json(silent=True) or {}
    action  = data.get('action')   # 'approve' | 'reject'
    reason  = (data.get('reason') or '').strip()

    if action == 'approve':
        checkin.status      = 1
        checkin.reject_reason = None
    elif action == 'reject':
        checkin.status        = 2
        checkin.reject_reason = reason or '内容不符合社区规范'
    else:
        return jsonify({'status': 'error', 'msg': '无效的操作'}), 400

    checkin.reviewed_by = admin.id
    checkin.reviewed_at = datetime.now()
    db.session.commit()
    verb = '通过' if action == 'approve' else '拒绝'
    return jsonify({'status': 'success', 'msg': f'打卡已{verb}'})


@community_bp.route('/admin/checkin/<int:cid>/delete', methods=['DELETE'])
@admin_required
def admin_delete_checkin(cid):
    """管理员：强制删除打卡"""
    checkin = Checkin.query.get_or_404(cid)
    db.session.delete(checkin)
    db.session.commit()
    return jsonify({'status': 'success', 'msg': '打卡已删除'})


# ── D4. 管理员统计面板 ─────────────────────────────────────────

@community_bp.route('/admin/stats', methods=['GET'])
@admin_required
def admin_stats():
    """管理员：概览统计"""
    total_users    = User.query.filter_by(role=0).count()
    banned_users   = User.query.filter_by(is_banned=1).count()
    pending_ck     = Checkin.query.filter_by(status=0).count()
    approved_ck    = Checkin.query.filter_by(status=1).count()
    pending_fb     = Feedback.query.filter_by(status=0).count()
    total_comments = CheckinComment.query.count()
    return jsonify({
        'status':         'success',
        'total_users':    total_users,
        'banned_users':   banned_users,
        'pending_checkins': pending_ck,
        'approved_checkins': approved_ck,
        'pending_feedbacks': pending_fb,
        'total_comments': total_comments,
    })
