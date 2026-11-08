"""Flask 应用入口：初始化数据库、注册蓝图、创建默认管理员。"""

import os

os.environ.setdefault('HF_ENDPOINT', 'https://modelscope.cn')

from flask import Flask
from flask_cors import CORS

from core.config import Config
from core.exts import db
# 模型导入是 db.create_all() 注册表结构的副作用依赖，勿删除
from core.models import (
    User, ChatSession, ChatHistory, Feedback, Checkin,
    CheckinComment, QuizScore, StudyReport, UserArtwork,
)
from api.routes import api_bp
from features.community.routes import community_bp
from features.quiz.routes import quiz_bp
from features.report.routes import report_bp


def create_app():
    """创建并配置 Flask 应用：注册蓝图、初始化数据库与默认管理员。"""
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(
        app,
        supports_credentials=True,
        origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
        allow_headers=['Content-Type', 'X-Client-Public-IP'],
    )

    db.init_app(app)

    app.register_blueprint(api_bp)
    app.register_blueprint(community_bp)
    app.register_blueprint(quiz_bp)
    app.register_blueprint(report_bp)

    with app.app_context():
        db.create_all()
        from features.revive.artwork import ensure_user_artworks_schema
        from features.report.service import ensure_study_reports_schema

        ensure_user_artworks_schema()
        ensure_study_reports_schema()

        from werkzeug.security import generate_password_hash
        admin = User.query.filter_by(username='admin').first()
        correct_hash = generate_password_hash('admin123', method='pbkdf2:sha256')

        if not admin:
            admin = User(username='admin', password_hash=correct_hash, role=1)
            db.session.add(admin)
            db.session.commit()
        elif admin.password_hash == 'pbkdf2:sha256:260000$placeholder_change_me' \
             or not admin.password_hash.startswith('pbkdf2:sha256:260000$') or len(admin.password_hash) < 50:
            admin.password_hash = correct_hash
            db.session.commit()

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
