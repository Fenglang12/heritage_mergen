"""跨 Blueprint 复用的 Session 鉴权工具。"""

from functools import wraps

from flask import jsonify, session

from core.models import User


def get_current_user_id():
    """从 Session Cookie 读取已登录用户 ID，未登录返回 None。"""
    return session.get('user_id')


def get_current_user():
    """返回当前用户 ORM 对象，未登录或不存在时返回 None。"""
    uid = get_current_user_id()
    return User.query.get(uid) if uid else None


def auth_required(f):
    """要求登录；封号用户返回 403。"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        uid = get_current_user_id()
        if not uid:
            return jsonify({'status': 'error', 'msg': '非法访问，请先登录'}), 401
        user = User.query.get(uid)
        if user and user.is_banned:
            reason = user.banned_reason or '违反社区规范'
            return jsonify({'status': 'error', 'msg': f'账号已被封禁：{reason}'}), 403
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    """要求管理员角色（role == 1）。"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        uid = get_current_user_id()
        if not uid:
            return jsonify({'status': 'error', 'msg': '请先登录'}), 401
        user = User.query.get(uid)
        if not user or user.role != 1:
            return jsonify({'status': 'error', 'msg': '权限不足'}), 403
        return f(*args, **kwargs)
    return wrapper
