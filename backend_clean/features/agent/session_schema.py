"""确保 chat_sessions.memory_json 列存在（兼容已有库）。"""

import logging

from sqlalchemy import inspect, text

from core.exts import db

logger = logging.getLogger(__name__)


def ensure_chat_session_memory_schema():
    try:
        insp = inspect(db.engine)
        if 'chat_sessions' not in insp.get_table_names():
            return
        cols = {c['name'] for c in insp.get_columns('chat_sessions')}
        if 'memory_json' in cols:
            return
        db.session.execute(text(
            'ALTER TABLE chat_sessions ADD COLUMN memory_json TEXT NULL'
        ))
        db.session.commit()
        logger.info('已为 chat_sessions 添加 memory_json 列')
    except Exception as exc:
        logger.warning('ensure_chat_session_memory_schema: %s', exc)
        try:
            db.session.rollback()
        except Exception:
            pass
