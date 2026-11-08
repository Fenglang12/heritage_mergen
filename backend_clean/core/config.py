"""应用配置：统一从 backend_clean/.env 读取，不在代码中硬编码密钥。"""

import os
from pathlib import Path

from dotenv import load_dotenv

# 固定加载 backend_clean/.env（避免工作目录不是本目录时读不到配置）
_ENV_FILE = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(_ENV_FILE, override=True)


def _env(key: str, default: str = '') -> str:
    return (os.environ.get(key) or default).strip()


class Config:
    # ── 安全配置（必须在 .env 设置 SECRET_KEY）────────────────
    SECRET_KEY = _env('SECRET_KEY') or 'dev-only-set-SECRET_KEY-in-dotenv'

    # Session Cookie 安全设置（前后端分离时配合 SameSite=None）
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'   # 生产 HTTPS 环境改为 'None'
    SESSION_COOKIE_SECURE = False      # 生产 HTTPS 环境改为 True

    # ── MySQL（账号密码在 .env；库名/主机可有本地默认）────────
    DB_USER = _env('DB_USER', 'root')
    DB_PASS = _env('DB_PASS')  # 勿在仓库写死密码
    DB_HOST = _env('DB_HOST', 'localhost')
    DB_NAME = _env('DB_NAME', 'heritage_db')

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── 讯飞星火（全部来自 .env，无仓库内默认值）──────────────
    SPARK_APPID = _env('SPARK_APPID')
    SPARK_API_SECRET = _env('SPARK_API_SECRET')
    SPARK_API_KEY = _env('SPARK_API_KEY')
    SPARK_URL = 'wss://spark-api.xf-yun.com/v3.1/chat'
    SPARK_DOMAIN = 'generalv3'

    IMAGE_URL = 'wss://spark-api.cn-huabei-1.xf-yun.com/v2.1/image'
    TTS_URL = 'wss://tts-api.xfyun.cn/v2/tts'
    IAT_URL = 'wss://iat.xf-yun.com/v1'

    # ── 阿里云百炼 ────────────────────────────────────────────
    DASHSCOPE_API_KEY = _env('DASHSCOPE_API_KEY')
    DASHSCOPE_BASE_URL = _env(
        'DASHSCOPE_BASE_URL',
        'https://dashscope.aliyuncs.com/compatible-mode/v1',
    )
    VIDEO_MODEL = _env('VIDEO_MODEL', 'qwen-vl-plus')
    # 视频理解专用通道：可指向智谱等 OpenAI 兼容服务；留空则回落到百炼
    VIDEO_BASE_URL = _env('VIDEO_BASE_URL')
    VIDEO_API_KEY = _env('VIDEO_API_KEY')
    QWEN_INTRO_MODEL = _env('QWEN_INTRO_MODEL', 'qwen3-max')
    _marker_provider = _env('MARKER_INTRO_PROVIDER', 'spark').lower()
    if _marker_provider in ('qwen3', 'qwen-max', 'dashscope'):
        _marker_provider = 'qwen'
    MARKER_INTRO_PROVIDER = _marker_provider if _marker_provider in ('spark', 'qwen') else 'spark'
    try:
        SOURCE_TRACE_MAX_MARKERS = max(1, int(_env('SOURCE_TRACE_MAX_MARKERS', '10') or '10'))
    except ValueError:
        SOURCE_TRACE_MAX_MARKERS = 10

    # ── 智谱 AI ───────────────────────────────────────────────
    ZHIPU_API_KEY = _env('ZHIPU_API_KEY')
    ZHIPU_IMAGE_MODEL = _env('ZHIPU_IMAGE_MODEL', 'cogview-4-250304')
    ZHIPU_VISION_MODEL = _env('ZHIPU_VISION_MODEL', 'glm-4v')

    # 演示模式
    _demo_mode = _env('DEMO_MODE', 'false').lower()
    DEMO_MODE = _demo_mode in ('1', 'true', 'yes')
    try:
        DEMO_SIMULATE_DELAY_SEC = max(0.0, float(_env('DEMO_SIMULATE_DELAY_SEC', '3') or '3'))
    except ValueError:
        DEMO_SIMULATE_DELAY_SEC = 3.0

    # ── 高德地图（Key 只来自 .env）────────────────────────────
    AMAP_API_KEY = _env('AMAP_API_KEY')
    DEFAULT_MAP_CITY = _env('DEFAULT_MAP_CITY', '广州市') or '广州市'
