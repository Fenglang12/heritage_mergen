# models.py — 完整数据模型（含管理员、反馈、社区打卡、评论）
from datetime import datetime

from sqlalchemy.dialects.mysql import LONGTEXT

from core.exts import db


class User(db.Model):
    __tablename__ = 'users'
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role          = db.Column(db.Integer, default=0, nullable=False)   # 0=普通用户 1=管理员
    is_banned     = db.Column(db.Integer, default=0, nullable=False)   # 0=正常 1=封号
    banned_reason = db.Column(db.String(255), default=None)
    created_at    = db.Column(db.DateTime, default=datetime.now)

    # 关联
    sessions  = db.relationship('ChatSession',     backref='owner',    lazy=True, cascade='all, delete-orphan')
    feedbacks = db.relationship('Feedback',        backref='author',   lazy=True, cascade='all, delete-orphan')
    checkins  = db.relationship('Checkin',         backref='user',     lazy='dynamic', cascade='all, delete-orphan',
                                foreign_keys='Checkin.user_id')
    comments    = db.relationship('CheckinComment',  backref='commenter', lazy=True, cascade='all, delete-orphan')
    quiz_scores   = db.relationship('QuizScore',       backref='user',      lazy=True, cascade='all, delete-orphan')
    study_reports = db.relationship('StudyReport',     backref='user',      lazy=True, cascade='all, delete-orphan')
    artworks      = db.relationship('UserArtwork',     backref='user',      lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id':           self.id,
            'username':     self.username,
            'role':         self.role,
            'is_banned':    self.is_banned,
            'banned_reason': self.banned_reason,
            'created_at':   self.created_at.strftime('%Y-%m-%d %H:%M'),
        }


class ChatSession(db.Model):
    __tablename__ = 'chat_sessions'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title      = db.Column(db.String(100), default='新的对话')
    created_at = db.Column(db.DateTime, default=datetime.now)
    # 会话级 Agent 记忆（研学目标 / 站点 / 近期问句），JSON 文本
    memory_json = db.Column(db.Text, nullable=True)

    messages = db.relationship('ChatHistory', backref='session', lazy=True, cascade='all, delete-orphan')


class ChatHistory(db.Model):
    __tablename__ = 'chat_histories'
    id         = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_sessions.id'), nullable=False)
    role       = db.Column(db.String(20), nullable=False)
    content    = db.Column(db.Text, nullable=False)
    timestamp  = db.Column(db.DateTime, default=datetime.now)


class Feedback(db.Model):
    """用户反馈"""
    __tablename__ = 'feedbacks'
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    type        = db.Column(db.String(30), default='general')  # general|bug|suggestion|other
    title       = db.Column(db.String(100), nullable=False)
    content     = db.Column(db.Text, nullable=False)
    status      = db.Column(db.Integer, default=0)   # 0=待处理 1=已处理 2=已忽略
    admin_reply = db.Column(db.Text, default=None)
    replied_at  = db.Column(db.DateTime, default=None)
    created_at  = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id':          self.id,
            'user_id':     self.user_id,
            'username':    self.author.username if self.author else '已注销',
            'type':        self.type,
            'title':       self.title,
            'content':     self.content,
            'status':      self.status,
            'admin_reply': self.admin_reply,
            'replied_at':  self.replied_at.strftime('%Y-%m-%d %H:%M') if self.replied_at else None,
            'created_at':  self.created_at.strftime('%Y-%m-%d %H:%M'),
        }


class Checkin(db.Model):
    """非遗地点打卡"""
    __tablename__ = 'checkins'
    id            = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    site_name     = db.Column(db.String(200), nullable=False)
    site_address  = db.Column(db.String(300), default=None)
    longitude     = db.Column(db.Numeric(10, 6), default=None)
    latitude      = db.Column(db.Numeric(10, 6), default=None)
    description   = db.Column(db.Text, default=None)
    photo_url     = db.Column(db.String(500), default=None)
    photo_data    = db.Column(db.Text, default=None)          # base64 小图
    status        = db.Column(db.Integer, default=0)          # 0=待审核 1=已通过 2=已拒绝
    reject_reason = db.Column(db.String(255), default=None)
    reviewed_by   = db.Column(db.Integer, db.ForeignKey('users.id'), default=None)
    reviewed_at   = db.Column(db.DateTime, default=None)
    created_at    = db.Column(db.DateTime, default=datetime.now)

    comments      = db.relationship('CheckinComment', backref='checkin', lazy='dynamic',
                                    cascade='all, delete-orphan')

    def to_dict(self, current_user_id=None):
        return {
            'id':           self.id,
            'user_id':      self.user_id,
            'username':     self.user.username if self.user else '已注销',
            'site_name':    self.site_name,
            'site_address': self.site_address,
            'longitude':    float(self.longitude) if self.longitude else None,
            'latitude':     float(self.latitude)  if self.latitude  else None,
            'description':  self.description,
            'photo_data':   self.photo_data,
            'status':       self.status,
            'reject_reason': self.reject_reason,
            'created_at':   self.created_at.strftime('%Y-%m-%d %H:%M'),
            'comment_count': self.comments.count(),
            'is_own':       (current_user_id == self.user_id) if current_user_id else False,
        }


class QuizScore(db.Model):
    """AI闯关答题成绩"""
    __tablename__ = 'quiz_scores'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    score      = db.Column(db.Integer, default=0)          # 本局得分
    total      = db.Column(db.Integer, default=5)          # 题目总数
    correct    = db.Column(db.Integer, default=0)          # 答对数
    time_used  = db.Column(db.Integer, default=0)          # 用时秒数
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id':         self.id,
            'user_id':    self.user_id,
            'username':   self.user.username if self.user else '已注销',
            'score':      self.score,
            'total':      self.total,
            'correct':    self.correct,
            'time_used':  self.time_used,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M'),
        }


class UserArtwork(db.Model):
    """用户 AI 焕新/创作作品"""
    __tablename__ = 'user_artworks'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    prompt     = db.Column(db.String(500), default='')
    # 存 base64 data URL，须 LONGTEXT（TEXT 仅 ~64KB，生图易超长）
    image_data = db.Column(LONGTEXT, nullable=False)
    analysis   = db.Column(LONGTEXT, default=None)
    source     = db.Column(db.String(20), default='revive')
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'prompt': self.prompt,
            'image': self.image_data,
            'analysis': self.analysis or '',
            'source': self.source,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M'),
        }


class StudyReport(db.Model):
    """用户非遗研学报告（JSON 缓存）"""
    __tablename__ = 'study_reports'
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content_json = db.Column(LONGTEXT, nullable=False)
    created_at   = db.Column(db.DateTime, default=datetime.now)


class CheckinComment(db.Model):
    """打卡评论"""
    __tablename__ = 'checkin_comments'
    id         = db.Column(db.Integer, primary_key=True)
    checkin_id = db.Column(db.Integer, db.ForeignKey('checkins.id'), nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content    = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self, current_user_id=None, is_admin=False):
        return {
            'id':         self.id,
            'checkin_id': self.checkin_id,
            'user_id':    self.user_id,
            'username':   self.commenter.username if self.commenter else '已注销',
            'content':    self.content,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M'),
            'can_delete': is_admin or (current_user_id == self.user_id),
        }
