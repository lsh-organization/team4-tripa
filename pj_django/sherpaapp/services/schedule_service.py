from datetime import datetime, timedelta, time

from ..models import (
    Category,
    Place,
    Schedule,
    SchedulePlace,
    TravelDayPlan,
)

from .place_service import search_places
from .route_service import (
    calculate_distance,
    get_travel_time,
)


# =========================================================
# 기본 설정
# =========================================================

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

    # 자동 일정에서 추가 사용
    '숙박': 30,
}


# 하루 관광 장소 최대 개수
# 음식 / 숙박은 포함하지 않음
MAX_ACTIVITY_PER_DAY = 3


# 첫날 시작
FIRST_DAY_START = time(9, 0)


# 2일차 이후 시작
NORMAL_DAY_START = time(9, 0)


# 하루 종료 기준
DAY_END = time(
    21,
    30
)


# 점심 목표시간
LUNCH_TIME = time(
    12,
    30
)


# 저녁 목표시간
DINNER_TIME = time(
    18,
    30
)


# =========================================================
# 선택 카테고리
# =========================================================

def get_selected_categories(travel):

    return (
        Category.objects
        .filter(
            travel_categories__travel=travel
        )
        .distinct()
    )


# =========================================================
# 체류시간
# =========================================================

def get_stay_time(category_name):

    return DEFAULT_STAY_TIME.get(
        category_name,
        60
    )


# =========================================================
# 여행 날짜 생성
# =========================================================

def create_travel_dates(travel):

    start_date = travel.t_start
    end_date = travel.t_end


    if isinstance(
        start_date,
        str
    ):

        start_date = (
            datetime.strptime(
                start_date,
                '%Y-%m-%d'
            )
            .date()
        )


    if isinstance(
        end_date,
        str
    ):

        end_date = (
            datetime.strptime(
                end_date,
                '%Y-%m-%d'
            )
            .date()
        )


    dates = []

    current_date = start_date


    while (
        current_date
        <=
        end_date
    ):

        dates.append(
            current_date
        )

        current_date += timedelta(
            days=1
        )


    return dates


# =========================================================
# time 값 정규화
# =========================================================

def normalize_time(value):

    if value is None:

        return None


    if isinstance(
        value,
        time
    ):

        return value


    if isinstance(
        value,
        datetime
    ):

        return value.time()


    if isinstance(
        value,
        str
    ):

        value = value.strip()

        if not value:

            return None


        for format_string in (
            '%H:%M:%S',
            '%H:%M',
        ):

            try:

                return (
                    datetime.strptime(
                        value,
                        format_string
                    )
                    .time()
                )

            except ValueError:

                pass


    return None


# =========================================================
# 숫자 변환
# =========================================================

def to_float(value):

    if value is None:

        return None


    try:

        return float(
            value
        )

    except (
        TypeError,
        ValueError
    ):

        return None


# =========================================================
# 후보 장소 좌표
#
# Kakao
# x = 경도
# y = 위도
# =========================================================

def get_candidate_coordinate(
    candidate
):

    lat = (
        candidate.get('y')
        or
        candidate.get('lat')
    )

    lon = (
        candidate.get('x')
        or
        candidate.get('lon')
    )


    lat = to_float(
        lat
    )

    lon = to_float(
        lon
    )


    if (
        lat is None
        or
        lon is None
    ):

        return (
            None,
            None
        )


    return (
        lat,
        lon
    )


# =========================================================
# 후보 장소 고유 KEY
# =========================================================

def get_candidate_key(
    candidate
):

    name = (
        candidate
        .get(
            'name',
            ''
        )
        .strip()
    )

    address = (
        candidate
        .get(
            'address',
            ''
        )
        .strip()
    )


    return (
        name,
        address
    )


# =========================================================
# 장소 중복 제거
# =========================================================

def remove_duplicate_places(
    candidates
):

    result = []

    seen = set()


    for candidate in candidates:

        key = get_candidate_key(
            candidate
        )


        if not key[0]:

            continue


        if key in seen:

            continue


        lat, lon = (
            get_candidate_coordinate(
                candidate
            )
        )


        # 지도 / 거리 계산 때문에
        # 좌표 없는 장소는 자동 일정에서 제외
        if (
            lat is None
            or
            lon is None
        ):

            continue


        seen.add(
            key
        )

        result.append(
            candidate
        )


    return result


# =========================================================
# 이동시간
# =========================================================

def calculate_travel_minutes(
    start_point,
    end_point,
    transport
):

    if (
        start_point is None
        or
        end_point is None
    ):

        return 0


    try:

        minutes = get_travel_time(

            start_point[0],
            start_point[1],

            end_point[0],
            end_point[1],

            transport
        )


        return max(
            int(minutes),
            0
        )


    except Exception as e:

        print(
            '이동시간 계산 실패:',
            e
        )

        return 0


# =========================================================
# 현재 위치에서 가장 가까운 장소
# =========================================================

def find_nearest_candidate(
    candidates,
    used_places,
    current_point=None
):

    available = []


    for candidate in candidates:

        key = get_candidate_key(
            candidate
        )


        if key in used_places:

            continue


        lat, lon = (
            get_candidate_coordinate(
                candidate
            )
        )


        if (
            lat is None
            or
            lon is None
        ):

            continue


        available.append(
            candidate
        )


    if not available:

        return None


    # 출발 위치가 없으면
    # 첫 번째 후보
    if current_point is None:

        return available[0]


    def distance(candidate):

        lat, lon = (
            get_candidate_coordinate(
                candidate
            )
        )


        try:

            return calculate_distance(

                current_point[0],
                current_point[1],

                lat,
                lon
            )

        except Exception:

            return 999999


    return min(
        available,
        key=distance
    )


# =========================================================
# 체크인 전 해당 장소를 방문할 수 있는지 계산
# =========================================================

def can_visit_before_fixed_time(
    candidate,
    current_datetime,
    current_point,
    fixed_datetime,
    fixed_point,
    transport
):

    candidate_point = (
        get_candidate_coordinate(
            candidate
        )
    )


    category_name = (
        candidate.get(
            'selected_category'
        )
        or
        '기타'
    )


    stay_time = (
        get_stay_time(
            category_name
        )
    )


    # 현재 장소 -> 후보 장소
    first_travel = (
        calculate_travel_minutes(

            current_point,
            candidate_point,
            transport
        )
    )


    candidate_finish = (

        current_datetime

        +

        timedelta(
            minutes=
                first_travel
                +
                stay_time
        )
    )


    # 후보 장소 -> 체크인 장소
    second_travel = (
        calculate_travel_minutes(

            candidate_point,
            fixed_point,
            transport
        )
    )


    final_arrival = (

        candidate_finish

        +

        timedelta(
            minutes=
                second_travel
        )
    )


    return (
        final_arrival
        <=
        fixed_datetime
    )


# =========================================================
# DB PLACE 생성 / 조회
# =========================================================

def get_or_create_place(
    travel,
    candidate
):

    lat, lon = (
        get_candidate_coordinate(
            candidate
        )
    )


    category_name = (
        candidate.get(
            'selected_category'
        )
        or
        candidate.get(
            'category'
        )
        or
        '기타'
    )


    place_obj, created = (
        Place.objects
        .get_or_create(

            travel=travel,

            p_name=
                candidate.get(
                    'name'
                ),

            defaults={

                'p_addr':
                    candidate.get(
                        'address'
                    )
                    or '',

                'p_lat':
                    lat,

                'p_lon':
                    lon,

                'p_kind':
                    category_name,
            }
        )
    )


    # 기존 장소인데 좌표 등이 비어 있으면 갱신
    changed = False


    if (
        not place_obj.p_addr
        and
        candidate.get(
            'address'
        )
    ):

        place_obj.p_addr = (
            candidate.get(
                'address'
            )
        )

        changed = True


    if (
        not place_obj.p_lat
        and
        lat is not None
    ):

        place_obj.p_lat = lat

        changed = True


    if (
        not place_obj.p_lon
        and
        lon is not None
    ):

        place_obj.p_lon = lon

        changed = True


    if changed:

        place_obj.save()


    return place_obj


# =========================================================
# SchedulePlace 하나 저장
# =========================================================

def save_schedule_place(
    travel,
    schedule,
    candidate,
    visit_order,
    current_datetime,
    current_point,
    transport,
    forced_arrival=None,
    stay_time_override=None
):

    candidate_point = (
        get_candidate_coordinate(
            candidate
        )
    )


    travel_time = (
        calculate_travel_minutes(

            current_point,
            candidate_point,
            transport
        )
    )


    calculated_arrival = (

        current_datetime

        +

        timedelta(
            minutes=
                travel_time
        )
    )


    # 점심 / 저녁 / 체크인처럼
    # 목표시간이 있는 경우
    if (
        forced_arrival
        and
        calculated_arrival
        <
        forced_arrival
    ):

        arrival_datetime = (
            forced_arrival
        )

    else:

        arrival_datetime = (
            calculated_arrival
        )


    category_name = (
        candidate.get(
            'selected_category'
        )
        or
        '기타'
    )


    if stay_time_override is None:

        stay_time = (
            get_stay_time(
                category_name
            )
        )

    else:

        stay_time = (
            stay_time_override
        )


    departure_datetime = (

        arrival_datetime

        +

        timedelta(
            minutes=
                stay_time
        )
    )


    place_obj = (
        get_or_create_place(
            travel,
            candidate
        )
    )


    SchedulePlace.objects.create(

        schedule=
            schedule,

        place=
            place_obj,

        visit_order=
            visit_order,

        stay_time=
            stay_time,

        arrive_time=
            arrival_datetime.time(),

        start_time=
            departure_datetime.time(),

        travel_time=
            travel_time
    )


    print(
        schedule.s_day,
        visit_order,
        candidate.get('name'),
        '도착:',
        arrival_datetime.time(),
        '이동:',
        travel_time,
        '체류:',
        stay_time
    )


    return (
        departure_datetime,
        candidate_point,
        visit_order + 1
    )


# =========================================================
# 숙소 후보
# =========================================================

def get_accommodation_candidate(
    travel
):

    accommodation = (
        getattr(
            travel,
            'accommodation',
            None
        )
    )


    if not accommodation:

        return None


    lat = to_float(
        getattr(
            travel,
            'accommodation_lat',
            None
        )
    )

    lon = to_float(
        getattr(
            travel,
            'accommodation_lon',
            None
        )
    )


    # DB에 좌표까지 있으면
    # 바로 사용
    if (
        lat is not None
        and
        lon is not None
    ):

        return {

            'name':
                accommodation,

            'address':
                accommodation,

            'x':
                lon,

            'y':
                lat,

            'selected_category':
                '숙박',
        }


    # 숙소명만 있으면
    # 카카오에서 검색
    try:

        results = search_places(
            travel.t_place,
            accommodation
        )

    except Exception as e:

        print(
            '숙소 검색 실패:',
            e
        )

        results = []


    if not results:

        return None


    candidate = (
        results[0].copy()
    )


    candidate[
        'selected_category'
    ] = '숙박'


    return candidate


# =========================================================
# 첫날 출발 위치
# =========================================================

def get_start_point(
    travel
):

    lat = to_float(
        getattr(
            travel,
            'start_lat',
            None
        )
    )

    lon = to_float(
        getattr(
            travel,
            'start_lon',
            None
        )
    )


    if (
        lat is None
        or
        lon is None
    ):

        return None


    return (
        lat,
        lon
    )


# =========================================================
# 활동 장소 후보 + 음식 후보
# =========================================================

def build_place_candidates(
    travel,
    categories
):

    activity_candidates = []

    meal_candidates = []


    # ==========================================
    # 사용자가 고른 컨셉
    # ==========================================

    for category in categories:

        try:

            searched_places = (
                search_places(

                    travel.t_place,

                    category.c_name
                )

                or
                []
            )

        except Exception as e:

            print(
                category.c_name,
                '장소 검색 실패:',
                e
            )

            continue


        print(
            category.c_name,
            '검색:',
            len(
                searched_places
            )
        )


        for place in searched_places:

            candidate = (
                place.copy()
            )


            candidate[
                'selected_category'
            ] = category.c_name


            # 음식은 관광 후보가 아니라
            # 점심/저녁 후보로 사용
            if (
                category.c_name
                ==
                '음식'
            ):

                meal_candidates.append(
                    candidate
                )

            else:

                activity_candidates.append(
                    candidate
                )


    # ==========================================
    # 음식 카테고리를 선택하지 않았더라도
    # 점심/저녁은 추천
    # ==========================================

    try:

        restaurant_results = (
            search_places(

                travel.t_place,

                '맛집'
            )

            or
            []
        )

    except Exception as e:

        print(
            '맛집 검색 실패:',
            e
        )

        restaurant_results = []


    for place in restaurant_results:

        candidate = (
            place.copy()
        )

        candidate[
            'selected_category'
        ] = '음식'

        meal_candidates.append(
            candidate
        )


    return (

        remove_duplicate_places(
            activity_candidates
        ),

        remove_duplicate_places(
            meal_candidates
        )
    )


# =========================================================
# 일정 구간에 관광지 자동 채우기
# =========================================================

def fill_activities(
    travel,
    schedule,
    candidates,
    used_places,
    current_datetime,
    current_point,
    visit_order,
    activity_count,
    limit_datetime,
    transport,
    max_activity_count,
    reach_point=None
):

    while (
        activity_count
        <
        max_activity_count
    ):

        if (
            current_datetime
            >=
            limit_datetime
        ):

            break


        possible = []


        # ======================================
        # 시간 안에 들어갈 수 있는 장소만 필터
        # ======================================

        for candidate in candidates:

            key = get_candidate_key(
                candidate
            )


            if key in used_places:

                continue


            candidate_point = (
                get_candidate_coordinate(
                    candidate
                )
            )


            travel_time = (
                calculate_travel_minutes(

                    current_point,
                    candidate_point,
                    transport
                )
            )


            stay_time = (
                get_stay_time(

                    candidate.get(
                        'selected_category'
                    )
                    or
                    '기타'
                )
            )


            finish_datetime = (

                current_datetime

                +

                timedelta(
                    minutes=
                        travel_time
                        +
                        stay_time
                )
            )


            # 단순 시간 제한
            if reach_point is None:

                if (
                    finish_datetime
                    <=
                    limit_datetime
                ):

                    possible.append(
                        candidate
                    )


            # 체크인 장소까지
            # 이동시간까지 포함해서 계산
            else:

                if (
                    can_visit_before_fixed_time(

                        candidate,
                        current_datetime,
                        current_point,
                        limit_datetime,
                        reach_point,
                        transport
                    )
                ):

                    possible.append(
                        candidate
                    )


        if not possible:

            break


        # ======================================
        # 현재 위치에서 가장 가까운 장소
        # ======================================

        candidate = (
            find_nearest_candidate(

                possible,
                used_places,
                current_point
            )
        )


        if candidate is None:

            break


        used_places.add(
            get_candidate_key(
                candidate
            )
        )


        (
            current_datetime,
            current_point,
            visit_order
        ) = save_schedule_place(

            travel,
            schedule,
            candidate,
            visit_order,
            current_datetime,
            current_point,
            transport
        )


        activity_count += 1


    return (
        current_datetime,
        current_point,
        visit_order,
        activity_count
    )


# =========================================================
# 점심 / 저녁 추가
# =========================================================

def add_meal(
    travel,
    schedule,
    meal_candidates,
    used_places,
    current_datetime,
    current_point,
    visit_order,
    transport,
    target_datetime
):

    candidate = (
        find_nearest_candidate(

            meal_candidates,
            used_places,
            current_point
        )
    )


    if candidate is None:

        print(
            '추천 가능한 음식점이 없습니다.'
        )

        return (
            current_datetime,
            current_point,
            visit_order
        )


    used_places.add(
        get_candidate_key(
            candidate
        )
    )


    return save_schedule_place(

        travel,
        schedule,
        candidate,
        visit_order,
        current_datetime,
        current_point,
        transport,

        forced_arrival=
            target_datetime,

        stay_time_override=
            90
    )


# =========================================================
# 체크인
# =========================================================

def add_checkin(
    travel,
    schedule,
    accommodation,
    current_datetime,
    current_point,
    visit_order,
    transport,
    checkin_datetime
):

    if accommodation is None:

        return (
            current_datetime,
            current_point,
            visit_order
        )


    print(
        '체크인:',
        accommodation.get(
            'name'
        ),
        checkin_datetime.time()
    )


    return save_schedule_place(

        travel,
        schedule,
        accommodation,
        visit_order,
        current_datetime,
        current_point,
        transport,

        forced_arrival=
            checkin_datetime,

        stay_time_override=
            30
    )



# =========================================================
# 날짜별 숙소 / 시작점 일반화
# =========================================================

DEFAULT_ACCOMMODATION_ARRIVAL = time(20, 0)


def build_accommodation_candidate(
    name,
    address=None,
    lat=None,
    lon=None,
):
    """TravelDayPlan/Travel 숙소 정보를 일정 후보 형식으로 변환한다."""

    name = (name or '').strip()

    if not name:
        return None

    lat = to_float(lat)
    lon = to_float(lon)

    if lat is None or lon is None:
        return None

    return {
        'name': name,
        'address': (address or name).strip(),
        'x': lon,
        'y': lat,
        'selected_category': '숙박',
        'category': '숙박',
    }


def get_legacy_accommodation_candidate(travel):
    """기존 Travel 숙소 컬럼을 임시 fallback으로 유지한다."""

    return build_accommodation_candidate(
        getattr(travel, 'accommodation', None),
        getattr(travel, 'accommodation', None),
        getattr(travel, 'accommodation_lat', None),
        getattr(travel, 'accommodation_lon', None),
    )


def get_travel_day_plans(travel):
    """날짜를 key로 하는 TravelDayPlan dict를 반환한다."""

    return {
        plan.plan_date: plan
        for plan in (
            TravelDayPlan.objects
            .filter(travel=travel)
            .order_by('plan_date', 'tdp_id')
        )
    }


def resolve_effective_accommodations(
    travel,
    travel_dates,
    day_plan_map,
):
    """
    숙소가 비어 있는 날은 이전 숙소를 그대로 사용한다.

    DAY 1 숙소 = DAY 1 일정 종료 지점
    DAY 2 시작점 = DAY 1 숙소
    """

    effective = {}

    current_accommodation = (
        get_legacy_accommodation_candidate(travel)
    )

    for travel_date in travel_dates:

        plan = day_plan_map.get(
            travel_date
        )

        if plan:
            candidate = build_accommodation_candidate(
                plan.accommodation_name,
                plan.accommodation_addr,
                plan.accommodation_lat,
                plan.accommodation_lon,
            )

            if candidate:
                current_accommodation = candidate

        effective[travel_date] = (
            current_accommodation.copy()
            if current_accommodation
            else None
        )

    return effective


def get_day_start_time(
    travel,
    travel_date,
    day_index,
    day_plan_map,
):
    """사용자 입력 시간이 없으면 09:00을 사용한다."""

    if day_index == 0:
        return (
            normalize_time(
                getattr(
                    travel,
                    'start_time',
                    None,
                )
            )
            or FIRST_DAY_START
        )

    plan = day_plan_map.get(
        travel_date
    )

    return (
        normalize_time(
            getattr(
                plan,
                'departure_time',
                None,
            )
            if plan
            else None
        )
        or NORMAL_DAY_START
    )


def get_day_accommodation_arrival_time(
    travel_date,
    day_plan_map,
):
    """숙소 도착 시간이 없으면 20:00을 사용한다."""

    plan = day_plan_map.get(
        travel_date
    )

    return (
        normalize_time(
            getattr(
                plan,
                'arrival_time',
                None,
            )
            if plan
            else None
        )
        or DEFAULT_ACCOMMODATION_ARRIVAL
    )


def get_first_day_start_candidate(travel):
    """지도 경로 계산에서도 재사용하기 쉬운 출발지 후보 정보."""

    name = (
        getattr(
            travel,
            'start_place',
            None,
        )
        or '출발지'
    )

    lat = to_float(
        getattr(
            travel,
            'start_lat',
            None,
        )
    )

    lon = to_float(
        getattr(
            travel,
            'start_lon',
            None,
        )
    )

    if lat is None or lon is None:
        return None

    return {
        'name': name,
        'address': (
            getattr(
                travel,
                'start_addr',
                None,
            )
            or name
        ),
        'x': lon,
        'y': lat,
        'selected_category': '출발지',
        'category': '출발지',
    }


def add_meal_before_deadline(
    travel,
    schedule,
    meal_candidates,
    used_places,
    current_datetime,
    current_point,
    visit_order,
    transport,
    target_datetime,
    fixed_datetime=None,
    fixed_point=None,
):
    """
    숙소 도착 시간이 정해져 있으면
    식사 후 숙소까지 갈 수 있는 음식점만 선택한다.
    """

    possible = []

    for candidate in meal_candidates:

        key = get_candidate_key(
            candidate
        )

        if key in used_places:
            continue

        if (
            fixed_datetime is not None
            and fixed_point is not None
        ):

            if not can_visit_before_fixed_time(
                candidate,
                current_datetime,
                current_point,
                fixed_datetime,
                fixed_point,
                transport,
            ):
                continue

        possible.append(
            candidate
        )

    candidate = find_nearest_candidate(
        possible,
        used_places,
        current_point,
    )

    if candidate is None:
        return (
            current_datetime,
            current_point,
            visit_order,
        )

    used_places.add(
        get_candidate_key(
            candidate
        )
    )

    return save_schedule_place(
        travel,
        schedule,
        candidate,
        visit_order,
        current_datetime,
        current_point,
        transport,
        forced_arrival=target_datetime,
        stay_time_override=90,
    )


def add_accommodation_arrival(
    travel,
    schedule,
    accommodation,
    current_datetime,
    current_point,
    visit_order,
    transport,
    arrival_datetime,
):
    """
    숙소는 '숙박 체류'가 아니라 '숙소 도착 이벤트'로 저장한다.
    다음 날의 시작점은 TravelDayPlan에서 별도로 계산한다.
    """

    if accommodation is None:
        return (
            current_datetime,
            current_point,
            visit_order,
        )

    return save_schedule_place(
        travel,
        schedule,
        accommodation,
        visit_order,
        current_datetime,
        current_point,
        transport,
        forced_arrival=arrival_datetime,
        stay_time_override=0,
    )



# =========================================================
# 메인 자동 일정 생성
# =========================================================

def generate_schedule(
    travel,
    reset_existing=True,
):
    """
    날짜별 시작점/숙소를 반영해 일정을 생성한다.

    DAY 1:
        Travel.start_* -> 관광/식사 -> DAY 1 숙소

    DAY 2 이후:
        전날 숙소 -> 관광/식사 -> 해당 DAY 숙소

    TravelDayPlan의 숙소가 비어 있으면 이전 숙소를 그대로 사용한다.
    출발시간 미입력: 09:00
    숙소 도착시간 미입력: 20:00
    """

    print()
    print('=================================')
    print('날짜별 자동 일정 생성 시작')
    print('여행:', travel.t_title)
    print('지역:', travel.t_place)

    # =====================================================
    # 1. 날짜 / DAY Schedule
    # =====================================================

    travel_dates = create_travel_dates(
        travel
    )

    schedules = []

    for travel_date in travel_dates:

        schedule, created = (
            Schedule.objects
            .get_or_create(
                travel=travel,
                s_day=travel_date,
            )
        )

        schedules.append(
            schedule
        )

        if reset_existing:
            (
                SchedulePlace.objects
                .filter(
                    schedule=schedule
                )
                .delete()
            )

        print(
            'Schedule:',
            schedule.s_id,
            schedule.s_day,
            'created:',
            created,
        )

    # =====================================================
    # 2. 컨셉 / 장소 후보
    # =====================================================

    categories = list(
        get_selected_categories(
            travel
        )
    )

    if not categories:
        print('선택된 카테고리가 없습니다.')
        return schedules

    (
        activity_candidates,
        meal_candidates,
    ) = build_place_candidates(
        travel,
        categories,
    )

    # =====================================================
    # 3. TravelDayPlan 해석
    # =====================================================

    day_plan_map = get_travel_day_plans(
        travel
    )

    effective_accommodations = (
        resolve_effective_accommodations(
            travel,
            travel_dates,
            day_plan_map,
        )
    )

    first_start_candidate = (
        get_first_day_start_candidate(
            travel
        )
    )

    used_places = set()

    # =====================================================
    # 4. DAY별 일정
    # =====================================================

    for day_index, schedule in enumerate(
        schedules
    ):

        travel_date = schedule.s_day

        start_time = get_day_start_time(
            travel,
            travel_date,
            day_index,
            day_plan_map,
        )

        current_datetime = datetime.combine(
            travel_date,
            start_time,
        )

        # ---------------------------------------------
        # DAY 시작점
        # ---------------------------------------------

        if day_index == 0:

            current_point = (
                get_candidate_coordinate(
                    first_start_candidate
                )
                if first_start_candidate
                else get_start_point(
                    travel
                )
            )

        else:

            previous_date = (
                travel_dates[
                    day_index - 1
                ]
            )

            previous_accommodation = (
                effective_accommodations.get(
                    previous_date
                )
            )

            current_point = (
                get_candidate_coordinate(
                    previous_accommodation
                )
                if previous_accommodation
                else None
            )

        # ---------------------------------------------
        # 해당 DAY 종료 숙소
        #
        # 마지막 날은 기본적으로 숙박 일정이 없다.
        # ---------------------------------------------

        is_last_day = (
            day_index
            ==
            len(schedules) - 1
        )

        accommodation = None
        accommodation_point = None
        accommodation_datetime = None

        if not is_last_day:

            accommodation = (
                effective_accommodations.get(
                    travel_date
                )
            )

            if accommodation:

                accommodation_point = (
                    get_candidate_coordinate(
                        accommodation
                    )
                )

                accommodation_datetime = (
                    datetime.combine(
                        travel_date,
                        get_day_accommodation_arrival_time(
                            travel_date,
                            day_plan_map,
                        ),
                    )
                )

        day_end_datetime = (
            accommodation_datetime
            or datetime.combine(
                travel_date,
                DAY_END,
            )
        )

        lunch_datetime = datetime.combine(
            travel_date,
            LUNCH_TIME,
        )

        dinner_datetime = datetime.combine(
            travel_date,
            DINNER_TIME,
        )

        visit_order = 1
        activity_count = 0

        print()
        print(
            f'DAY {day_index + 1}',
            travel_date,
            '출발:',
            start_time,
            '숙소:',
            accommodation.get('name')
            if accommodation
            else None,
            '숙소도착:',
            accommodation_datetime.time()
            if accommodation_datetime
            else None,
        )

        # =================================================
        # 오전 관광
        # =================================================

        morning_limit = min(
            lunch_datetime,
            day_end_datetime,
        )

        (
            current_datetime,
            current_point,
            visit_order,
            activity_count,
        ) = fill_activities(
            travel,
            schedule,
            activity_candidates,
            used_places,
            current_datetime,
            current_point,
            visit_order,
            activity_count,
            morning_limit,
            travel.t_way,
            MAX_ACTIVITY_PER_DAY,
            reach_point=(
                accommodation_point
                if morning_limit == day_end_datetime
                else None
            ),
        )

        # =================================================
        # 점심
        # =================================================

        if (
            lunch_datetime
            <
            day_end_datetime
            and current_datetime.time()
            <
            time(15, 0)
        ):

            (
                current_datetime,
                current_point,
                visit_order,
            ) = add_meal_before_deadline(
                travel,
                schedule,
                meal_candidates,
                used_places,
                current_datetime,
                current_point,
                visit_order,
                travel.t_way,
                lunch_datetime,
                fixed_datetime=(
                    accommodation_datetime
                    if accommodation
                    else None
                ),
                fixed_point=(
                    accommodation_point
                    if accommodation
                    else None
                ),
            )

        # =================================================
        # 오후 관광
        # =================================================

        afternoon_limit = min(
            dinner_datetime,
            day_end_datetime,
        )

        (
            current_datetime,
            current_point,
            visit_order,
            activity_count,
        ) = fill_activities(
            travel,
            schedule,
            activity_candidates,
            used_places,
            current_datetime,
            current_point,
            visit_order,
            activity_count,
            afternoon_limit,
            travel.t_way,
            MAX_ACTIVITY_PER_DAY,
            reach_point=(
                accommodation_point
                if afternoon_limit == day_end_datetime
                else None
            ),
        )

        # =================================================
        # 저녁
        # =================================================

        if (
            dinner_datetime
            <
            day_end_datetime
            and current_datetime.time()
            <
            time(21, 0)
        ):

            (
                current_datetime,
                current_point,
                visit_order,
            ) = add_meal_before_deadline(
                travel,
                schedule,
                meal_candidates,
                used_places,
                current_datetime,
                current_point,
                visit_order,
                travel.t_way,
                dinner_datetime,
                fixed_datetime=(
                    accommodation_datetime
                    if accommodation
                    else None
                ),
                fixed_point=(
                    accommodation_point
                    if accommodation
                    else None
                ),
            )

        # =================================================
        # 저녁 이후 / 숙소 전 남는 시간
        # =================================================

        (
            current_datetime,
            current_point,
            visit_order,
            activity_count,
        ) = fill_activities(
            travel,
            schedule,
            activity_candidates,
            used_places,
            current_datetime,
            current_point,
            visit_order,
            activity_count,
            day_end_datetime,
            travel.t_way,
            MAX_ACTIVITY_PER_DAY,
            reach_point=(
                accommodation_point
                if accommodation
                else None
            ),
        )

        # =================================================
        # 해당 DAY 숙소 도착
        # =================================================

        if (
            accommodation
            and accommodation_datetime
        ):

            (
                current_datetime,
                current_point,
                visit_order,
            ) = add_accommodation_arrival(
                travel,
                schedule,
                accommodation,
                current_datetime,
                current_point,
                visit_order,
                travel.t_way,
                accommodation_datetime,
            )

    print()
    print('날짜별 자동 일정 생성 완료')
    print('=================================')

    return schedules
