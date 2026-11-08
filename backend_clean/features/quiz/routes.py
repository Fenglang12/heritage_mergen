"""闯关答题与管理员热力图 API。"""

import json
import logging
import time

import pymysql
from flask import Blueprint, Response, jsonify, request, stream_with_context

from core.auth_utils import admin_required, auth_required, get_current_user_id
from core.config import Config
from core.exts import db
from core.models import Checkin, QuizScore
from features.quiz.service import generate_quiz_questions

logger = logging.getLogger(__name__)

quiz_bp = Blueprint('quiz', __name__, url_prefix='/api')


def _get_db_conn():
    return pymysql.connect(
        host=Config.DB_HOST, user=Config.DB_USER,
        password=Config.DB_PASS, database=Config.DB_NAME,
        charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
    )


# ================================================================
# 1. 闯关答题模块
# ================================================================

@quiz_bp.route('/quiz/generate', methods=['GET'])
@auth_required
def generate_quiz():
    """一次性返回 5 道 AI 生成选择题。"""
    questions, err = generate_quiz_questions()
    if err:
        return jsonify({'status': 'error', 'msg': err}), 500
    return jsonify({'status': 'success', 'questions': questions})


@quiz_bp.route('/quiz/generate/stream', methods=['GET'])
@auth_required
def generate_quiz_stream():
    """SSE 假流式：LLM 一次生成后逐题推送，改善等待体验。"""
    def gen():
        questions, err = generate_quiz_questions()
        if err:
            yield f"data: {json.dumps({'type': 'error', 'msg': err}, ensure_ascii=False)}\n\n"
            return
        total = len(questions)
        for idx, q in enumerate(questions):
            yield f"data: {json.dumps({'type': 'question', 'index': idx, 'total': total, 'data': q}, ensure_ascii=False)}\n\n"
            time.sleep(0.35)
        yield f"data: {json.dumps({'type': 'done', 'total': total}, ensure_ascii=False)}\n\n"

    return Response(
        stream_with_context(gen()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


@quiz_bp.route('/quiz/submit', methods=['POST'])
@auth_required
def submit_quiz():
    """
    提交答题结果，写入 quiz_scores 表。
    请求体：{ answers: {"1": "A", "2": "C", ...}, questions: [...], time_used: 45 }
    返回：{ status, score, correct, total, rank }
    """
    uid  = get_current_user_id()
    data = request.get_json(silent=True) or {}

    user_answers = data.get('answers', {})      # {"1": "A", ...}
    questions    = data.get('questions', [])     # 原始题目（含 answer 字段）
    time_used    = int(data.get('time_used', 0))

    if not questions:
        return jsonify({'status': 'error', 'msg': '缺少题目数据'}), 400

    correct = 0
    total   = len(questions)
    for q in questions:
        qid    = str(q.get('id', ''))
        expect = (q.get('answer') or '').strip().upper()
        got    = (user_answers.get(qid) or '').strip().upper()
        if got == expect:
            correct += 1

    # 分数算法：
    #   基础分：每题 20 分，5 题全对才能满分（错题无法靠时间补回）
    #   时间加成：180 秒内完成才有加成，每快 30 秒 +1 分
    #             上限为答对题数 * 2 分（全对最多加 10 分）
    #   效果：错 1 题基础分最高 80，加成最多 8 分 → 最高 88，永远低于全对的 90+
    base_score = correct * 20
    time_bonus = min(
        correct * 2,                        # 上限：答对几题最多加几×2分
        max(0, (180 - time_used)) // 30     # 180秒内每快30秒+1分，超时则0分
    )
    score = min(100, base_score + time_bonus)

    record = QuizScore(
        user_id=uid, score=score, total=total,
        correct=correct, time_used=time_used
    )
    db.session.add(record)
    db.session.commit()

    # 本用户在排行榜中的名次（按最高分）
    rank_query = db.session.execute(
        db.text("""
            SELECT COUNT(*) + 1 AS user_rank FROM (
                SELECT user_id, MAX(score) AS best
                FROM quiz_scores GROUP BY user_id
            ) sub WHERE sub.best > (
                SELECT MAX(score) FROM quiz_scores WHERE user_id = :uid
            )
        """),
        {'uid': uid}
    ).fetchone()
    rank = rank_query[0] if rank_query else 1

    return jsonify({
        'status':  'success',
        'score':   score,
        'correct': correct,
        'total':   total,
        'rank':    rank,
    })


@quiz_bp.route('/quiz/leaderboard', methods=['GET'])
@auth_required
def quiz_leaderboard():
    """
    排行榜：每位用户取最高分，返回前 20 名。
    """
    rows = db.session.execute(db.text("""
        SELECT u.username, MAX(qs.score) AS best_score,
               MAX(qs.correct) AS best_correct,
               MIN(qs.time_used) AS best_time,
               COUNT(qs.id) AS play_count
        FROM quiz_scores qs
        JOIN users u ON u.id = qs.user_id
        GROUP BY qs.user_id, u.username
        ORDER BY best_score DESC, best_correct DESC, best_time ASC
        LIMIT 20
    """)).fetchall()

    board = [
        {
            'rank':         idx + 1,
            'username':     r[0],
            'best_score':   r[1],
            'best_correct': r[2],
            'best_time':    r[3],
            'play_count':   r[4],
        }
        for idx, r in enumerate(rows)
    ]

    # 当前用户的名次
    uid = get_current_user_id()
    my_rank_row = db.session.execute(db.text("""
        SELECT COUNT(*) + 1 FROM (
            SELECT user_id, MAX(score) AS best FROM quiz_scores GROUP BY user_id
        ) sub
        WHERE sub.best > COALESCE(
            (SELECT MAX(score) FROM quiz_scores WHERE user_id = :uid), -1
        )
    """), {'uid': uid}).fetchone()
    my_rank = my_rank_row[0] if my_rank_row else None

    my_best_row = db.session.execute(db.text(
        "SELECT MAX(score), MAX(correct) FROM quiz_scores WHERE user_id = :uid"
    ), {'uid': uid}).fetchone()
    my_best = {'score': my_best_row[0], 'correct': my_best_row[1]} if my_best_row else {}

    return jsonify({
        'status':    'success',
        'board':     board,
        'my_rank':   my_rank,
        'my_best':   my_best,
    })


# ================================================================
# 2. 管理员热力图数据
# ================================================================

@quiz_bp.route('/admin/heatmap/heritage', methods=['GET'])
@admin_required
def heatmap_heritage():
    """
    非遗项目热力图：从 graph_nodes 筛选 label 为非遗相关的节点，
    返回带经纬度的坐标点列表。
    """
    HERITAGE_LABELS = {'非遗项目', '项目', '传承人', '技艺', '保护单位', '非遗'}

    conn = _get_db_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, label, properties FROM graph_nodes"
            )
            nodes = cursor.fetchall()
    finally:
        conn.close()

    points = []
    for n in nodes:
        # 筛选非遗标签
        if n['label'] not in HERITAGE_LABELS:
            continue

        props = n.get('properties') or {}
        if isinstance(props, str):
            try:
                props = json.loads(props)
            except Exception:
                props = {}

        lng = props.get('longitude') or props.get('lng') or props.get('经度')
        lat = props.get('latitude')  or props.get('lat') or props.get('纬度')
        region = props.get('region') or props.get('地区') or props.get('location') or ''

        # 如果没坐标，尝试按地区给一个模糊坐标（主要城市）
        if not (lng and lat) and region:
            region_coords = _fuzzy_region_coord(region)
            if region_coords:
                lng, lat = region_coords

        if lng and lat:
            try:
                points.append({
                    'lng':    float(lng),
                    'lat':    float(lat),
                    'name':   n['id'],
                    'label':  n['label'],
                    'region': region,
                    'weight': 1,
                })
            except (ValueError, TypeError):
                pass

    return jsonify({'status': 'success', 'points': points, 'total': len(points)})


@quiz_bp.route('/admin/heatmap/checkin', methods=['GET'])
@admin_required
def heatmap_checkin():
    """
    用户打卡热力图：从 checkins 表取已审核通过的打卡记录，返回坐标列表。
    """
    checkins = Checkin.query.filter_by(status=1).all()

    points = []
    for c in checkins:
        if c.longitude and c.latitude:
            points.append({
                'lng':    float(c.longitude),
                'lat':    float(c.latitude),
                'name':   c.site_name,
                'weight': 1,
            })

    return jsonify({'status': 'success', 'points': points, 'total': len(points)})


def _fuzzy_region_coord(region: str):
    """按地区关键词返回模糊坐标，用于没有精确经纬度的节点"""
    CITY_COORDS = {
        '北京': (116.4074, 39.9042),
        '上海': (121.4737, 31.2304),
        '广州': (113.2644, 23.1291),
        '成都': (104.0668, 30.5728),
        '西安': (108.9398, 34.3416),
        '苏州': (120.6195, 31.2990),
        '杭州': (120.1536, 30.2876),
        '南京': (118.7969, 32.0603),
        '武汉': (114.3054, 30.5931),
        '重庆': (106.5516, 29.5630),
        '昆明': (102.8329, 24.8801),
        '贵阳': (106.6302, 26.6477),
        '西藏': (91.1145, 29.6445),
        '拉萨': (91.1145, 29.6445),
        '新疆': (87.6168, 43.8256),
        '乌鲁木齐': (87.6168, 43.8256),
        '内蒙古': (111.7519, 40.8415),
        '呼和浩特': (111.7519, 40.8415),
        '哈尔滨': (126.5353, 45.8038),
        '沈阳': (123.4315, 41.8057),
        '长春': (125.3245, 43.8868),
        '济南': (117.0009, 36.6758),
        '郑州': (113.6254, 34.7466),
        '长沙': (112.9388, 28.2278),
        '南昌': (115.8580, 28.6820),
        '福州': (119.2965, 26.0745),
        '厦门': (118.0894, 24.4798),
        '南宁': (108.3669, 22.8170),
        '海口': (110.3312, 20.0320),
        '兰州': (103.7922, 36.0561),
        '银川': (106.2782, 38.4663),
        '西宁': (101.7782, 36.6171),
    }
    for city, coords in CITY_COORDS.items():
        if city in region:
            # 加小随机偏移，避免所有节点重叠
            import random
            offset_lng = random.uniform(-0.5, 0.5)
            offset_lat = random.uniform(-0.3, 0.3)
            return (coords[0] + offset_lng, coords[1] + offset_lat)
    return None
