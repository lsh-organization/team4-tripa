from datetime import timedelta

from ..models import (
    Category,
    TravelCategory,
    Place,
    Schedule,
    SchedulePlace,
)

from .place_service import search_places
from .route_service import calculate_distance, get_travel_time


DEFAULT_STAY_TIME = {
    '쇼핑': 120,
    '역사': 90,
    '전통문화': 90,
    '랜드마크': 60,
    '카페': 60,
    '공원': 90,
    '음식': 90,
    '자연': 120,
    '바다': 120,
}


def get_selected_categories(travel):

    return Category.objects.filter(
        travel_categories__travel=travel
    )


def get_stay_time(category_name):

    return DEFAULT_STAY_TIME.get(
        category_name,
        60
    )


def create_travel_dates(travel):

    dates = []

    current_date = travel.t_start

    while current_date <= travel.t_end:

        dates.append(current_date)

        current_date += timedelta(days=1)

    return dates


def generate_schedule(travel):

    # ============================
    # 1. 여행 날짜 생성
    # ============================

    travel_dates = create_travel_dates(
        travel
    )

    # ============================
    # 2. 선택 카테고리 조회
    # ============================

    categories = get_selected_categories(
        travel
    )

    # ============================
    # 3. 카테고리별 장소 후보 검색
    # ============================

    place_candidates = []

    for category in categories:

        searched_places = search_places(
            travel.t_place,
            category.c_name
        )

        place_candidates.extend(
            searched_places
        )

    # 일단 테스트용
    print('============================')
    print('여행:', travel.t_title)
    print('지역:', travel.t_place)
    print('날짜:', travel_dates)

    for place in place_candidates:
        print(
            place['category'],
            place['name']
        )

    print('============================')

    # 이후 단계에서
    #
    # 날짜별 Schedule 생성
    # 장소 중복 제거
    # 이동시간 계산
    # 점심/저녁 배치
    # 체크인 시간 처리
    # SchedulePlace 저장