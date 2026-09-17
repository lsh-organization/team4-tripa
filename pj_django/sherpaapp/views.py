from datetime import datetime, timedelta, time, date
import requests
from django.conf import settings
from django.db.models import Prefetch
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template import loader
from .models import Member
from .models import Travel
from .models import Place
from .models import Schedule
from .models import Pay
from .models import Category
from .models import SchedulePlace
from .services.schedule_service import generate_schedule
from .services.route_service import get_kakao_route
from .models import TravelCategory
from .models import TravelDayPlan

# ==============================================
# 카카오 이미지 검색 공통 함수
# ==============================================
def _search_kakao_image(query):
    """장소명으로 대표 이미지 URL 1개를 조회한다."""
    query = (query or '').strip()
    if not query:
        return None

    headers = {
        'Authorization': f'KakaoAK {settings.KAKAO_REST_API_KEY}'
    }

    response = requests.get(
        'https://dapi.kakao.com/v2/search/image',
        headers=headers,
        params={'query': query, 'size': 1},
        timeout=10,
    )
    response.raise_for_status()

    data = response.json()
    documents = data.get('documents', [])

    if not documents:
        return None

    return (
        documents[0].get('thumbnail_url')
        or documents[0].get('image_url')
    )


# ==============================================
# 카카오 장소 검색 공통 함수
# ==============================================
def _search_kakao_places(query, size=5):
    """카카오 장소 검색 + 대표 이미지 검색 결과를 공통 형식으로 반환한다."""
    query = (query or '').strip()
    if not query:
        return []

    headers = {
        'Authorization': f'KakaoAK {settings.KAKAO_REST_API_KEY}'
    }

    place_response = requests.get(
        'https://dapi.kakao.com/v2/local/search/keyword.json',
        headers=headers,
        params={'query': query, 'size': size},
        timeout=10,
    )
    place_response.raise_for_status()
    place_data = place_response.json()

    places = []

    for item in place_data.get('documents', []):
        place_name = item.get('place_name', '')
        image = None

        if place_name:
            try:
                image = _search_kakao_image(place_name)
            except requests.RequestException:
                # 이미지 조회 실패는 장소 검색 자체를 실패시키지 않는다.
                image = None

        places.append({
            'name': place_name,
            'address': item.get('road_address_name') or item.get('address_name'),
            'category': item.get('category_name'),
            'phone': item.get('phone'),
            'place_url': item.get('place_url'),
            'x': item.get('x'),
            'y': item.get('y'),
            'image': image,
        })

    return places


# 회원가입
def join(request):
    template = loader.get_template('sherpaapp/join.html')
    return HttpResponse(
        template.render({},request))

# 로그인
def login(request):
    template = loader.get_template('sherpaapp/login.html')
    return HttpResponse(template.render({},request))

# 장소 검색
def place_search(request):

    login_user = request.session.get('login_ok_user')

    member = None
    travels = Travel.objects.none()

    if login_user:
        try:
            member = Member.objects.get(
                email=login_user
            )

            travels = (
                Travel.objects
                .filter(member=member)
                .order_by('-t_id')
            )

        except Member.DoesNotExist:
            pass

    return render(
        request,
        'sherpaapp/place_search.html',
        {
            'member': member,
            'travels': travels,
            'KAKAO_MAP_API_KEY': settings.KAKAO_MAP_API_KEY,
        }
    )


# 장소 검색 실행
def place_search_search(request):

    query = request.GET.get(
        'query',
        ''
    ).strip()

    login_user = request.session.get(
        'login_ok_user'
    )

    member = None
    travels = Travel.objects.none()

    if login_user:
        try:
            member = Member.objects.get(
                email=login_user
            )

            travels = (
                Travel.objects
                .filter(member=member)
                .order_by('-t_id')
            )

        except Member.DoesNotExist:
            pass

    try:
        places = _search_kakao_places(
            query
        )

    except requests.RequestException:
        places = []

    context = {
        'member': member,
        'travels': travels,
        'places': places,
        'query': query,
        'KAKAO_MAP_API_KEY':
            settings.KAKAO_MAP_API_KEY,
    }

    return render(
        request,
        'sherpaapp/place_search.html',
        context
    )


# 여행 생성
def travel_create(request):
    login_user = request.session.get('login_ok_user')

    # 로그인 확인
    if not login_user:
        return redirect('login')

    try:
        member = Member.objects.get(email=login_user)
    except Member.DoesNotExist:
        return redirect('login')

    # ==========================================
    # 여행 저장
    # ==========================================
    if request.method == 'POST':
        title = request.POST.get('t_title')
        place = request.POST.get('t_place')
        start_str = request.POST.get('t_start')
        end_str = request.POST.get('t_end')
        start_place = request.POST.get('start_place')
        start_addr = request.POST.get('start_addr')
        start_lat = request.POST.get('start_lat') or None
        start_lon = request.POST.get('start_lon') or None
        start_time = request.POST.get('start_time') or None
        plan_dates = request.POST.getlist('plan_date[]')

        stay_names = request.POST.getlist('stay_name[]')
        stay_addrs = request.POST.getlist('stay_addr[]')
        stay_lats = request.POST.getlist('stay_lat[]')
        stay_lons = request.POST.getlist('stay_lon[]')

        arrival_times = request.POST.getlist('stay_arrival_time[]')
        departure_times = request.POST.getlist('day_departure_time[]')

        # 날짜 문자열 -> date 객체
        try:
            start = datetime.strptime(start_str, '%Y-%m-%d').date()
            end = datetime.strptime(end_str, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            categories = Category.objects.all().order_by('c_id')
            return render(
                request,
                'sherpaapp/travel_create.html',
                {
                    'member': member,
                    'categories': categories,
                    'error': '여행 날짜를 올바르게 입력해주세요.',
                }
            )

        # 시작일은 오늘보다 과거일 수 없음
        if start < date.today():
            categories = Category.objects.all().order_by('c_id')
            return render(
                request,
                'sherpaapp/travel_create.html',
                {
                    'member': member,
                    'categories': categories,
                    'error': '여행 시작일은 오늘 이후로 선택해주세요.',
                }
            )

        # 종료일은 시작일과 같거나 이후여야 함
        # 시작일 == 종료일이면 당일 여행으로 허용
        if end < start:
            categories = Category.objects.all().order_by('c_id')
            return render(
                request,
                'sherpaapp/travel_create.html',
                {
                    'member': member,
                    'categories': categories,
                    'error': '여행 종료일은 시작일과 같거나 이후로 선택해주세요.',
                }
            )

        traffic = ','.join(
            value for value in request.POST.getlist('traffic')
            if value
        )

        # ======================================
        # 선택한 여행 컨셉 조회
        #
        # 현재 템플릿(name="categories", value=C_ID)과
        # 예전 템플릿(name="concept", value=C_NAME)을
        # 둘 다 지원한다.
        # ======================================
        category_ids = [
            value
            for value in request.POST.getlist('categories')
            if value
        ]

        concept_names = [
            value.strip()
            for value in request.POST.getlist('concept')
            if value and value.strip()
        ]

        selected_categories = []

        if category_ids:
            selected_categories = list(
                Category.objects.filter(
                    c_id__in=category_ids
                ).order_by('c_id')
            )
        elif concept_names:
            selected_categories = list(
                Category.objects.filter(
                    c_name__in=concept_names
                ).order_by('c_id')
            )

        # 컨셉이 하나도 전달되지 않았으면 자동 추천을 만들 수 없음
        if not selected_categories:
            categories = Category.objects.all().order_by('c_id')
            return render(
                request,
                'sherpaapp/travel_create.html',
                {
                    'member': member,
                    'categories': categories,
                    'error': '여행 컨셉을 1개 이상 선택해주세요.',
                }
            )

        # ======================================
        # TRAVEL 생성
        # ======================================
        travel = Travel.objects.create(
            member=member,
            t_title=title,
            t_place=place,
            t_start=start,
            t_end=end,
            t_day=start,
            t_way=traffic,
            t_budget=100000,
            start_place=start_place,
            start_addr=start_addr,
            start_lat=start_lat,
            start_lon=start_lon,
            start_time=start_time,
        )

        # ======================================
        # 중요: 자동 일정 생성 전에
        # TRAVEL_CATEGORY를 먼저 저장해야 함.
        # generate_schedule()은 이 값을 읽어
        # 추천 장소를 검색한다.
        # ======================================
        for category in selected_categories:
            TravelCategory.objects.get_or_create(
                travel=travel,
                category=category,
            )

        print(
            '자동 일정 생성 카테고리:',
            [category.c_name for category in selected_categories]
        )

        # ==============================================
        # 날짜별 숙소 / 출발시간 저장
        # ==============================================

        for index, plan_date_str in enumerate(plan_dates):

            if not plan_date_str:
                continue

            plan_date = datetime.strptime(
                plan_date_str,
                '%Y-%m-%d'
            ).date()

            stay_name = (
                stay_names[index].strip()
                if index < len(stay_names)
                else ''
            )

            stay_addr = (
                stay_addrs[index].strip()
                if index < len(stay_addrs)
                else ''
            )

            stay_lat = (
                stay_lats[index].strip()
                if index < len(stay_lats)
                else ''
            )

            stay_lon = (
                stay_lons[index].strip()
                if index < len(stay_lons)
                else ''
            )

            arrival_time = (
                arrival_times[index].strip()
                if index < len(arrival_times)
                else ''
            )

            departure_time = (
                departure_times[index].strip()
                if index < len(departure_times)
                else ''
            )

            TravelDayPlan.objects.create(
                travel=travel,
                plan_date=plan_date,

                accommodation_name=stay_name or None,
                accommodation_addr=stay_addr or None,
                accommodation_lat=stay_lat or None,
                accommodation_lon=stay_lon or None,

                arrival_time=arrival_time or None,
                departure_time=departure_time or None,
            )        

        # ======================================
        # 자동 일정 생성
        # ======================================
        generate_schedule(travel)

        return redirect(
            'travel_detail',
            travel_id=travel.t_id
        )

    # ==========================================
    # GET - 카테고리 목록
    # ==========================================
    categories = Category.objects.all().order_by('c_id')

    return render(
        request,
        'sherpaapp/travel_create.html',
        {
            'member': member,
            'categories': categories,
        }
    )

# 여행 목록
def travel_list(request):
    login_user = request.session.get('login_ok_user')
    if not login_user:
        return redirect('login')
    try:
        member = Member.objects.get(email=login_user)
    except Member.DoesNotExist:
        return redirect('login')
    travels = (Travel.objects.filter(member=member).order_by('-t_id'))
    return render(request,'sherpaapp/travel_list.html',{'member':member,'travels':travels})

# 여행 상세
def travel_detail(request, travel_id):
    travel = get_object_or_404(Travel, t_id=travel_id)

    login_user = request.session.get('login_ok_user')
    member = None
    if login_user:
        try:
            member = Member.objects.get(email=login_user)
        except Member.DoesNotExist:
            member = None

    # DAY 단위 일정. 장소 정보는 SchedulePlace를 통해 조회한다.
    schedules = (
        Schedule.objects
        .filter(travel=travel)
        .order_by('s_day', 's_id')
    )

    schedule_places = (
        SchedulePlace.objects
        .filter(schedule__travel=travel)
        .select_related('schedule', 'place')
        .order_by('schedule__s_day', 'visit_order', 'sp_id')
    )

    # 여행 기간별 DAY 정보 생성
    days = []
    travel_days = 0

    if travel.t_start and travel.t_end:
        current_date = travel.t_start
        day_number = 1

        while current_date <= travel.t_end:
            day_schedules = [
                schedule
                for schedule in schedules
                if schedule.s_day == current_date
            ]

            days.append({
                'day_number': day_number,
                'date': current_date,
                'schedules': day_schedules,
            })

            current_date += timedelta(days=1)
            day_number += 1

        travel_days = len(days)

    # 중복 없이 방문 장소 목록 생성
    visited_places = []
    visited_place_ids = set()

    for schedule_place in schedule_places:
        place = schedule_place.place
        if place and place.p_id not in visited_place_ids:
            visited_place_ids.add(place.p_id)
            visited_places.append(place)

    context = {
        'travel': travel,
        'member': member,
        'schedules': schedules,
        'days': days,
        'visited_places': visited_places,
        'travel_days': travel_days,
        'place_count': len(visited_places),
        'KAKAO_MAP_API_KEY': settings.KAKAO_MAP_API_KEY,
    }

    return render(request, 'sherpaapp/travel_detail.html', context)


# ==============================================
# 여행 DAY 상세 AJAX
# ==============================================

def travel_detail_day(
    request,
    travel_id,
    day
):

    travel = get_object_or_404(
        Travel,
        t_id=travel_id
    )


    schedules = (
        Schedule.objects
        .filter(
            travel=travel
        )
        .order_by(
            's_day'
        )
    )


    # 일정 없음
    if not schedules.exists():

        return JsonResponse({
            'success':
                False,

            'message':
                '등록된 여행 일정이 없습니다.'
        })


    # DAY 범위 확인
    if (
        day < 1
        or
        day > schedules.count()
    ):

        return JsonResponse({
            'success':
                False,

            'message':
                '존재하지 않는 DAY입니다.'
        })


    schedule = schedules[
        day - 1
    ]


    # ==========================================
    # 일정 장소
    # ==========================================

    schedule_places = (
        SchedulePlace.objects
        .filter(
            schedule=schedule
        )
        .select_related(
            'place'
        )
        .order_by(
            'visit_order'
        )
    )


    # ==========================================
    # 해당 DAY 비용
    # ==========================================

    pays = (
        Pay.objects
        .filter(
            schedule=schedule
        )
        .select_related(
            'place'
        )
    )


    total_pay = sum(
        pay.pay_pay or 0
        for pay in pays
    )


    # ==========================================
    # 장소 데이터
    # ==========================================

    places = []


    for sp in schedule_places:

        place = sp.place
        place_image = getattr(place, 'p_image', '') or ''

        # 자동 생성 일정처럼 이미지가 비어 있는 장소는
        # DAY 조회 시 카카오 이미지 API로 한 번 조회하고 DB에 캐시한다.
        if not place_image and place.p_name:
            try:
                image_query = (
                    f"{place.p_name} {place.p_addr or ''}"
                ).strip()

                place_image = (
                    _search_kakao_image(image_query)
                    or _search_kakao_image(place.p_name)
                    or ''
                )

                if place_image and hasattr(place, 'p_image'):
                    place.p_image = place_image
                    place.save(update_fields=['p_image'])

            except requests.RequestException:
                place_image = ''

        places.append({

            'sp_id':
                sp.sp_id,

            'visit_order':
                sp.visit_order,

            'arrive_time': (
                sp.arrive_time.strftime(
                    '%H:%M'
                )
                if sp.arrive_time
                else ''
            ),

            'stay_time':
                sp.stay_time,

            'start_time': (
                sp.start_time.strftime(
                    '%H:%M'
                )
                if sp.start_time
                else ''
            ),

            'travel_time':
                sp.travel_time,

            'place_id':
                sp.place.p_id,

            'place_name':
                sp.place.p_name,

            'place_addr':
                sp.place.p_addr,

            'place_kind':
                sp.place.p_kind,

            'place_image':
                place_image,
        })


    # ==========================================
    # 비용 데이터
    # ==========================================

    payments = []


    for pay in pays:

        payments.append({

            'pay_id':
                pay.pay_id,

            'pay_context':
                pay.pay_context,

            'pay_pay':
                pay.pay_pay,

            'place_id': (
                pay.place.p_id
                if pay.place
                else None
            ),

            'place_name': (
                pay.place.p_name
                if pay.place
                else ''
            )
        })


    return JsonResponse({

        'success':
            True,

        'travel_id':
            travel_id,

        'day':
            day,

        'schedule_id':
            schedule.s_id,

        's_day':
            schedule.s_day.strftime(
                '%Y.%m.%d'
            ),

        'places':
            places,

        'pays':
            payments,

        'total_pay':
            total_pay
    })


# ==============================================
# 여행 수정
# ==============================================

def travel_update(
    request,
    travel_id
):

    travel = get_object_or_404(
        Travel,
        t_id=travel_id
    )


    login_user = request.session.get(
        'login_ok_user'
    )


    member = None


    if login_user:

        try:

            member = Member.objects.get(
                email=login_user
            )

        except Member.DoesNotExist:

            member = None


    # ==========================================
    # 수정 저장
    # ==========================================

    if request.method == 'POST':

        travel.t_title = (
            request.POST.get(
                't_title'
            )
        )


        travel.t_place = (
            request.POST.get(
                't_place'
            )
        )


        travel.t_start = (
            request.POST.get(
                't_start'
            )
        )


        travel.t_end = (
            request.POST.get(
                't_end'
            )
        )


        traffic = ','.join(
            request.POST.getlist(
                'traffic'
            )
        )


        travel.t_way = (
            traffic
        )


        travel.t_day = (
            request.POST.get(
                't_start'
            )
        )


        travel.save()


        return redirect(
            'travel_detail',
            travel_id=travel.t_id
        )


    return render(
        request,
        'sherpaapp/travel_update.html',
        {
            'travel':
                travel,

            'member':
                member
        }
    )


# ==============================================
# 여행 삭제
# ==============================================

def travel_delete(
    request,
    travel_id
):

    travel = get_object_or_404(
        Travel,
        t_id=travel_id
    )


    if request.method == 'POST':

        travel.delete()


    return redirect(
        'travel_list'
    )


# ==============================================
# 홈페이지
# ==============================================

def index(request):

    template = loader.get_template(
        'index.html'
    )


    login_user = request.session.get(
        'login_ok_user'
    )


    member = None


    if login_user:

        try:

            member = Member.objects.get(
                email=login_user
            )

        except Member.DoesNotExist:

            member = None


    return HttpResponse(
        template.render(
            {
                'member':
                    member
            },
            request
        )
    )


# ==============================================
# 비용 관리
# ==============================================

def budget(
    request,
    travel_id=None
):

    # ==========================================
    # 로그인 확인
    # ==========================================

    login_user = request.session.get(
        'login_ok_user'
    )


    if not login_user:

        return redirect(
            'login'
        )


    try:

        member = Member.objects.get(
            email=login_user
        )

    except Member.DoesNotExist:

        return redirect(
            'login'
        )


    # ==========================================
    # 현재 회원의 여행 목록
    # ==========================================

    travels = (
        Travel.objects
        .filter(
            member=member
        )
        .order_by(
            '-t_id'
        )
    )


    # ==========================================
    # 선택된 여행
    # ==========================================

    if travel_id:

        travel = get_object_or_404(
            Travel,
            t_id=travel_id,
            member=member
        )

    else:

        travel = travels.first()


    # ==========================================
    # 여행이 하나도 없음
    # ==========================================

    if not travel:

        return render(
            request,
            'sherpaapp/budget.html',
            {
                'member':
                    member,

                'travels':
                    travels,

                'travel':
                    None,

                'pays':
                    [],

                'total_budget':
                    0,

                'used_money':
                    0,

                'remain_money':
                    0,

                'budget_percent':
                    0
            }
        )


    # ==========================================
    # 해당 여행의 비용
    # ==========================================

    pays = (
        Pay.objects
        .filter(
            schedule__travel=travel
        )
        .select_related(
            'schedule',
            'place'
        )
        .order_by(
            '-schedule__s_day',
            '-pay_id'
        )
    )


    # ==========================================
    # 총 예산
    # ==========================================

    total_budget = (
        travel.t_budget
        or 0
    )


    # ==========================================
    # 사용 금액
    # ==========================================

    used_money = sum(
        pay.pay_pay or 0
        for pay in pays
    )


    # ==========================================
    # 남은 금액
    # ==========================================

    remain_money = (
        total_budget
        -
        used_money
    )


    # ==========================================
    # 예산 사용률
    # ==========================================

    if total_budget > 0:

        budget_percent = int(
            used_money
            /
            total_budget
            *
            100
        )

    else:

        budget_percent = 0


    # 진행바 최대 100%
    if budget_percent > 100:

        budget_percent = 100


    return render(
        request,
        'sherpaapp/budget.html',
        {
            'member':
                member,

            'travels':
                travels,

            'travel':
                travel,

            'pays':
                pays,

            'total_budget':
                total_budget,

            'used_money':
                used_money,

            'remain_money':
                remain_money,

            'budget_percent':
                budget_percent
        }
    )


# ==============================================
# 총 예산 수정
# ==============================================

def budget_update_total(
    request,
    travel_id
):

    if request.method != 'POST':

        return redirect(
            'budget_travel',
            travel_id=travel_id
        )


    login_user = request.session.get(
        'login_ok_user'
    )


    if not login_user:

        return redirect(
            'login'
        )


    try:

        member = Member.objects.get(
            email=login_user
        )

    except Member.DoesNotExist:

        return redirect(
            'login'
        )


    travel = get_object_or_404(
        Travel,
        t_id=travel_id,
        member=member
    )


    budget_value = request.POST.get(
        'total_budget'
    )


    try:

        budget_value = int(
            budget_value
        )


        if budget_value < 0:

            raise ValueError


    except (
        TypeError,
        ValueError
    ):

        return HttpResponse("""
            <script>
                alert('올바른 예산 금액을 입력해주세요.');
                history.back();
            </script>
        """)


    travel.t_budget = (
        budget_value
    )


    travel.save(
        update_fields=[
            't_budget'
        ]
    )


    return redirect(
        'budget_travel',
        travel_id=travel.t_id
    )


# ==============================================
# 비용 추가
# ==============================================

def budget_add(
    request,
    travel_id
):

    if request.method != 'POST':

        return redirect(
            'budget_travel',
            travel_id=travel_id
        )


    # ==========================================
    # 로그인 확인
    # ==========================================

    login_user = request.session.get(
        'login_ok_user'
    )


    if not login_user:

        return redirect(
            'login'
        )


    try:

        member = Member.objects.get(
            email=login_user
        )

    except Member.DoesNotExist:

        return redirect(
            'login'
        )


    # ==========================================
    # 여행 확인
    # ==========================================

    travel = get_object_or_404(
        Travel,
        t_id=travel_id,
        member=member
    )


    # ==========================================
    # FORM 값
    # ==========================================

    amount = request.POST.get(
        'expense_amount'
    )


    category = request.POST.get(
        'expense_category',
        ''
    ).strip()


    place_name = request.POST.get(
        'expense_place',
        ''
    ).strip()


    memo = request.POST.get(
        'expense_memo',
        ''
    ).strip()


    expense_date = request.POST.get(
        'expense_date'
    )


    # ==========================================
    # 금액 확인
    # ==========================================

    try:

        amount = int(
            amount
        )


        if amount <= 0:

            raise ValueError


    except (
        TypeError,
        ValueError
    ):

        return HttpResponse("""
            <script>
                alert('올바른 금액을 입력해주세요.');
                history.back();
            </script>
        """)


    # ==========================================
    # 날짜 확인
    # ==========================================

    if not expense_date:

        return HttpResponse("""
            <script>
                alert('날짜를 선택해주세요.');
                history.back();
            </script>
        """)


    # ==========================================
    # 여행 날짜 범위 확인
    # ==========================================

    if (
        travel.t_start
        and
        expense_date < str(
            travel.t_start
        )
    ):

        return HttpResponse("""
            <script>
                alert('여행 시작일 이전 날짜입니다.');
                history.back();
            </script>
        """)


    if (
        travel.t_end
        and
        expense_date > str(
            travel.t_end
        )
    ):

        return HttpResponse("""
            <script>
                alert('여행 종료일 이후 날짜입니다.');
                history.back();
            </script>
        """)


    # ==========================================
    # 해당 날짜 일정 찾기
    # ==========================================

    schedule = (
        Schedule.objects
        .filter(
            travel=travel,
            s_day=expense_date
        )
        .first()
    )


    # 일정이 없으면 생성
    if not schedule:

        schedule = (
            Schedule.objects.create(
                travel=travel,
                s_day=expense_date
            )
        )


    # ==========================================
    # 장소 연결
    # ==========================================

    place = None


    if place_name:

        place = (
            Place.objects
            .filter(
                travel=travel,
                p_name=place_name
            )
            .first()
        )


    # ==========================================
    # 메모 자동 생성
    # ==========================================

    if not memo:

        if (
            place_name
            and
            category
        ):

            memo = (
                f'{place_name} '
                f'{category}'
            )

        elif place_name:

            memo = (
                f'{place_name} 비용'
            )

        elif category:

            memo = (
                category
            )

        else:

            memo = (
                '기타 비용'
            )


    # ==========================================
    # PAY 저장
    # ==========================================

    Pay.objects.create(

        schedule=
            schedule,

        place=
            place,

        pay_context=
            memo,

        pay_pay=
            amount
    )


    return redirect(
        'budget_travel',
        travel_id=travel.t_id
    )


# ==============================================
# 비용 삭제
# ==============================================

def budget_delete(
    request,
    travel_id,
    pay_id
):

    if request.method != 'POST':

        return redirect(
            'budget_travel',
            travel_id=travel_id
        )


    login_user = request.session.get(
        'login_ok_user'
    )


    if not login_user:

        return redirect(
            'login'
        )


    try:

        member = Member.objects.get(
            email=login_user
        )

    except Member.DoesNotExist:

        return redirect(
            'login'
        )


    travel = get_object_or_404(
        Travel,
        t_id=travel_id,
        member=member
    )


    pay = get_object_or_404(
        Pay,
        pay_id=pay_id,
        schedule__travel=travel
    )


    pay.delete()


    return redirect(
        'budget_travel',
        travel_id=travel.t_id
    )


# ==============================================
# 이메일 중복 확인
# ==============================================

def check_email(request):

    email = request.GET.get(
        'email'
    )


    exists = (
        Member.objects
        .filter(
            email=email
        )
        .exists()
    )


    return JsonResponse({
        'is_exists':
            exists
    })


# ==============================================
# 회원가입 처리
# ==============================================

def join_ok(request):

    email = request.POST.get(
        'email'
    )

    pwd = request.POST.get(
        'pwd'
    )

    name = request.POST.get(
        'name'
    )

    nickname = request.POST.get(
        'nickname'
    )


    # 이메일 중복
    if (
        Member.objects
        .filter(
            email=email
        )
        .exists()
    ):

        return HttpResponse("""
            <script>
                alert('이미 사용 중인 이메일입니다.');
                history.back();
            </script>
        """)


    Member.objects.create(
        email=email,
        pwd=pwd,
        name=name,
        nickname=nickname
    )


    return HttpResponse("""
        <script>
            alert('회원가입이 완료되었습니다!');
            location.href = '../login/';
        </script>
    """)


# ==============================================
# 로그인 처리
# ==============================================

def login_ok(request):

    email = request.POST.get(
        'email'
    )

    pwd = request.POST.get(
        'pwd'
    )


    try:

        member = Member.objects.get(
            email=email
        )


        if member.pwd == pwd:

            request.session[
                'login_ok_user'
            ] = member.email


            return HttpResponse("""
                <script>
                    alert('로그인되었습니다.');
                    location.href = '../';
                </script>
            """)


        else:

            return HttpResponse("""
                <script>
                    alert('비밀번호가 틀렸습니다.');
                    history.back();
                </script>
            """)


    except Member.DoesNotExist:

        return HttpResponse("""
            <script>
                alert('존재하지 않는 이메일입니다.');
                history.back();
            </script>
        """)


# ==============================================
# 마이페이지
# ==============================================

def mypage(request):

    login_user = request.session.get(
        'login_ok_user'
    )


    if not login_user:

        return redirect(
            'login'
        )


    try:

        member = Member.objects.get(
            email=login_user
        )

    except Member.DoesNotExist:

        return redirect(
            'login'
        )


    return render(
        request,
        'mypage.html',
        {
            'member':
                member
        }
    )


# ==============================================
# 로그아웃
# ==============================================

def logout(request):

    request.session.flush()


    return HttpResponse("""
        <script>
            alert('로그아웃되었습니다.');
            location.href = '../';
        </script>
    """)


# ==============================================
# ID / PW 찾기
# ==============================================

def idpw(request):

    template = loader.get_template(
        'idpw.html'
    )


    return HttpResponse(
        template.render(
            {},
            request
        )
    )


# ==============================================
# 아이디 찾기
# ==============================================

def id_find(request):

    name = request.POST.get(
        'name'
    )

    nickname = request.POST.get(
        'nickname'
    )


    members = (
        Member.objects
        .filter(
            name=name,
            nickname=nickname
        )
    )


    if members.exists():

        emails = [
            member.email
            for member in members
        ]


        return HttpResponse(f"""
            <script>
                alert('회원님의 아이디는 {", ".join(emails)} 입니다.');
                location.href = '../idpw/';
            </script>
        """)


    return HttpResponse("""
        <script>
            alert('일치하는 회원정보가 없습니다.');
            history.back();
        </script>
    """)


# ==============================================
# 비밀번호 찾기
# ==============================================

def pw_find(request):

    email = request.POST.get(
        'email'
    )

    name = request.POST.get(
        'name'
    )

    new_pwd = request.POST.get(
        'new_pwd'
    )

    new_pwd_check = request.POST.get(
        'new_pwd_check'
    )


    try:

        member = Member.objects.get(
            email=email,
            name=name
        )


        if (
            new_pwd
            !=
            new_pwd_check
        ):

            return HttpResponse("""
                <script>
                    alert('비밀번호가 일치하지 않습니다.');
                    history.back();
                </script>
            """)


        member.pwd = (
            new_pwd
        )


        member.save()


        return HttpResponse("""
            <script>
                alert('비밀번호가 변경되었습니다.');
                location.href = '../login/';
            </script>
        """)


    except Member.DoesNotExist:

        return HttpResponse("""
            <script>
                alert('일치하는 회원정보가 없습니다.');
                history.back();
            </script>
        """)


# ==============================================
# 내정보 수정
# ==============================================

def mypage_edit(request):

    login_user = request.session.get(
        'login_ok_user'
    )


    if not login_user:

        return redirect(
            'login'
        )


    try:

        member = Member.objects.get(
            email=login_user
        )

    except Member.DoesNotExist:

        return redirect(
            'login'
        )


    if request.method == 'POST':

        name = request.POST.get(
            'name'
        )

        nickname = request.POST.get(
            'nickname'
        )


        member.name = (
            name
        )

        member.nickname = (
            nickname
        )


        member.save()


        return redirect(
            'mypage'
        )


    return render(
        request,
        'mypage_edit.html',
        {
            'member': member
        }
    )

def schedule_place_search(request):
    query = request.GET.get('query', '').strip()

    if not query:
        return JsonResponse({'places': []})

    try:
        places = _search_kakao_places(query)
    except requests.RequestException as e:
        return JsonResponse({
            'places': [],
            'message': f'장소 검색 중 오류가 발생했습니다: {e}',
        }, status=502)

    return JsonResponse({'places': places})


# ==============================================
# 방문시간 기준 일정 순서 재정렬
# ==============================================

def reorder_schedule_places_by_time(schedule):
    """같은 DAY의 장소를 방문시간 오름차순으로 정렬하고 visit_order를 다시 부여한다."""

    schedule_places = list(
        SchedulePlace.objects
        .filter(schedule=schedule)
        .order_by('visit_order', 'sp_id')
    )

    # 방문시간이 있는 장소를 먼저, 빠른 시간부터 정렬한다.
    # 동일한 시간은 기존 visit_order와 sp_id 순서를 유지한다.
    schedule_places.sort(
        key=lambda item: (
            item.arrive_time is None,
            item.arrive_time or time.max,
            item.visit_order if item.visit_order is not None else 999999,
            item.sp_id,
        )
    )

    changed_places = []

    for new_order, item in enumerate(schedule_places, start=1):
        if item.visit_order != new_order:
            item.visit_order = new_order
            changed_places.append(item)

    if changed_places:
        SchedulePlace.objects.bulk_update(
            changed_places,
            ['visit_order']
        )

    return schedule_places


# ==============================================
# 교통수단 값 정규화
# ==============================================

def normalize_schedule_transport(transport):
    """TRAVEL.T_WAY 값을 get_kakao_route()에서 쓰는 형식으로 통일한다."""

    transport = (
        str(transport or 'car')
        .split(',')[0]
        .strip()
        .lower()
    )

    transport_map = {
        'car': 'car',
        '자동차': 'car',
        '차': 'car',
        'walk': 'walk',
        '도보': 'walk',
        'bike': 'bike',
        '자전거': 'bike',
        'public_transport': 'public_transport',
        'public transport': 'public_transport',
        'public': 'public_transport',
        '대중교통': 'public_transport',
    }

    return transport_map.get(
        transport,
        transport
    )


# ==============================================
# 두 장소 사이 이동시간 계산
# ==============================================

def get_route_travel_minutes(
    start_place,
    end_place,
    transport,
    fallback_minutes=0,
):
    """
    현재 지도 경로와 동일하게 get_kakao_route()를 사용해
    두 장소 사이 이동시간을 '분' 단위로 반환한다.

    Kakao Mobility Directions의 duration 값은 초 단위이므로
    올림하여 분으로 변환한다.
    """

    if (
        not start_place
        or not end_place
        or start_place.p_lat is None
        or start_place.p_lon is None
        or end_place.p_lat is None
        or end_place.p_lon is None
    ):
        return max(
            int(fallback_minutes or 0),
            0
        )

    try:
        route_data = get_kakao_route(
            start_lat=start_place.p_lat,
            start_lon=start_place.p_lon,
            end_lat=end_place.p_lat,
            end_lon=end_place.p_lon,
            transport=normalize_schedule_transport(
                transport
            )
        )

        if not route_data:
            raise ValueError(
                '경로 데이터가 없습니다.'
            )

        duration_seconds = route_data.get(
            'duration',
            0
        ) or 0

        duration_seconds = float(
            duration_seconds
        )

        if duration_seconds <= 0:
            return max(
                int(fallback_minutes or 0),
                0
            )

        # 초 -> 분, 1초라도 남으면 다음 분으로 올림
        return max(
            int(
                (duration_seconds + 59)
                // 60
            ),
            1
        )

    except Exception as e:
        print(
            '일정 이동시간 재계산 실패:',
            getattr(start_place, 'p_name', ''),
            '->',
            getattr(end_place, 'p_name', ''),
            e
        )

        return max(
            int(fallback_minutes or 0),
            0
        )


# ==============================================
# DAY 일정 시간 연쇄 재계산
# ==============================================

def recalculate_schedule_timeline(
    schedule,
    anchor_sp_id=None,
):
    """
    방문시간 또는 체류시간이 수정되었을 때
    영향받는 뒤쪽 일정의 시간을 연쇄적으로 다시 계산한다.

    계산식:
        현재 장소 출발시간
        + 현재 장소 -> 다음 장소 이동시간
        = 다음 장소 방문시간

        다음 장소 방문시간
        + 다음 장소 체류시간
        = 다음 장소 출발시간

    anchor_sp_id가 있으면 사용자가 직접 수정한 장소의
    방문시간은 그대로 유지하고 그 장소 이후 일정만 밀어낸다.
    """

    schedule_places = list(
        SchedulePlace.objects
        .filter(schedule=schedule)
        .select_related('place')
        .order_by('visit_order', 'sp_id')
    )

    if not schedule_places:
        return []

    # ==========================================
    # 연쇄 계산 시작 위치
    # ==========================================
    anchor_index = 0

    if anchor_sp_id is not None:
        for index, item in enumerate(
            schedule_places
        ):
            if item.sp_id == anchor_sp_id:
                anchor_index = index
                break

    anchor = schedule_places[
        anchor_index
    ]

    # ==========================================
    # 사용자가 수정한 기준 장소 자체 정리
    # ==========================================

    # 첫 장소는 이전 장소가 없으므로 이동시간 0분
    if anchor_index == 0:
        anchor.travel_time = 0

    else:
        previous = schedule_places[
            anchor_index - 1
        ]

        anchor.travel_time = (
            get_route_travel_minutes(
                previous.place,
                anchor.place,
                schedule.travel.t_way,
                anchor.travel_time or 0,
            )
        )

    # 기준 장소의 방문시간은 사용자가 직접 설정한 값을 유지한다.
    # 대신 체류시간에 맞춰 출발시간은 다시 계산한다.
    if anchor.arrive_time:
        anchor_arrival_dt = datetime.combine(
            schedule.s_day,
            anchor.arrive_time
        )

        anchor.start_time = (
            anchor_arrival_dt
            + timedelta(
                minutes=anchor.stay_time or 0
            )
        ).time()

    anchor.save(
        update_fields=[
            'travel_time',
            'start_time',
        ]
    )

    # ==========================================
    # 기준 장소 다음 일정부터 연쇄 재계산
    # ==========================================
    previous = anchor

    for current in schedule_places[
        anchor_index + 1:
    ]:

        travel_minutes = (
            get_route_travel_minutes(
                previous.place,
                current.place,
                schedule.travel.t_way,
                current.travel_time or 0,
            )
        )

        # 앞 장소의 출발시간이 없으면 이후 계산을 진행할 수 없다.
        if not previous.start_time:
            current.travel_time = travel_minutes
            current.save(
                update_fields=[
                    'travel_time'
                ]
            )
            previous = current
            continue

        previous_start_dt = datetime.combine(
            schedule.s_day,
            previous.start_time
        )

        current_arrival_dt = (
            previous_start_dt
            + timedelta(
                minutes=travel_minutes
            )
        )

        current_start_dt = (
            current_arrival_dt
            + timedelta(
                minutes=current.stay_time or 0
            )
        )

        current.travel_time = travel_minutes
        current.arrive_time = current_arrival_dt.time()
        current.start_time = current_start_dt.time()

        current.save(
            update_fields=[
                'travel_time',
                'arrive_time',
                'start_time',
            ]
        )

        previous = current

    return schedule_places


# ==============================================
# 일정 장소 추가
# ==============================================

def schedule_place_add(request):
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': '잘못된 요청입니다.',
        }, status=400)

    schedule_id = request.POST.get('schedule_id')
    travel_id = request.POST.get('travel_id')
    s_day = request.POST.get('s_day')
    place_id = request.POST.get('place_id')
    arrive_time = request.POST.get('arrive_time')
    requested_stay_time = request.POST.get('stay_time')

    # 카카오 검색 결과를 바로 추가하는 경우 넘어오는 값
    place_name = request.POST.get('place_name', '').strip()
    place_addr = request.POST.get('place_addr', '').strip()
    place_kind = request.POST.get('place_kind', '').strip()
    place_lat = request.POST.get('place_lat') or None
    place_lon = request.POST.get('place_lon') or None
    place_image = request.POST.get('place_image') or None

    # schedule_id가 있으면 기존 일정을 사용한다.
    if schedule_id:
        schedule = get_object_or_404(Schedule, s_id=schedule_id)
        travel = schedule.travel
    else:
        if not travel_id or not s_day:
            return JsonResponse({
                'success': False,
                'message': '일정 정보가 없습니다.',
            }, status=400)

        travel = get_object_or_404(Travel, t_id=travel_id)
        schedule = (
            Schedule.objects
            .filter(travel=travel, s_day=s_day)
            .order_by('s_id')
            .first()
        )

        if not schedule:
            schedule = Schedule.objects.create(
                travel=travel,
                s_day=s_day,
            )

    # place_id가 있으면 기존 PLACE를 사용한다.
    if place_id:
        place = get_object_or_404(Place, p_id=place_id)
    else:
        if not place_name:
            return JsonResponse({
                'success': False,
                'message': '장소 정보가 없습니다.',
            }, status=400)

        place = (
            Place.objects
            .filter(
                travel=travel,
                p_name=place_name,
                p_addr=place_addr,
            )
            .first()
        )

        if not place:
            place = Place.objects.create(
                travel=travel,
                p_name=place_name,
                p_addr=place_addr,
                p_kind=place_kind,
                p_lat=place_lat,
                p_lon=place_lon,
                p_image=place_image,
            )

    # 이미지가 비어 있으면 API를 통해 자동 보완하고 DB에 저장한다.
    if hasattr(place, 'p_image') and not (place.p_image or ''):
        try:
            image_query = f"{place.p_name} {place.p_addr or ''}".strip()
            auto_image = (
                place_image
                or _search_kakao_image(image_query)
                or _search_kakao_image(place.p_name)
            )

            if auto_image:
                place.p_image = auto_image
                place.save(update_fields=['p_image'])
        except requests.RequestException:
            pass

    # 같은 장소가 같은 DAY에 이미 들어가 있으면 중복 추가 방지
    if SchedulePlace.objects.filter(schedule=schedule, place=place).exists():
        return JsonResponse({
            'success': False,
            'message': '이미 일정에 추가된 장소입니다.',
        }, status=400)

    last_place = (
        SchedulePlace.objects
        .filter(schedule=schedule)
        .order_by('-visit_order', '-sp_id')
        .first()
    )

    visit_order = (
        last_place.visit_order + 1
        if last_place
        else 1
    )

    # 방문시간을 따로 넘기지 않아도 추가 가능하게 한다.
    # 기존 일정이 있으면 마지막 장소 출발시간, 없으면 10:00을 기본값으로 사용한다.
    if arrive_time:
        try:
            arrival = datetime.strptime(
                arrive_time,
                '%H:%M'
            ).time()
        except ValueError:
            return JsonResponse({
                'success': False,
                'message': '방문시간 형식이 올바르지 않습니다.',
            }, status=400)
    elif last_place and last_place.start_time:
        arrival = last_place.start_time
    else:
        arrival = time(10, 0)

    # 체류시간은 직접 전달된 값이 있으면 사용하고,
    # 없으면 장소 종류별 기본값을 적용한다.
    if requested_stay_time not in (None, ''):
        try:
            stay_time = int(requested_stay_time)
            if stay_time <= 0 or stay_time > 24 * 60:
                raise ValueError
        except (TypeError, ValueError):
            return JsonResponse({
                'success': False,
                'message': '체류시간은 1~1440분 사이로 설정해주세요.',
            }, status=400)
    else:
        kind = place.p_kind or ''

        if '쇼핑' in kind:
            stay_time = 120
        elif '역사' in kind or '문화' in kind:
            stay_time = 90
        elif '랜드마크' in kind:
            stay_time = 60
        elif '공원' in kind:
            stay_time = 90
        elif '카페' in kind:
            stay_time = 60
        elif '음식' in kind or '식당' in kind:
            stay_time = 90
        elif '자연' in kind or '바다' in kind:
            stay_time = 120
        elif '관광' in kind:
            stay_time = 120
        else:
            stay_time = 60

    arrival_datetime = datetime.combine(
        schedule.s_day,
        arrival
    )

    start_time = (
        arrival_datetime
        + timedelta(minutes=stay_time)
    ).time()

    schedule_place = SchedulePlace.objects.create(
        schedule=schedule,
        place=place,
        visit_order=visit_order,
        stay_time=stay_time,
        arrive_time=arrival,
        start_time=start_time,
    )

    # 새 장소도 방문시간 기준으로 전체 DAY 순서를 다시 정렬한다.
    reorder_schedule_places_by_time(schedule)

    # 새 장소를 기준으로 이후 일정의 이동시간 / 방문시간 / 출발시간을
    # 연쇄적으로 다시 계산한다.
    recalculate_schedule_timeline(
        schedule,
        anchor_sp_id=schedule_place.sp_id
    )

    schedule_place.refresh_from_db(
        fields=[
            'visit_order',
            'travel_time',
            'arrive_time',
            'start_time',
        ]
    )

    return JsonResponse({
        'success': True,
        'message': f'{place.p_name} 장소가 일정에 추가되었습니다.',
        'schedule_id': schedule.s_id,
        'sp_id': schedule_place.sp_id,
        'visit_order': schedule_place.visit_order,
        'place_id': place.p_id,
        'place_name': place.p_name,
        'address': place.p_addr,
        'kind': place.p_kind,
        'place_image': getattr(place, 'p_image', '') or '',
        'arrive_time': (
            schedule_place.arrive_time.strftime('%H:%M')
            if schedule_place.arrive_time
            else ''
        ),
        'stay_time': schedule_place.stay_time,
        'travel_time': schedule_place.travel_time,
        'start_time': (
            schedule_place.start_time.strftime('%H:%M')
            if schedule_place.start_time
            else ''
        ),
    })


# ==============================================
# 일정 장소 삭제
# ==============================================

def schedule_place_delete(request):

    if request.method != 'POST':

        return JsonResponse(
            {
                'success':
                    False,

                'message':
                    '잘못된 요청입니다.'
            },
            status=400
        )


    sp_id = request.POST.get(
        'sp_id'
    )


    if not sp_id:

        return JsonResponse(
            {
                'success':
                    False,

                'message':
                    '삭제할 일정 정보가 없습니다.'
            },
            status=400
        )


    schedule_place = (
        get_object_or_404(
            SchedulePlace,
            sp_id=sp_id
        )
    )


    schedule = (
        schedule_place.schedule
    )


    schedule_place.delete()


    # ==========================================
    # 삭제 후 순서 / 이동시간 / 전체 타임라인 재계산
    # ==========================================

    reorder_schedule_places_by_time(
        schedule
    )

    recalculate_schedule_timeline(
        schedule
    )


    return JsonResponse({
        'success':
            True,

        'message':
            '일정이 삭제되었습니다.'
    })


# ==============================================
# 일정 방문시간 수정
# ==============================================

def schedule_place_time_update(request):

    if request.method != 'POST':
        return JsonResponse(
            {
                'success': False,
                'message': '잘못된 요청입니다.'
            },
            status=400
        )

    sp_id = request.POST.get('sp_id')
    arrive_time = request.POST.get('arrive_time')
    stay_time_value = request.POST.get('stay_time')

    if not sp_id:
        return JsonResponse(
            {
                'success': False,
                'message': '일정 정보가 없습니다.'
            },
            status=400
        )

    if arrive_time in (None, '') and stay_time_value in (None, ''):
        return JsonResponse(
            {
                'success': False,
                'message': '수정할 시간 정보가 없습니다.'
            },
            status=400
        )

    schedule_place = get_object_or_404(
        SchedulePlace,
        sp_id=sp_id
    )

    schedule = schedule_place.schedule
    update_fields = []
    arrival_changed = False

    # ==========================================
    # 방문시간 수정
    # ==========================================
    if arrive_time not in (None, ''):
        try:
            arrival = datetime.strptime(
                arrive_time,
                '%H:%M'
            ).time()
        except ValueError:
            return JsonResponse(
                {
                    'success': False,
                    'message': '방문시간 형식이 올바르지 않습니다.'
                },
                status=400
            )

        if schedule_place.arrive_time != arrival:
            arrival_changed = True

        schedule_place.arrive_time = arrival
        update_fields.append('arrive_time')

    # ==========================================
    # 체류시간 수정
    # ==========================================
    if stay_time_value not in (None, ''):
        try:
            stay_time = int(stay_time_value)

            if stay_time <= 0 or stay_time > 24 * 60:
                raise ValueError

        except (TypeError, ValueError):
            return JsonResponse(
                {
                    'success': False,
                    'message': '체류시간은 1~1440분 사이로 설정해주세요.'
                },
                status=400
            )

        schedule_place.stay_time = stay_time
        update_fields.append('stay_time')

    # ==========================================
    # 출발시간 재계산
    # 방문시간 + 체류시간
    # ==========================================
    if schedule_place.arrive_time:
        arrival_datetime = datetime.combine(
            schedule.s_day,
            schedule_place.arrive_time
        )

        start_datetime = (
            arrival_datetime
            + timedelta(
                minutes=(schedule_place.stay_time or 0)
            )
        )

        schedule_place.start_time = start_datetime.time()
        update_fields.append('start_time')

    schedule_place.save(
        update_fields=list(dict.fromkeys(update_fields))
    )

    # ==========================================
    # 방문시간이 변경되면 같은 DAY 전체를 시간순 재정렬
    # ==========================================
    if arrival_changed:
        reorder_schedule_places_by_time(
            schedule
        )

    # ==========================================
    # 수정한 장소를 기준으로 뒤쪽 일정 연쇄 재계산
    #
    # - 현재 장소 출발시간 = 방문시간 + 체류시간
    # - 다음 장소 이동시간 = 새 방문순서 기준 실제 경로시간
    # - 다음 장소 방문시간 = 이전 출발시간 + 이동시간
    # - 다음 장소 출발시간 = 방문시간 + 체류시간
    # ==========================================
    recalculate_schedule_timeline(
        schedule,
        anchor_sp_id=schedule_place.sp_id
    )

    schedule_place.refresh_from_db(
        fields=[
            'visit_order',
            'travel_time',
            'arrive_time',
            'stay_time',
            'start_time',
        ]
    )

    return JsonResponse({
        'success': True,
        'message': '일정 시간이 변경되었습니다.',
        'visit_order': schedule_place.visit_order,
        'arrive_time': (
            schedule_place.arrive_time.strftime('%H:%M')
            if schedule_place.arrive_time
            else ''
        ),
        'stay_time': schedule_place.stay_time,
        'travel_time': schedule_place.travel_time,
        'start_time': (
            schedule_place.start_time.strftime('%H:%M')
            if schedule_place.start_time
            else ''
        )
    })


# ==============================================
# 경로 조회
# ==============================================

def travel_route(
    request,
    schedule_id
):

    schedule = get_object_or_404(
        Schedule,
        s_id=schedule_id
    )


    schedule_places = list(
        SchedulePlace.objects
        .filter(
            schedule=schedule
        )
        .select_related(
            'place'
        )
        .order_by(
            'visit_order'
        )
    )


    # ==========================================
    # 장소가 2개 미만이면 경로 없음
    # ==========================================

    if len(
        schedule_places
    ) < 2:

        return JsonResponse({
            'success':
                True,

            'message':
                '경로를 계산할 장소가 부족합니다.',

            'points':
                [],

            'routes':
                [],

            'distance':
                0,

            'duration':
                0
        })


    # ==========================================
    # 교통수단
    # ==========================================

    transport = request.GET.get(
        'transport'
    )


    if not transport:

        transport = (
            schedule.travel.t_way
            or 'car'
        )


    # 여러 교통수단 저장돼 있으면 첫 번째 사용
    transport = (
        str(transport)
        .split(',')[0]
        .strip()
        .lower()
    )


    # ==========================================
    # 한글/영문 통일
    # ==========================================

    transport_map = {

        'car':
            'car',

        '자동차':
            'car',

        'walk':
            'walk',

        '도보':
            'walk',

        'bike':
            'bike',

        '자전거':
            'bike',

        'public_transport':
            'public_transport',

        'public transport':
            'public_transport',

        '대중교통':
            'public_transport'
    }


    transport = (
        transport_map.get(
            transport,
            transport
        )
    )


    routes = []

    all_points = []

    total_distance = 0

    total_duration = 0


    # ==========================================
    # 장소 → 다음 장소 경로
    # ==========================================

    for index in range(
        len(schedule_places) - 1
    ):

        start_sp = (
            schedule_places[index]
        )

        end_sp = (
            schedule_places[index + 1]
        )


        start_place = (
            start_sp.place
        )

        end_place = (
            end_sp.place
        )


        # 좌표 없으면 건너뜀
        if (
            start_place.p_lat is None
            or
            start_place.p_lon is None
            or
            end_place.p_lat is None
            or
            end_place.p_lon is None
        ):

            continue


        try:

            route_data = get_kakao_route(

                start_lat=
                    start_place.p_lat,

                start_lon=
                    start_place.p_lon,

                end_lat=
                    end_place.p_lat,

                end_lon=
                    end_place.p_lon,

                transport=
                    transport
            )


        except Exception as e:

            routes.append({

                'from_place':
                    start_place.p_name,

                'to_place':
                    end_place.p_name,

                'success':
                    False,

                'message':
                    str(e),

                'points':
                    [],

                'distance':
                    0,

                'duration':
                    0
            })

            continue


        if not route_data:

            routes.append({

                'from_place':
                    start_place.p_name,

                'to_place':
                    end_place.p_name,

                'success':
                    False,

                'points':
                    [],

                'distance':
                    0,

                'duration':
                    0
            })

            continue


        points = route_data.get(
            'points',
            []
        )


        distance = route_data.get(
            'distance',
            0
        ) or 0


        duration = route_data.get(
            'duration',
            0
        ) or 0


        all_points.extend(
            points
        )


        total_distance += (
            distance
        )


        total_duration += (
            duration
        )


        routes.append({

            'from_place':
                start_place.p_name,

            'to_place':
                end_place.p_name,

            'success':
                True,

            'points':
                points,

            'distance':
                distance,

            'duration':
                duration
        })


    places = []
    for sp in schedule_places:
        place = sp.place
        places.append({
            'id': place.p_id,
            'name': place.p_name,
            'address': place.p_addr,
            'lat': float(place.p_lat) if place.p_lat is not None else None,
            'lon': float(place.p_lon) if place.p_lon is not None else None,
            'order': sp.visit_order,
            'arrival_time': (
                sp.arrive_time.strftime('%H:%M')
                if sp.arrive_time
                else None
            ),
            'stay_time': sp.stay_time,
        })

    return JsonResponse({
        'success': True,
        'transport': transport,
        'schedule_id': schedule.s_id,
        's_day': schedule.s_day.strftime('%Y.%m.%d'),
        'places': places,

        # 현재 구조에서 사용하는 이름
        'points': all_points,
        'routes': routes,
        'distance': total_distance,
        'duration': total_duration,

        # 기존 JS와의 호환을 위한 이름
        'route_points': all_points,
        'total_distance': total_distance,
        'total_duration': total_duration,
    })
