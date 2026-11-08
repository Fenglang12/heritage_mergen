"""用户焕新作品持久化，供研学报告「数字创作集」使用。"""

import base64
import io
import logging
import re

from PIL import Image

from core.exts import db
from core.models import UserArtwork

logger = logging.getLogger(__name__)

MAX_ARTWORKS_PER_USER = 12
# 入库前压缩目标：宽度不超过 768、JPEG，避免单行过大（仍依赖 LONGTEXT）
_DB_PREVIEW_MAX_SIDE = 768
_DB_JPEG_QUALITY = 82


def ensure_user_artworks_schema():
    """已有表若为 TEXT，升级为 LONGTEXT（create_all 不会改已有列）。"""
    from sqlalchemy import inspect, text

    try:
        insp = inspect(db.engine)
        if 'user_artworks' not in insp.get_table_names():
            return
        cols = {c['name']: c for c in insp.get_columns('user_artworks')}
        col = cols.get('image_data')
        if not col:
            return
        type_str = str(col.get('type', '')).upper()
        if 'LONGTEXT' in type_str or 'MEDIUMTEXT' in type_str:
            return
        db.session.execute(
            text(
                'ALTER TABLE user_artworks '
                'MODIFY COLUMN image_data LONGTEXT NOT NULL, '
                'MODIFY COLUMN analysis LONGTEXT NULL'
            )
        )
        db.session.commit()
        logger.info('user_artworks.image_data 已升级为 LONGTEXT')
    except Exception as exc:
        db.session.rollback()
        logger.warning('user_artworks 表结构升级跳过: %s', exc)


def _compact_image_for_db(image_url: str) -> str:
    """将 data URL 压缩为较小 JPEG，便于入库与报告展示。"""
    raw = str(image_url or '').strip()
    if not raw.startswith('data:image'):
        return raw[:500_000] if len(raw) <= 500_000 else raw[:500_000]

    match = re.match(r'^data:image/[^;]+;base64,(.+)$', raw, re.DOTALL)
    if not match:
        return raw
    try:
        binary = base64.b64decode(match.group(1))
        img = Image.open(io.BytesIO(binary))
        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')
        img.thumbnail((_DB_PREVIEW_MAX_SIDE, _DB_PREVIEW_MAX_SIDE))
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=_DB_JPEG_QUALITY, optimize=True)
        encoded = base64.b64encode(buf.getvalue()).decode('ascii')
        return f'data:image/jpeg;base64,{encoded}'
    except Exception as exc:
        logger.warning('焕新图入库压缩失败，使用截断原图: %s', exc)
        return raw if len(raw) <= 500_000 else raw[:500_000]


def save_user_artwork(user_id: int, prompt: str, image_url: str,
                      analysis: str = '', source: str = 'revive') -> UserArtwork | None:
    """保存焕新作品；压缩图片并清理超出保留上限的旧作品。"""
    if not user_id or not image_url:
        return None
    try:
        img = _compact_image_for_db(image_url)
        row = UserArtwork(
            user_id=user_id,
            prompt=(prompt or '')[:500],
            image_data=img,
            analysis=(analysis or '')[:8000],
            source=source[:20],
        )
        db.session.add(row)
        db.session.flush()

        old = (
            UserArtwork.query.filter_by(user_id=user_id)
            .order_by(UserArtwork.id.desc())
            .offset(MAX_ARTWORKS_PER_USER)
            .all()
        )
        for o in old:
            db.session.delete(o)
        db.session.commit()
        return row
    except Exception as exc:
        db.session.rollback()
        logger.exception('焕新作品入库失败 user_id=%s: %s', user_id, exc)
        return None


def list_user_artworks(user_id: int, limit: int = 8) -> list:
    """按时间倒序返回用户最近的焕新作品。"""
    rows = (
        UserArtwork.query.filter_by(user_id=user_id)
        .order_by(UserArtwork.created_at.desc())
        .limit(limit)
        .all()
    )
    return [r.to_dict() for r in rows]
