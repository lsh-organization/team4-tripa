import requests

from django.conf import settings


# ==============================================
# 카카오 경로 API 공통 호출
# ==============================================

def get_kakao_route(
    start_lat,
    start_lon,
    end_lat,
    end_lon,
    transport
):

    # ==========================================
    # 교통수단 값 통일
    # ==========================================

    transport = str(transport).strip().lower()

    transport_map = {
        'car': 'car',
        '자동차': 'car',
        '차': 'car',

        'walk': 'walk',
        '도보': 'walk',

        'public transport': 'public_transport',
        'public_transport': 'public_transport',
        'public': 'public_transport',
        '대중교통': 'public_transport',

        'bike': 'bike',
        '자전거': 'bike',
    }

    transport = transport_map.get(
        transport,
        transport
    )

    # ↓ 기존 코드 계속

    headers = {
        'Authorization':
            f'KakaoAK {settings.KAKAO_REST_API_KEY}'
    }

    # ==========================================
    # 자동차
    # ==========================================

    if transport == 'car':

        url = (
            'https://apis-navi.kakaomobility.com/'
            'v1/directions'
        )

        params = {
            'origin':
                f'{start_lon},{start_lat}',

            'destination':
                f'{end_lon},{end_lat}',

            'priority': 'RECOMMEND',

            # 경로 좌표가 필요하므로 False
            'summary': 'false'
        }

        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        return parse_car_route(data)


    # ==========================================
    # 대중교통
    # ==========================================

    elif transport == 'public_transport':

        url = (
            'https://dapi.kakao.com/'
            'v2/routing/publictraffic'
        )


    # ==========================================
    # 도보
    # ==========================================

    elif transport == 'walk':

        url = (
            'https://dapi.kakao.com/'
            'v2/routing/walk'
        )


    # ==========================================
    # 자전거
    # ==========================================

    elif transport == 'bike':

        url = (
            'https://dapi.kakao.com/'
            'v2/routing/bicycle'
        )

    else:

        raise ValueError(
            f'지원하지 않는 교통수단: {transport}'
        )


    params = {
        'start_x': str(start_lon),
        'start_y': str(start_lat),
        'end_x': str(end_lon),
        'end_y': str(end_lat),
    }

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=10
    )

    response.raise_for_status()

    data = response.json()


    if transport == 'public_transport':

        return parse_public_route(data)

    return parse_walk_bike_route(data)

from math import radians, sin, cos, sqrt, atan2


# ==============================================
# 두 좌표 사이 직선거리 계산
# ==============================================

def calculate_distance(
    lat1,
    lon1,
    lat2,
    lon2
):
    """
    두 좌표 사이 직선거리 계산
    반환값: km
    """

    lat1 = float(lat1)
    lon1 = float(lon1)
    lat2 = float(lat2)
    lon2 = float(lon2)

    earth_radius = 6371

    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)

    a = (
        sin(d_lat / 2) ** 2
        + cos(radians(lat1))
        * cos(radians(lat2))
        * sin(d_lon / 2) ** 2
    )

    c = 2 * atan2(
        sqrt(a),
        sqrt(1 - a)
    )

    return earth_radius * c


# ==============================================
# 이동시간 계산
# ==============================================

def get_travel_time(
    lat1,
    lon1,
    lat2,
    lon2,
    transport
):
    """
    이동시간 반환
    단위: 분

    현재는 직선거리 + 평균속도 기반.
    실제 카카오 경로 API와 연결되면 교체 가능.
    """

    distance = calculate_distance(
        lat1,
        lon1,
        lat2,
        lon2
    )

    # DB에 CAR / car 둘 다 들어올 수 있으므로 통일
    transport = str(transport).strip().lower()

        # 실제 도로는 직선거리보다 길기 때문에 보정
    road_distance = distance * 1.15

    if transport == 'car':

        # 장거리
        if distance >= 100:
            speed = 80

        # 중거리
        elif distance >= 30:
            speed = 60

        # 시내 이동
        else:
            speed = 30

    elif transport == 'walk':
        speed = 4

    elif transport == 'bike':
        speed = 15

    elif transport in (
        'public transport',
        'public_transport'
    ):
        speed = 25

    else:
        speed = 30

    hours = (
        road_distance
        /
        speed
    )

    minutes = round(
        hours * 60
    )

    return max(
        minutes,
        1
    )


# ==============================================
# 자동차 경로 파싱
# ==============================================

def parse_car_route(data):

    routes = data.get('routes', [])

    if not routes:
        return None

    route = routes[0]

    if route.get('result_code') != 0:
        return None

    points = []

    for section in route.get('sections', []):

        for road in section.get('roads', []):

            vertexes = road.get(
                'vertexes',
                []
            )

            # [경도, 위도, 경도, 위도 ...]
            for i in range(
                0,
                len(vertexes),
                2
            ):

                points.append({
                    'lon': vertexes[i],
                    'lat': vertexes[i + 1]
                })

    summary = route.get('summary', {})

    return {
        'points': points,

        'distance':
            summary.get('distance', 0),

        'duration':
            summary.get('duration', 0)
    }

# ==============================================
# 도보 / 자전거 경로 파싱
# ==============================================

def parse_walk_bike_route(data):

    if data.get('status') != 'OK':
        return None

    route = data.get('route')

    if not route:
        return None

    points = []

    for leg in route.get('legs', []):

        for step in leg.get('steps', []):

            path = step.get(
                'path',
                {}
            )

            for point in path.get(
                'points',
                []
            ):

                points.append({
                    'lon': point[0],
                    'lat': point[1]
                })

    properties = route.get(
        'properties',
        {}
    )

    return {
        'points': points,

        'distance':
            properties.get(
                'totalDistance',
                0
            ),

        'duration':
            properties.get(
                'totalTime',
                0
            )
    }

# ==============================================
# 대중교통 경로 파싱
# ==============================================

def parse_public_route(data):

    if data.get('status') != 'OK':
        return None

    routes = data.get(
        'routes',
        []
    )

    if not routes:
        return None

    # 첫 번째 추천 경로 사용
    route = routes[0]

    points = []

    for step in route.get(
        'steps',
        []
    ):

        path = step.get(
            'path',
            {}
        )

        for point in path.get(
            'points',
            []
        ):

            points.append({
                'lon': point[0],
                'lat': point[1]
            })

    properties = route.get(
        'properties',
        {}
    )

    return {
        'points': points,

        'distance':
            properties.get(
                'totalDistance',
                0
            ),

        'duration':
            properties.get(
                'totalTime',
                0
            )
    }

