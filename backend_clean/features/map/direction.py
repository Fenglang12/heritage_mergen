"""高德路线规划服务，供 HTTP 接口与 Agent 工具复用。"""

import logging

import requests

from core.config import Config

logger = logging.getLogger(__name__)


def _parse_polyline(steps_list):
    pts = []
    for step in steps_list:
        poly = step.get('polyline', '')
        if not poly:
            continue
        for pt in poly.split(';'):
            parts = pt.split(',')
            if len(parts) == 2:
                try:
                    pts.append([float(parts[0]), float(parts[1])])
                except ValueError:
                    pass
    return pts


def _extract_steps(steps_list):
    return [
        {
            'instruction':   s.get('instruction', ''),
            'road_name':     s.get('road_name', ''),
            'step_distance': s.get('step_distance', ''),
        }
        for s in steps_list
    ]


def plan_direction(origin_lng, origin_lat, dest_lng, dest_lat, mode='driving', citycode='010'):
    """
    规划起点到终点的路线。
    返回 dict：status, distance, duration, cost, steps, polyline, msg（失败时）
    """
    if not all([origin_lng, origin_lat, dest_lng, dest_lat]):
        return {'status': 'error', 'msg': '缺少起终点坐标'}

    origin = f'{float(origin_lng):.6f},{float(origin_lat):.6f}'
    destination = f'{float(dest_lng):.6f},{float(dest_lat):.6f}'
    key = Config.AMAP_API_KEY
    mode = (mode or 'driving').lower()

    try:
        if mode == 'driving':
            res = requests.get(
                'https://restapi.amap.com/v5/direction/driving',
                params={
                    'key': key, 'origin': origin, 'destination': destination,
                    'show_fields': 'cost,polyline', 'output': 'json',
                },
                timeout=8,
            ).json()
            if res.get('status') != '1' or not res.get('route', {}).get('paths'):
                return {'status': 'error', 'msg': res.get('info', '驾车规划失败')}
            path = res['route']['paths'][0]
            return {
                'status': 'success',
                'distance': int(path.get('distance', 0)),
                'duration': int(path.get('cost', {}).get('duration', 0)),
                'cost': f"打车约¥{res['route']['taxi_cost']}" if res['route'].get('taxi_cost') else None,
                'steps': _extract_steps(path.get('steps', [])),
                'polyline': _parse_polyline(path.get('steps', [])),
            }

        if mode == 'cycling':
            res = requests.get(
                'https://restapi.amap.com/v5/direction/bicycling',
                params={
                    'key': key, 'origin': origin, 'destination': destination,
                    'show_fields': 'cost,polyline', 'output': 'json',
                },
                timeout=8,
            ).json()
            if res.get('status') != '1' or not res.get('route', {}).get('paths'):
                return {'status': 'error', 'msg': res.get('info', '骑行规划失败')}
            path = res['route']['paths'][0]
            return {
                'status': 'success',
                'distance': int(path.get('distance', 0)),
                'duration': int(path.get('cost', {}).get('duration', 0)),
                'cost': None,
                'steps': _extract_steps(path.get('steps', [])),
                'polyline': _parse_polyline(path.get('steps', [])),
            }

        if mode == 'walking':
            res = requests.get(
                'https://restapi.amap.com/v5/direction/walking',
                params={
                    'key': key, 'origin': origin, 'destination': destination,
                    'show_fields': 'cost,polyline', 'output': 'json',
                },
                timeout=8,
            ).json()
            if res.get('status') != '1' or not res.get('route', {}).get('paths'):
                return {'status': 'error', 'msg': res.get('info', '步行规划失败')}
            path = res['route']['paths'][0]
            return {
                'status': 'success',
                'distance': int(path.get('distance', 0)),
                'duration': int(path.get('cost', {}).get('duration', 0)),
                'cost': None,
                'steps': _extract_steps(path.get('steps', [])),
                'polyline': _parse_polyline(path.get('steps', [])),
            }

        if mode == 'transit':
            res = requests.get(
                'https://restapi.amap.com/v5/direction/transit/integrated',
                params={
                    'key': key, 'origin': origin, 'destination': destination,
                    'city1': citycode, 'city2': citycode,
                    'show_fields': 'cost', 'output': 'json',
                },
                timeout=8,
            ).json()
            if res.get('status') != '1' or not res.get('route', {}).get('transits'):
                return {'status': 'error', 'msg': '该区域暂无公交方案，建议切换其他出行方式'}
            transit = res['route']['transits'][0]
            steps = []
            for seg in (transit.get('segments') or []):
                walking = seg.get('walking') or {}
                for s in (walking.get('steps') or []):
                    steps.append({
                        'instruction': '步行：' + s.get('instruction', ''),
                        'road_name': s.get('road_name', ''),
                        'step_distance': s.get('step_distance', ''),
                    })
                bus = seg.get('bus') or {}
                for bl in (bus.get('buslines') or [])[:1]:
                    dep = (bl.get('departure_stop') or {}).get('name', '')
                    arr = (bl.get('arrival_stop') or {}).get('name', '')
                    steps.append({
                        'instruction': f"乘坐 {bl.get('name', '')}（{dep} → {arr}）",
                        'road_name': '',
                        'step_distance': str(bl.get('distance', '')),
                    })
            return {
                'status': 'success',
                'distance': int(transit.get('distance', 0)),
                'duration': int((transit.get('cost') or {}).get('duration', 0)),
                'cost': (
                    f"票价约¥{transit['cost']['transit_fee']}"
                    if (transit.get('cost') or {}).get('transit_fee') else None
                ),
                'steps': steps,
                'polyline': [],
            }

        return {'status': 'error', 'msg': f'不支持的出行方式: {mode}'}

    except Exception as exc:
        logger.error('路线规划失败 mode=%s: %s', mode, exc)
        return {'status': 'error', 'msg': '路线规划服务异常，请稍后重试'}
