from datetime import datetime, timedelta, time, date
import hashlib
import json
import logging
import re
from decimal import Decimal
import requests
from django.conf import settings
from django.core.cache import cache
from django.db.models import Prefetch
from django.http import HttpResponse, JsonResponse
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.template import loader
from django.urls import reverse
from django.views.decorators.http import require_POST
from .models import Member
from .models import Travel
from .models import Place
from .models import Schedule
from .models import Pay
from .models import Category
from .models import SchedulePlace
from .services.schedule_service import (
    generate_schedule,
    get_day_start_time,
    get_travel_day_plans,
    resolve_effective_accommodations,
)
from .services import chat_service
from .services.route_service import get_kakao_route, get_travel_time
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

# ==============================================
# 장소 검색
# ==============================================

def place_search(request):

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

    # 현재 로그인한 회원의 여행 목록만 조회
    travels = (
        Travel.objects
        .filter(
            member=member
        )
        .order_by(
            '-t_id'
        )
    )

    return render(
        request,
        'sherpaapp/place_search.html',
        {
            'member': member,
            'travels': travels,
            'places': [],
            'query': '',
            'KAKAO_MAP_API_KEY':
                settings.KAKAO_MAP_API_KEY,
        }
    )


# ==============================================
# 장소 검색 실행
# ==============================================

def place_search_search(request):

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

    # 검색 후 페이지가 다시 렌더링되어도
    # 일정 추가 모달의 여행 목록이 유지되도록 다시 조회
    travels = (
        Travel.objects
        .filter(
            member=member
        )
        .order_by(
            '-t_id'
        )
    )

    query = request.GET.get(
        'query',
        ''
    ).strip()

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

    # 기본은 AI 대화 방식, ?mode=manual 이면 예전 직접 선택 방식
    mode = 'manual' if request.GET.get('mode') == 'manual' else 'chat'

    return render(
        request,
        'sherpaapp/travel_create.html',
        {
            'member': member,
            'categories': categories,
            'mode': mode,
            **_parse_plan_query(request),
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

# 일정 관리 (사이드바 메뉴)
# 가장 최근 여행의 일정으로 보내고, 여행이 하나도 없으면 안내 카드를 보여준다.
def schedule_manage(request):
    login_user = request.session.get('login_ok_user')
    if not login_user:
        return redirect('login')
    try:
        member = Member.objects.get(email=login_user)
    except Member.DoesNotExist:
        return redirect('login')

    travel = Travel.objects.filter(member=member).order_by('-t_id').first()
    if travel:
        return redirect('travel_detail', travel_id=travel.t_id)

    return render(request, 'sherpaapp/schedule_empty.html', {'member': member})

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

        # ODsay Basic(Web) 키. 브라우저에서 직접 ODsay를 호출하므로
        # PythonAnywhere 무료 계정의 outbound allowlist 영향을 받지 않는다.
        # settings.py에 ODSAY_WEB_API_KEY를 추가하면 활성화된다.
        'ODSAY_WEB_API_KEY': getattr(
            settings,
            'ODSAY_WEB_API_KEY',
            ''
        ),
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

# ==============================================
# 메인 - 일정 시작 폼 / 최근 일정 미리보기 도우미
# ==============================================

_BUDGET_STYLE_LABELS = {
    'value': '가성비',
    'premium': '비싸도 괜찮음',
}


def _parse_plan_query(request):
    """메인 화면의 입력(q, budget_style)을 여행 만들기 화면의 미리 채울 값으로 바꾼다.

    - q 전체는 여행 제목 후보로 쓴다.
    - '강릉 1박 2일' 처럼 'N박 M일' 앞의 단어가 있으면 여행 지역 후보로 쓴다.
    """
    query = (request.GET.get('q') or '').strip()[:100]
    style = request.GET.get('budget_style') or ''

    place = ''
    match = re.search(r'([가-힣A-Za-z]+)\s*\d+\s*박\s*\d+\s*일', query)
    if match:
        place = match.group(1)

    return {
        'prefill_title': query,
        'prefill_place': place,
        'prefill_budget_style': _BUDGET_STYLE_LABELS.get(style, ''),
        'prefill_budget_code': style if style in _BUDGET_STYLE_LABELS else '',
    }


def _format_stay_time(minutes):
    if not minutes:
        return ''

    hours, mins = divmod(int(minutes), 60)

    if hours and mins:
        return f'{hours}시간 {mins}분'
    if hours:
        return f'{hours}시간'
    return f'{mins}분'


def _build_recent_travel(travel):
    """메인 화면 '최근 만든 일정' 카드용 데이터 (최대 3일, 하루 3곳)."""
    days = []

    if travel.t_start and travel.t_end and travel.t_end >= travel.t_start:
        day_count = (travel.t_end - travel.t_start).days + 1

        for offset in range(min(day_count, 3)):
            day = travel.t_start + timedelta(days=offset)

            schedule_places = (
                SchedulePlace.objects
                .filter(schedule__travel=travel, schedule__s_day=day)
                .select_related('place')
                .order_by('visit_order', 'sp_id')[:3]
            )

            items = []

            for sp in schedule_places:
                visit_time = sp.arrive_time or sp.start_time
                detail = [
                    part for part in (
                        sp.place.p_kind,
                        _format_stay_time(sp.stay_time),
                    ) if part
                ]

                items.append({
                    'time': visit_time.strftime('%H:%M') if visit_time else '',
                    'name': sp.place.p_name,
                    'detail': ' · '.join(detail),
                })

            days.append({
                'number': offset + 1,
                'items': items,
            })

    return {
        'id': travel.t_id,
        'title': travel.t_title or travel.t_place or '내 여행',
        'place': travel.t_place or '',
        'start': travel.t_start,
        'end': travel.t_end,
        'days': days,
    }


def index(request):

    template = loader.get_template(
        'index.html'
    )


    login_user = request.session.get(
        'login_ok_user'
    )


    member = None
    recent_travel = None


    if login_user:

        try:

            member = Member.objects.get(
                email=login_user
            )

        except Member.DoesNotExist:

            member = None


    # 로그인한 회원의 가장 최근 여행
    if member:

        latest_travel = (
            Travel.objects
            .filter(member=member)
            .order_by('-t_id')
            .first()
        )

        if latest_travel:
            recent_travel = _build_recent_travel(latest_travel)


    return HttpResponse(
        template.render(
            {
                'member':
                    member,
                'recent_travel':
                    recent_travel,
            },
            request
        )
    )


# ==============================================
# 비용 관리
# ==============================================

# ==============================================
# 비용 관리 화면용 계산 (분류 / 날짜별 묶음 / 그래프)
# ==============================================

# (이름, 키, 색, 아이콘, 키워드)
BUDGET_CATEGORIES = [
    ('관광지', 'sight', '#2d6cdf', 'landmark',
     ('관광', '입장', '체험', '티켓', '문화', '역사', '공원', '박물관', '미술관')),
    ('식비', 'food', '#f0a03c', 'utensils',
     ('음식', '식당', '카페', '맛집', '점심', '저녁', '아침', '커피', '간식')),
    ('교통', 'move', '#7a8cf0', 'bus',
     ('이동', '버스', '택시', '지하철', '기차', 'KTX', '렌트', '주유', '주차', '항공', '톨게이트')),
    ('숙박', 'stay', '#2fb59b', 'bed',
     ('숙소', '호텔', '게스트', '펜션', '리조트', '모텔')),
    ('쇼핑', 'shop', '#e46b9b', 'bag',
     ('기념품', '마트')),
    ('기타', 'etc', '#9aa5b8', 'card', ()),
]

# 키워드로 찾을 때의 우선순위 (넓게 걸리는 '관광지'는 마지막)
_BUDGET_KEYWORD_ORDER = ('stay', 'move', 'food', 'shop', 'sight')


def _budget_category(pay):
    """비용 한 건이 어떤 분류인지 알아낸다. 모르면 '기타'."""
    text = pay.pay_context or ''
    by_key = {c[1]: c for c in BUDGET_CATEGORIES}

    # 1) 비용 추가 화면에서 고른 항목 이름이 그대로 들어 있는 경우
    for cat in BUDGET_CATEGORIES[:-1]:
        if cat[0] in text:
            return cat

    # 2) 내용이나 장소 종류에 단서가 있는 경우
    kind = pay.place.p_kind if pay.place_id and pay.place and pay.place.p_kind else ''

    for source in (text, kind):
        for key in _BUDGET_KEYWORD_ORDER:
            if any(word in source for word in by_key[key][4]):
                return by_key[key]

    return by_key['etc']


def _pct(part, whole):
    return '%.2f' % (part / whole * 100) if whole > 0 else '0.00'


def _budget_overview(travel, pays, total_budget, used_money):
    """비용 관리 화면에 필요한 묶음 데이터를 만든다."""
    by_cat = {}

    for cat in BUDGET_CATEGORIES:
        by_cat[cat[1]] = {
            'name': cat[0], 'key': cat[1], 'color': cat[2], 'icon': cat[3],
            'amount': 0, 'count': 0,
        }

    groups = {}
    ordered = sorted(
        pays,
        key=lambda p: (p.schedule.s_day if p.schedule and p.schedule.s_day else date.max, p.pay_id)
    )

    for index, pay in enumerate(ordered):
        cat = _budget_category(pay)
        amount = pay.pay_pay or 0
        by_cat[cat[1]]['amount'] += amount
        by_cat[cat[1]]['count'] += 1

        day = pay.schedule.s_day if pay.schedule and pay.schedule.s_day else None
        group = groups.get(day)

        if group is None:
            day_no = ((day - travel.t_start).days + 1) if (day and travel.t_start) else None
            group = groups[day] = {
                'day': day, 'day_no': day_no, 'total': 0, 'rows': [],
            }

        group['total'] += amount
        group['rows'].append({
            'pay': pay,
            'index': index,
            'amount': amount,
            'place': pay.place.p_name if pay.place_id and pay.place else (travel.t_place or ''),
            'category': by_cat[cat[1]],
        })

    categories = [c for c in by_cat.values() if c['amount'] > 0]
    categories.sort(key=lambda c: -c['amount'])

    for c in categories:
        c['percent'] = round(c['amount'] / used_money * 100) if used_money > 0 else 0

    # 한 줄 그래프: 예산을 넘으면 사용 금액 전체가 100%, 아니면 총 예산이 100%
    whole = max(total_budget, used_money)
    segments = [
        {'name': c['name'], 'color': c['color'], 'amount': c['amount'], 'width': _pct(c['amount'], whole)}
        for c in categories
    ]
    is_over = total_budget > 0 and used_money > total_budget

    return {
        'day_groups': list(groups.values()),
        'categories': categories,
        'bar_segments': segments,
        'is_over': is_over,
        'over_money': max(used_money - total_budget, 0),
        'total_marker': _pct(total_budget, whole) if is_over else None,
        'top_category': categories[0] if categories else None,
        'pay_count': len(ordered),
    }


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
                budget_percent,

            **_budget_overview(
                travel,
                pays,
                total_budget,
                used_money
            )
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
# 비용 금액 수정
# ==============================================

def budget_update_pay(
    request,
    travel_id,
    pay_id
):

    if request.method != 'POST':

        return JsonResponse(
            {'ok': False, 'error': '잘못된 요청이에요.'},
            status=405
        )


    login_user = request.session.get(
        'login_ok_user'
    )

    if not login_user:

        return JsonResponse(
            {'ok': False, 'error': '로그인이 필요해요.', 'login': True},
            status=401
        )


    try:

        member = Member.objects.get(
            email=login_user
        )

    except Member.DoesNotExist:

        return JsonResponse(
            {'ok': False, 'error': '로그인이 필요해요.', 'login': True},
            status=401
        )


    # 내 여행의 비용만 고칠 수 있다
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


    raw_amount = (
        request.POST.get('amount', '')
        .replace(',', '')
        .strip()
    )

    try:

        amount = int(raw_amount)

        if amount <= 0 or amount > 2000000000:

            raise ValueError

    except ValueError:

        return JsonResponse(
            {'ok': False, 'error': '1원 이상의 올바른 금액을 입력해 주세요.'},
            status=400
        )


    pay.pay_pay = amount
    pay.save(update_fields=['pay_pay'])


    return JsonResponse({
        'ok': True,
        'amount': amount,
    })


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

# ==============================================
# 회원탈퇴
# ==============================================

def member_delete(request):

    # POST 요청만 허용
    if request.method != 'POST':

        return redirect(
            'mypage'
        )


    # 로그인 확인
    login_user = request.session.get(
        'login_ok_user'
    )


    if not login_user:

        return redirect(
            'login'
        )


    # 현재 회원 조회
    try:

        member = Member.objects.get(
            email=login_user
        )

    except Member.DoesNotExist:

        request.session.flush()

        return redirect(
            'login'
        )


    # 입력한 비밀번호
    password = request.POST.get(
        'password',
        ''
    )


    # 비밀번호 확인
    if member.pwd != password:

        return HttpResponse("""
            <script>
                alert('비밀번호가 일치하지 않습니다.');
                history.back();
            </script>
        """)


    # 회원 삭제
    member.delete()


    # 로그인 세션 삭제
    request.session.flush()


    return HttpResponse("""
        <script>
            alert('회원탈퇴가 완료되었습니다.');
            location.href = '../';
        </script>
    """)

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
# 좌표 기준 이동시간 계산
# ==============================================

def get_route_travel_minutes_by_coords(
    start_lat,
    start_lon,
    end_lat,
    end_lon,
    transport,
    fallback_minutes=0,
):
    """
    첫 번째 일정처럼 PLACE 객체가 없는 출발지(S)에서도
    동일한 경로시간 계산을 사용하기 위한 함수.
    """

    try:
        if (
            start_lat is None
            or start_lon is None
            or end_lat is None
            or end_lon is None
        ):
            raise ValueError(
                '경로 좌표가 없습니다.'
            )

        normalized_transport = (
            normalize_schedule_transport(
                transport
            )
        )

        # 서버에서 ODsay Web API를 호출하지 않으므로
        # public_transport는 저장된 계획시간을 우선 사용한다.
        if normalized_transport == 'public_transport':
            return max(
                int(fallback_minutes or 0),
                0
            )

        route_data = get_kakao_route(
            start_lat=start_lat,
            start_lon=start_lon,
            end_lat=end_lat,
            end_lon=end_lon,
            transport=normalized_transport,
        )

        if not route_data:
            raise ValueError(
                '경로 데이터가 없습니다.'
            )

        duration_seconds = float(
            route_data.get(
                'duration',
                0
            )
            or 0
        )

        if duration_seconds <= 0:
            raise ValueError(
                '이동시간이 없습니다.'
            )

        return max(
            int(
                (duration_seconds + 59)
                // 60
            ),
            1
        )

    except Exception as e:
        print(
            '좌표 기준 일정 이동시간 계산 실패:',
            e
        )

        return max(
            int(fallback_minutes or 0),
            0
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

    return get_route_travel_minutes_by_coords(
        start_place.p_lat,
        start_place.p_lon,
        end_place.p_lat,
        end_place.p_lon,
        transport,
        fallback_minutes,
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

    # 첫 장소도 DAY 시작점(S) -> 1번 장소의 이동시간을 반영한다.
    if anchor_index == 0:
        start_point = _build_route_start_point(
            schedule.travel,
            schedule,
        )

        anchor.travel_time = (
            get_route_travel_minutes_by_coords(
                (
                    start_point.get('lat')
                    if start_point
                    else None
                ),
                (
                    start_point.get('lon')
                    if start_point
                    else None
                ),
                anchor.place.p_lat,
                anchor.place.p_lon,
                schedule.travel.t_way,
                anchor.travel_time or 0,
            )
        )

        # 삭제/전체 재계산(anchor_sp_id=None)일 때는
        # 시작지 출발시각 + 실제 이동시간으로 첫 일정도 다시 맞춘다.
        if (
            anchor_sp_id is None
            and start_point
            and start_point.get('departure_time')
        ):
            try:
                start_departure = datetime.strptime(
                    start_point['departure_time'],
                    '%H:%M'
                ).time()

                anchor_arrival_dt = (
                    datetime.combine(
                        schedule.s_day,
                        start_departure,
                    )
                    + timedelta(
                        minutes=anchor.travel_time
                    )
                )

                anchor.arrive_time = (
                    anchor_arrival_dt.time()
                )

            except (TypeError, ValueError):
                pass

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
            'arrive_time',
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

def _build_route_start_point(
    travel,
    schedule,
):
    """
    DAY 1은 Travel.start_*,
    DAY 2 이후는 전날의 유효 숙소를 출발점으로 사용한다.
    """

    schedule_date = schedule.s_day

    # DAY 1 여부는 날짜 타입 비교가 아니라 실제 첫 Schedule 기준으로 판단한다.
    # (SQLite/MySQL, 문자열/date 타입 차이 때문에 start_point가 누락되는 문제 방지)
    first_schedule = (
        Schedule.objects
        .filter(travel=travel)
        .order_by('s_day', 's_id')
        .first()
    )

    is_first_day = (
        first_schedule is not None
        and first_schedule.s_id == schedule.s_id
    )

    if is_first_day:

        if (
            travel.start_lat is None
            or travel.start_lon is None
        ):
            return None

        return {
            'name':
                travel.start_place
                or '출발지',

            'address':
                travel.start_addr
                or travel.start_place
                or '',

            'lat':
                float(
                    travel.start_lat
                ),

            'lon':
                float(
                    travel.start_lon
                ),

            'departure_time': (
                travel.start_time.strftime('%H:%M')
                if travel.start_time
                else '09:00'
            ),

            'marker':
                'S',
        }


    # DAY 2 이후
    previous_date = (
        schedule_date
        -
        timedelta(days=1)
    )

    # 기존 Travel 숙소를 fallback으로 둔다.
    current_name = (
        travel.accommodation
        or None
    )

    current_addr = (
        travel.accommodation
        or ''
    )

    current_lat = (
        travel.accommodation_lat
    )

    current_lon = (
        travel.accommodation_lon
    )


    # 이전 날짜까지 TravelDayPlan을 순서대로 읽어서
    # 마지막으로 입력된 숙소를 유효 숙소로 사용한다.
    previous_plans = (
        TravelDayPlan.objects
        .filter(
            travel=travel,
            plan_date__lte=previous_date
        )
        .order_by(
            'plan_date',
            'tdp_id'
        )
    )


    for plan in previous_plans:

        if (
            plan.accommodation_name
            and
            plan.accommodation_lat is not None
            and
            plan.accommodation_lon is not None
        ):

            current_name = (
                plan.accommodation_name
            )

            current_addr = (
                plan.accommodation_addr
                or plan.accommodation_name
            )

            current_lat = (
                plan.accommodation_lat
            )

            current_lon = (
                plan.accommodation_lon
            )


    if (
        not current_name
        or current_lat is None
        or current_lon is None
    ):

        return None


    current_plan = (
        TravelDayPlan.objects
        .filter(
            travel=travel,
            plan_date=schedule_date
        )
        .order_by(
            'tdp_id'
        )
        .first()
    )


    return {
        'name':
            current_name,

        'address':
            current_addr
            or current_name,

        'lat':
            float(
                current_lat
            ),

        'lon':
            float(
                current_lon
            ),

        'departure_time': (
            current_plan.departure_time.strftime('%H:%M')
            if (
                current_plan
                and
                current_plan.departure_time
            )
            else '09:00'
        ),

        'marker':
            'S',
    }


# ==============================================
# 마지막 DAY 출발지 복귀 정보
# 기본 복귀 예정 시간: 22:00
# ==============================================

def _build_return_home_point(
    travel,
    schedule
):
    """
    마지막 DAY에만 최초 출발지를 복귀 지점으로 반환한다.
    실제 장소 일정(SCHEDULE_PLACES)에는 저장하지 않고,
    지도/타임라인용 가상 복귀 지점으로 사용한다.
    """

    last_schedule = (
        Schedule.objects
        .filter(travel=travel)
        .order_by('-s_day', '-s_id')
        .first()
    )

    if (
        last_schedule is None
        or last_schedule.s_id != schedule.s_id
    ):
        return None

    lat = getattr(
        travel,
        'start_lat',
        None
    )

    lon = getattr(
        travel,
        'start_lon',
        None
    )

    if lat is None or lon is None:
        return None

    name = (
        getattr(
            travel,
            'start_place',
            None
        )
        or '출발지'
    )

    address = (
        getattr(
            travel,
            'start_addr',
            None
        )
        or name
    )

    return {
        'name': name,
        'address': address,
        'lat': float(lat),
        'lon': float(lon),
        'arrival_time': '22:00',
        'marker': 'R',
        'travel_time': 0,
    }


# ==============================================
# [보관용 / 현재 미사용] Kakao Mobility 대중교통 통합 길찾기
# - 제휴 API 사용 승인을 받으면 아래 코드를 다시 활성화할 수 있다.
# - 현재는 무료 ODsay Basic Web API를 브라우저에서 직접 호출한다.
# ==============================================
# # ==============================================
# # Kakao Mobility 대중교통 통합 길찾기
# # ==============================================
#
# KAKAO_PUBLIC_TRANSIT_URL = (
#     'https://apis-navi.kakaomobility.com/'
#     'affiliate/publictransit/v1/multimodal/directions'
# )
#
#
# def _seconds_from_midnight_to_hhmm(value):
#     """Kakao 대중교통 API의 자정 기준 초 값을 HH:MM으로 변환한다."""
#     try:
#         total = int(value)
#     except (TypeError, ValueError):
#         return None
#
#     if total < 0:
#         return None
#
#     total %= 24 * 60 * 60
#     hour = total // 3600
#     minute = (total % 3600) // 60
#     return f'{hour:02d}:{minute:02d}'
#
#
# def _normalize_transit_departure_hhmmss(value):
#     """09:30 / datetime.time 등을 Kakao hhmmss 정수 형식으로 바꾼다."""
#     if value is None:
#         return -1
#
#     if isinstance(value, time):
#         return (
#             value.hour * 10000
#             + value.minute * 100
#             + value.second
#         )
#
#     value = str(value).strip()
#     if not value:
#         return -1
#
#     for fmt in ('%H:%M:%S', '%H:%M'):
#         try:
#             parsed = datetime.strptime(value, fmt).time()
#             return (
#                 parsed.hour * 10000
#                 + parsed.minute * 100
#                 + parsed.second
#             )
#         except ValueError:
#             pass
#
#     return -1
#
#
# def _kakao_transit_day_type(travel_date):
#     """
#     Kakao 대중교통 API day_type.
#     토요일/일요일은 구분하고, 평일 공휴일은 별도 공휴일 캘린더가
#     없으므로 Weekday로 요청한다.
#     """
#     weekday = travel_date.weekday()
#
#     if weekday == 5:
#         return 'Saturday'
#
#     if weekday == 6:
#         return 'Holiday'
#
#     return 'Weekday'
#
#
# def _kakao_transit_vehicle_label(mode, vehicle_type):
#     vehicle_type = str(vehicle_type or '').strip().upper()
#
#     if mode == 'walk':
#         return '도보'
#
#     if mode == 'subway':
#         return {
#             'GENERAL': '지하철',
#             'EXPRESS': '급행 지하철',
#             'LIMITED_EXPRESS': '특급 지하철',
#             'DIRECT': '직행 지하철',
#         }.get(vehicle_type, '지하철')
#
#     return {
#         'EMPTY': '버스',
#         'BLUE': '간선버스',
#         'GREEN': '지선버스',
#         'RED': '광역버스',
#         'YELLOW': '순환버스',
#         'AIRPORT': '공항버스',
#         'GENERAL': '일반버스',
#         'SEAT': '좌석버스',
#         'EXPRESS': '급행버스',
#         'MAUL': '마을버스',
#         'DIRECT': '직행버스',
#         'OUTER': '외곽버스',
#         'INTERCITY': '시외버스',
#         'RURAL': '농어촌버스',
#     }.get(vehicle_type, '버스')
#
#
# def _append_transit_path_points(target, path):
#     """[x1,y1,x2,y2,...]를 지도용 [{lat,lon}, ...]로 변환한다."""
#     if not isinstance(path, list):
#         return
#
#     for i in range(0, len(path) - 1, 2):
#         try:
#             lon = float(path[i])
#             lat = float(path[i + 1])
#         except (TypeError, ValueError):
#             continue
#
#         point = {
#             'lat': lat,
#             'lon': lon,
#         }
#
#         if target and target[-1] == point:
#             continue
#
#         target.append(point)
#
#
# def _get_kakao_public_transit_route(
#     start_item,
#     end_item,
#     travel_date,
# ):
#     """
#     Kakao Mobility 대중교통 통합 길찾기에서 추천 경로 1개를 조회한다.
#
#     반환값은 travel_route()의 기존 route 구조와 맞춘다.
#     API 사용 권한/네트워크 문제가 있으면 예외를 발생시키고
#     호출부에서 기존 예상 경로로 fallback 한다.
#     """
#
#     departure_hhmmss = _normalize_transit_departure_hhmmss(
#         start_item.get('departure_time')
#     )
#
#     params = {
#         'start': f"{start_item['lon']},{start_item['lat']}",
#         'goal': f"{end_item['lon']},{end_item['lat']}",
#         'date': int(travel_date.strftime('%Y%m%d')),
#         'hhmmss': departure_hhmmss,
#         'day_type': _kakao_transit_day_type(travel_date),
#         'route_type': 'All',
#     }
#
#     headers = {
#         'Authorization': f'KakaoAK {settings.KAKAO_REST_API_KEY}',
#         'accept': 'application/json',
#         'Content-Type': 'application/json',
#     }
#
#     try:
#         response = requests.get(
#             KAKAO_PUBLIC_TRANSIT_URL,
#             headers=headers,
#             params=params,
#             timeout=12,
#         )
#     except requests.RequestException as e:
#         raise RuntimeError(
#             'Kakao 대중교통 API 연결 실패'
#         ) from e
#
#     if not response.ok:
#         message = ''
#         try:
#             error_data = response.json()
#             message = (
#                 error_data.get('msg')
#                 or error_data.get('message')
#                 or error_data.get('result_message')
#                 or ''
#             )
#         except ValueError:
#             pass
#
#         suffix = f': {message}' if message else ''
#         raise RuntimeError(
#             f'Kakao 대중교통 API HTTP {response.status_code}{suffix}'
#         )
#
#     data = response.json()
#
#     result_code = data.get('result_code')
#     if result_code != 0:
#         raise RuntimeError(
#             data.get('result_message')
#             or f'Kakao 대중교통 길찾기 실패 ({result_code})'
#         )
#
#     journeys = data.get('journeys') or []
#     if not journeys:
#         raise RuntimeError(
#             'Kakao 대중교통 추천 경로가 없습니다.'
#         )
#
#     # 문서상 journeys는 추천 순으로 제공되므로 첫 번째 경로 사용
#     journey = journeys[0]
#     summary = journey.get('summary') or {}
#     sections = journey.get('sections') or []
#
#     points = []
#     transit_steps = []
#     major_steps = []
#
#     for section in sections:
#         route = section.get('route') or {}
#         departure_stop = section.get('departure_stop') or {}
#         arrival_stop = section.get('arrival_stop') or {}
#
#         route_short_name = (
#             route.get('route_short_name')
#             or ''
#         )
#
#         vehicle_type = (
#             route.get('vehicle_type_name')
#             or ''
#         )
#
#         is_walk = (
#             str(route_short_name).strip().lower() == 'walk'
#             or str(vehicle_type).strip().lower() == 'walk'
#         )
#
#         is_subway = (
#             not is_walk
#             and (
#                 route.get('branch_id')
#                 or route.get('branch_direction')
#                 or route.get('train_type')
#             )
#         )
#
#         if is_walk:
#             mode = 'walk'
#         elif is_subway:
#             mode = 'subway'
#         else:
#             mode = 'bus'
#
#         vehicle_label = _kakao_transit_vehicle_label(
#             mode,
#             vehicle_type
#         )
#
#         line_name = ''
#         if mode != 'walk':
#             line_name = (
#                 route_short_name
#                 or route.get('route_full_name')
#                 or ''
#             )
#
#         display_name = vehicle_label
#         if line_name:
#             display_name = f'{vehicle_label} {line_name}'
#
#         step = {
#             'mode': mode,
#             'vehicle_type': vehicle_type,
#             'vehicle_label': vehicle_label,
#             'line_name': line_name,
#             'display_name': display_name,
#             'boarding_stop': departure_stop.get('stop_name') or '',
#             'alighting_stop': arrival_stop.get('stop_name') or '',
#             'departure_time': _seconds_from_midnight_to_hhmm(
#                 departure_stop.get('departure_time')
#             ),
#             'arrival_time': _seconds_from_midnight_to_hhmm(
#                 arrival_stop.get('arrival_time')
#             ),
#             'duration_minutes': max(
#                 int((int(section.get('time') or 0) + 59) // 60),
#                 0,
#             ),
#             'waiting_minutes': max(
#                 int((int(section.get('waiting_time') or 0) + 59) // 60),
#                 0,
#             ),
#             'direction': route.get('last_stop_name_of_trip') or '',
#             'first_trip': bool(section.get('first_trip', False)),
#             'last_trip': bool(section.get('last_trip', False)),
#             'platform_number': (
#                 (section.get('transfer') or {}).get('platform_number')
#                 or ''
#             ),
#         }
#
#         transit_steps.append(step)
#
#         if mode != 'walk':
#             major_steps.append(step)
#
#         _append_transit_path_points(
#             points,
#             section.get('path')
#         )
#
#         # path가 없는 구간은 최소한 정류장 좌표로 연결한다.
#         if not section.get('path'):
#             for stop in (departure_stop, arrival_stop):
#                 try:
#                     lon = float(stop.get('x'))
#                     lat = float(stop.get('y'))
#                 except (TypeError, ValueError):
#                     continue
#
#                 point = {
#                     'lat': lat,
#                     'lon': lon,
#                 }
#                 if not points or points[-1] != point:
#                     points.append(point)
#
#     if len(points) < 2:
#         points = [
#             {
#                 'lat': float(start_item['lat']),
#                 'lon': float(start_item['lon']),
#             },
#             {
#                 'lat': float(end_item['lat']),
#                 'lon': float(end_item['lon']),
#             },
#         ]
#
#     transport_names = [
#         step['display_name']
#         for step in major_steps
#         if step.get('display_name')
#     ]
#
#     transport_label = (
#         ' → '.join(transport_names)
#         if transport_names
#         else '대중교통'
#     )
#
#     first_major = major_steps[0] if major_steps else None
#     last_major = major_steps[-1] if major_steps else None
#
#     # 출발지에서 첫 승차지점까지 도보 시간이 있으면 함께 제공한다.
#     first_walk_minutes = 0
#     for step in transit_steps:
#         if step['mode'] != 'walk':
#             break
#         first_walk_minutes += step.get('duration_minutes') or 0
#
#     return {
#         'from_place': start_item['name'],
#         'to_place': end_item['name'],
#         'from_marker': start_item['marker'],
#         'to_marker': end_item['marker'],
#         'to_order': end_item['order'],
#         'success': True,
#         'estimated': False,
#         'api_source': 'kakao_public_transit',
#         'points': points,
#         'distance': int(summary.get('distance') or 0),
#         'duration': int(summary.get('total_time') or 0),
#         'moving_time': int(summary.get('moving_time') or 0),
#         'waiting_time': int(summary.get('waiting_time') or 0),
#         'walking_time': int(summary.get('walking_time') or 0),
#         'transfer_count': int(summary.get('transfer_count') or 0),
#         'transport': 'public_transport',
#         'transport_label': transport_label,
#         # 일정상 해당 구간을 시작하려는 시각
#         'origin_departure_time': start_item.get('departure_time'),
#         # 실제 노선에 승차하는 시각
#         'departure_time': (
#             first_major.get('departure_time')
#             if first_major
#             else start_item.get('departure_time')
#         ),
#         'departure_time_source': 'kakao_timetable',
#         'arrival_time': (
#             last_major.get('arrival_time')
#             if last_major
#             else None
#         ),
#         'transit_type': (
#             first_major.get('vehicle_label')
#             if first_major
#             else '대중교통'
#         ),
#         'line_name': (
#             first_major.get('line_name')
#             if first_major
#             else None
#         ),
#         'boarding_stop': (
#             first_major.get('boarding_stop')
#             if first_major
#             else None
#         ),
#         'alighting_stop': (
#             last_major.get('alighting_stop')
#             if last_major
#             else None
#         ),
#         'first_walk_minutes': first_walk_minutes,
#         'transit_steps': transit_steps,
#         'transit_detail_available': bool(transit_steps),
#     }
#
#

# ==============================================
# 일정별 지도 경로 API
# 출발지 S -> 일정 1 -> 일정 2 -> ...
# ==============================================

def travel_route(
    request,
    schedule_id
):

    schedule = get_object_or_404(
        Schedule,
        s_id=schedule_id
    )

    travel = schedule.travel


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
    # 교통수단
    # ==========================================

    transport = request.GET.get(
        'transport'
    )

    if not transport:

        transport = (
            travel.t_way
            or 'car'
        )


    transport = (
        str(transport)
        .split(',')[0]
        .strip()
        .lower()
    )


    transport_map = {

        'car':
            'car',

        '자동차':
            'car',

        '차':
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

        'public':
            'public_transport',

        '대중교통':
            'public_transport',
    }


    transport = transport_map.get(
        transport,
        transport
    )


    # ==========================================
    # 출발지
    # ==========================================

    start_point = (
        _build_route_start_point(
            travel,
            schedule
        )
    )

    # 마지막 DAY이면 최초 출발지로 돌아가는 복귀 지점을 만든다.
    return_point = (
        _build_return_home_point(
            travel,
            schedule
        )
    )


    # ==========================================
    # 일정 장소
    # ==========================================

    places = []


    for sp in schedule_places:

        place = sp.place

        if (
            place.p_lat is None
            or
            place.p_lon is None
        ):

            continue


        places.append({

            'id':
                place.p_id,

            'name':
                place.p_name,

            'address':
                place.p_addr,

            'lat':
                float(
                    place.p_lat
                ),

            'lon':
                float(
                    place.p_lon
                ),

            'order':
                sp.visit_order,

            'arrival_time': (
                sp.arrive_time.strftime(
                    '%H:%M'
                )
                if sp.arrive_time
                else None
            ),

            'stay_time':
                sp.stay_time,

            'start_time': (
                sp.start_time.strftime('%H:%M')
                if sp.start_time
                else None
            ),

            'travel_time':
                sp.travel_time,

            'kind':
                place.p_kind,
        })


    # ==========================================
    # 경로 계산용 waypoint
    # ==========================================

    waypoints = []


    if start_point:

        waypoints.append({

            'name':
                start_point['name'],

            'lat':
                start_point['lat'],

            'lon':
                start_point['lon'],

            'marker':
                'S',

            'order':
                None,

            'departure_time':
                start_point.get('departure_time'),
        })


    for place in places:

        waypoints.append({

            'name':
                place['name'],

            'lat':
                place['lat'],

            'lon':
                place['lon'],

            'marker':
                str(
                    place['order']
                ),

            'order':
                place['order'],

            'departure_time':
                place.get('start_time'),
        })


    # 마지막 DAY은 마지막 일정 -> 최초 출발지(R) 구간까지 경로에 포함한다.
    if return_point:

        # Kakao Mobility가 아직 차단돼 있어도 타임라인에 이동시간을
        # 보여줄 수 있도록 기존 평균속도 계산값을 함께 내려준다.
        if waypoints:
            previous_point = waypoints[-1]

            try:
                return_point['travel_time'] = (
                    get_travel_time(
                        previous_point['lat'],
                        previous_point['lon'],
                        return_point['lat'],
                        return_point['lon'],
                        transport
                    )
                )
            except Exception as e:
                print(
                    '출발지 복귀 예상시간 계산 실패:',
                    e
                )
                return_point['travel_time'] = 0

        waypoints.append({
            'name': return_point['name'],
            'lat': return_point['lat'],
            'lon': return_point['lon'],
            'marker': 'R',
            'order': None,
            'departure_time': None,
        })


    routes = []
    route_points = []

    total_distance = 0
    total_duration = 0


    def build_estimated_route(
        start_item,
        end_item,
        message=''
    ):
        """
        실제 경로 API를 사용할 수 없을 때 지도에서 구간 자체가
        사라지지 않도록 두 지점을 직선으로 연결하는 예상 구간을 만든다.

        주의: 대중교통 노선/정류장/탑승시각을 의미하는 실제 경로가 아니다.
        """
        try:
            minutes = get_travel_time(
                start_item['lat'],
                start_item['lon'],
                end_item['lat'],
                end_item['lon'],
                transport
            )
        except Exception:
            minutes = 0

        points = [
            {
                'lat': float(start_item['lat']),
                'lon': float(start_item['lon']),
            },
            {
                'lat': float(end_item['lat']),
                'lon': float(end_item['lon']),
            },
        ]

        if transport == 'public_transport':
            transport_label = '대중교통(상세 노선 미연동)'
        elif transport == 'car':
            transport_label = '자동차(예상)'
        elif transport == 'walk':
            transport_label = '도보(예상)'
        elif transport == 'bike':
            transport_label = '자전거(예상)'
        else:
            transport_label = '이동(예상)'

        return {
            'from_place': start_item['name'],
            'to_place': end_item['name'],
            'from_marker': start_item['marker'],
            'to_marker': end_item['marker'],
            'to_order': end_item['order'],
            'success': True,
            'estimated': True,
            'message': message,
            'points': points,
            'distance': 0,
            'duration': max(int(minutes or 0), 0) * 60,
            'transport': transport,
            'transport_label': transport_label,
            # 현재 값은 실제 버스/지하철 시간표가 아니라
            # 우리 일정에서 이 구간을 출발하도록 계획한 시각이다.
            'departure_time': start_item.get('departure_time'),
            'departure_time_source': 'schedule',
            'arrival_time': None,
            'transit_type': None,
            'line_name': None,
            'boarding_stop': None,
            'alighting_stop': None,
            'transit_detail_available': False,
        }


    for index in range(
        len(waypoints) - 1
    ):

        start_item = waypoints[index]
        end_item = waypoints[index + 1]


        # 대중교통은 서버에서 제휴 API를 호출하지 않는다.
        # 먼저 S/장소/R 좌표를 이용해 임시 경로를 만들고,
        # travel_detail.html에서 ODsay Basic Web API로 상세 노선을 보강한다.
        # 이렇게 하면 PythonAnywhere 무료 계정의 외부접속 allowlist와
        # 서버 고정 IP 문제를 피할 수 있다.
        if transport == 'public_transport':
            estimated_route = build_estimated_route(
                start_item,
                end_item,
                'ODsay Web API 조회 전 임시 경로'
            )
            estimated_route['api_source'] = 'odsay_web_pending'
            estimated_route['transit_api_error'] = False
            routes.append(estimated_route)
            route_points.extend(
                estimated_route['points']
            )
            total_duration += estimated_route['duration']

            # ------------------------------------------------------
            # [보관용 / 현재 미사용] Kakao Mobility 제휴 대중교통 API
            # ------------------------------------------------------
            # try:
            #     transit_route = _get_kakao_public_transit_route(
            #         start_item,
            #         end_item,
            #         schedule.s_day,
            #     )
            #     routes.append(transit_route)
            #     route_points.extend(transit_route.get('points', []))
            #     total_distance += transit_route.get('distance', 0) or 0
            #     total_duration += transit_route.get('duration', 0) or 0
            # except Exception as e:
            #     estimated_route = build_estimated_route(
            #         start_item,
            #         end_item,
            #         str(e)
            #     )
            #     estimated_route['transit_api_error'] = True
            #     routes.append(estimated_route)
            #     route_points.extend(estimated_route['points'])
            #     total_duration += estimated_route['duration']

            continue

        try:
            route_data = get_kakao_route(
                start_lat=start_item['lat'],
                start_lon=start_item['lon'],
                end_lat=end_item['lat'],
                end_lon=end_item['lon'],
                transport=transport
            )

        except Exception as e:
            estimated_route = build_estimated_route(
                start_item,
                end_item,
                str(e)
            )
            routes.append(estimated_route)
            route_points.extend(
                estimated_route['points']
            )
            total_duration += estimated_route['duration']
            continue

        if not route_data:
            estimated_route = build_estimated_route(
                start_item,
                end_item,
                '경로 데이터가 없어 예상 구간으로 표시'
            )
            routes.append(estimated_route)
            route_points.extend(
                estimated_route['points']
            )
            total_duration += estimated_route['duration']
            continue

        points = route_data.get('points', []) or []
        distance = route_data.get('distance', 0) or 0
        duration = route_data.get('duration', 0) or 0

        # 응답은 왔지만 그릴 좌표가 없으면 예상 직선 구간으로 대체한다.
        if len(points) < 2:
            estimated_route = build_estimated_route(
                start_item,
                end_item,
                '상세 경로 좌표가 없어 예상 구간으로 표시'
            )
            routes.append(estimated_route)
            route_points.extend(
                estimated_route['points']
            )
            total_duration += estimated_route['duration']
            continue

        route_points.extend(points)
        total_distance += distance
        total_duration += duration

        routes.append({
            'from_place': start_item['name'],
            'to_place': end_item['name'],
            'from_marker': start_item['marker'],
            'to_marker': end_item['marker'],
            'to_order': end_item['order'],
            'success': True,
            'estimated': False,
            'points': points,
            'distance': distance,
            'duration': duration,
            'transport': transport,
            'transport_label': (
                '자동차'
                if transport == 'car'
                else transport
            ),
            'departure_time': start_item.get('departure_time'),
            'departure_time_source': 'schedule',
            'arrival_time': None,
            'transit_type': None,
            'line_name': None,
            'boarding_stop': None,
            'alighting_stop': None,
            'transit_detail_available': False,
        })


    return JsonResponse({

        'success':
            True,

        'schedule_id':
            schedule.s_id,

        's_day':
            schedule.s_day.strftime(
                '%Y.%m.%d'
            ),

        'transport':
            transport,

        'start_point':
            start_point,

        'return_point':
            return_point,

        'is_last_day':
            bool(return_point),

        'places':
            places,

        'routes':
            routes,

        'points':
            route_points,

        'route_points':
            route_points,

        'distance':
            total_distance,

        'duration':
            total_duration,

        'total_distance':
            total_distance,

        'total_duration':
            total_duration,
    })



# ==============================================
# AI 대화로 여행 만들기
#
#   travel_chat        : 대화 한 번 처리 (AI 답변 + 갱신된 일정 초안)
#   travel_chat_apply  : 완성된 초안으로 실제 여행 생성
#
# 일정(장소/시간표) 자체는 기존 generate_schedule()이 만든다.
# ==============================================
chat_logger = logging.getLogger(__name__)

CHAT_BODY_LIMIT = 30000


def _chat_member(request):
    login_user = request.session.get('login_ok_user')

    if not login_user:
        return None

    try:
        return Member.objects.get(email=login_user)
    except Member.DoesNotExist:
        return None


def _chat_json_body(request):
    """요청 본문을 dict로 읽는다. 잘못되면 None."""
    if len(request.body) > CHAT_BODY_LIMIT:
        return None

    try:
        body = json.loads(request.body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return None

    return body if isinstance(body, dict) else None


def _chat_error(message, status, **extra):
    return JsonResponse({'ok': False, 'error': message, **extra}, status=status)


def _decimal_or_none(value):
    if value is None:
        return None

    return Decimal(str(value))


@require_POST
def travel_chat(request):
    member = _chat_member(request)

    if not member:
        return _chat_error('로그인이 필요해요.', 401, login=True)

    body = _chat_json_body(request)

    if body is None:
        return _chat_error('요청 형식이 올바르지 않아요.', 400)

    if not chat_service.check_rate_limit(request.session):
        return _chat_error('잠시 후 다시 시도해 주세요. (요청이 너무 많아요)', 429)

    category_names = list(
        Category.objects.order_by('c_id').values_list('c_name', flat=True)
    )

    try:
        result = chat_service.run_chat_turn(
            body.get('messages'),
            body.get('draft'),
            category_names,
            today=date.today(),
        )
    except chat_service.ChatError as error:
        return _chat_error(str(error), 502)
    except Exception:
        chat_logger.exception('travel_chat 처리 중 오류')
        return _chat_error('대화를 처리하지 못했어요. 잠시 후 다시 시도해 주세요.', 500)

    return JsonResponse(result)


@require_POST
def travel_chat_apply(request):
    member = _chat_member(request)

    if not member:
        return _chat_error('로그인이 필요해요.', 401, login=True)

    body = _chat_json_body(request)

    if body is None:
        return _chat_error('요청 형식이 올바르지 않아요.', 400)

    category_names = list(
        Category.objects.order_by('c_id').values_list('c_name', flat=True)
    )

    # 브라우저가 보낸 초안은 한 번 더 검증한다.
    draft = chat_service.normalize_draft(
        body.get('draft'),
        None,
        category_names,
        date.today(),
        resolve=False,
    )

    missing = chat_service.missing_fields(draft)

    if missing:
        return _chat_error(
            '아직 필요한 정보가 있어요: ' + ', '.join(missing),
            400,
        )

    try:
        travel = _chat_create_travel(member, draft)
    except ValueError as error:
        return _chat_error(str(error), 400)

    detail_url = reverse('travel_detail', kwargs={'travel_id': travel.t_id})
    warning = None

    try:
        generate_schedule(travel)
    except Exception:
        chat_logger.exception('AI 대화 여행 일정 생성 실패 (t_id=%s)', travel.t_id)
        warning = '여행은 만들어졌지만 자동 일정 생성에 실패했어요. 상세 화면에서 다시 확인해 주세요.'

    if warning is None:
        try:
            failed_pins = _chat_finish_schedule(
                travel,
                draft,
                _chat_clean_removed(body.get('removed')),
                _chat_clean_order(body.get('order')),
                with_images=True,
            )

            if failed_pins:
                warning = '일부 장소(%s)는 일정에 넣지 못했어요. 상세 화면에서 직접 추가해 주세요.' % ', '.join(failed_pins[:3])
        except Exception:
            chat_logger.exception('AI 대화 일정에 담은 장소/삭제/순서 반영 실패 (t_id=%s)', travel.t_id)
            warning = '여행은 만들어졌지만 담은 장소나 순서를 일정에 반영하지 못했어요. 상세 화면에서 확인해 주세요.'

    return JsonResponse({
        'ok': True,
        'url': detail_url,
        'warning': warning,
        'travel_id': travel.t_id,
        'start': draft['start'],
        'pins': [],  # 담은 장소는 이제 서버가 직접 일정에 넣는다
    })


# ==============================================
# AI 대화 여행 만들기 - 일정 미리보기
# ==============================================

PREVIEW_RATE_COUNT = 30        # 10분에 30번까지 (일정 생성은 무거운 작업이라 따로 센다)
PREVIEW_CACHE_SECONDS = 600    # 같은 초안/삭제 조건이면 10분 동안 저장해 둔 결과를 다시 쓴다
PREVIEW_TRANSPORT_LABEL = {
    'car': '자동차',
    'walk': '도보',
    'bike': '자전거',
    'public_transport': '대중교통',
}
WEEKDAY_KO = ['월', '화', '수', '목', '금', '토', '일']


def _chat_create_travel(member, draft):
    """검증된 초안으로 Travel / 컨셉 / 숙소 행을 만든다. (적용과 미리보기가 같이 쓴다)"""
    start = datetime.strptime(draft['start'], '%Y-%m-%d').date()
    end = datetime.strptime(draft['end'], '%Y-%m-%d').date()

    categories = list(
        Category.objects.filter(c_name__in=draft['categories']).order_by('c_id')
    )

    if not categories:
        raise ValueError('여행 컨셉을 다시 선택해 주세요.')

    start_place = draft.get('start_place') or {}
    start_time = draft.get('start_time') or None

    with transaction.atomic():
        travel = Travel.objects.create(
            member=member,
            t_title=draft['title'],
            t_place=draft['place'],
            t_start=start,
            t_end=end,
            t_day=start,
            t_way=draft.get('transport') or '',
            t_budget=draft.get('budget_total') or 100000,
            start_place=start_place.get('name') or start_place.get('query'),
            start_addr=start_place.get('addr'),
            start_lat=_decimal_or_none(start_place.get('lat')),
            start_lon=_decimal_or_none(start_place.get('lon')),
            start_time=start_time,
        )

        # generate_schedule()이 읽으므로 먼저 저장
        for category in categories:
            TravelCategory.objects.get_or_create(
                travel=travel,
                category=category,
            )

        for stay in draft.get('stays') or []:
            TravelDayPlan.objects.create(
                travel=travel,
                plan_date=datetime.strptime(stay['date'], '%Y-%m-%d').date(),
                accommodation_name=stay.get('name') or stay.get('query'),
                accommodation_addr=stay.get('addr'),
                accommodation_lat=_decimal_or_none(stay.get('lat')),
                accommodation_lon=_decimal_or_none(stay.get('lon')),
                arrival_time=stay.get('arrival_time') or None,
                departure_time=stay.get('departure_time') or None,
            )

    return travel


def _chat_clean_removed(raw):
    """브라우저가 보낸 '미리보기에서 지운 장소' 목록을 정리한다. [{day, name}]"""
    result = []

    if not isinstance(raw, list):
        return result

    for item in raw[:60]:
        if not isinstance(item, dict):
            continue

        day = item.get('day')
        name = item.get('name')

        if isinstance(day, bool) or not isinstance(day, int) or not 1 <= day <= 31:
            continue

        if not isinstance(name, str) or not name.strip():
            continue

        result.append({'day': day, 'name': name.strip()[:100]})

    return result


def _chat_apply_removed(travel, removed):
    """만들어진 일정에서 사용자가 지운 장소를 빼고, 시간을 다시 계산한다."""
    touched = {}

    for item in removed:
        day_date = travel.t_start + timedelta(days=item['day'] - 1)
        schedule = Schedule.objects.filter(travel=travel, s_day=day_date).first()

        if not schedule:
            continue

        deleted, _ = SchedulePlace.objects.filter(
            schedule=schedule,
            place__p_name=item['name'],
        ).delete()

        if deleted:
            touched[schedule.s_id] = schedule

    for schedule in touched.values():
        reorder_schedule_places_by_time(schedule)
        recalculate_schedule_timeline(schedule)


def _default_stay_minutes(kind):
    """장소 종류별 기본 체류시간(분). 장소 직접 추가(schedule_place_add)와 같은 기준."""
    kind = kind or ''

    if '쇼핑' in kind:
        return 120
    if '역사' in kind or '문화' in kind:
        return 90
    if '랜드마크' in kind:
        return 60
    if '공원' in kind:
        return 90
    if '카페' in kind:
        return 60
    if '음식' in kind or '식당' in kind:
        return 90
    if '자연' in kind or '바다' in kind:
        return 120
    if '관광' in kind:
        return 120

    return 60


def _chat_add_pins(travel, pins, with_images=False):
    """대화에서 담아 둔 장소를 만들어진 일정에 넣는다. 넣지 못한 장소 이름 목록을 돌려준다."""
    failed = []

    for pin in pins or []:
        name = (pin.get('name') or '').strip()

        try:
            with transaction.atomic():
                day = int(pin.get('day'))
                day_date = travel.t_start + timedelta(days=day - 1)

                if not name or day_date > travel.t_end:
                    raise ValueError('날짜가 여행 기간 밖이에요.')

                addr = (pin.get('addr') or '').strip()
                kind = (pin.get('kind') or '').strip()

                schedule = (
                    Schedule.objects.filter(travel=travel, s_day=day_date).order_by('s_id').first()
                    or Schedule.objects.create(travel=travel, s_day=day_date)
                )

                place = Place.objects.filter(travel=travel, p_name=name, p_addr=addr).first()

                if not place:
                    place = Place.objects.create(
                        travel=travel,
                        p_name=name,
                        p_addr=addr,
                        p_kind=kind,
                        p_lat=pin.get('lat'),
                        p_lon=pin.get('lon'),
                    )

                if with_images and not (place.p_image or ''):
                    try:
                        image = _search_kakao_image(f'{name} {addr}'.strip()) or _search_kakao_image(name)

                        if image:
                            place.p_image = image
                            place.save(update_fields=['p_image'])
                    except requests.RequestException:
                        pass

                if SchedulePlace.objects.filter(schedule=schedule, place=place).exists():
                    continue

                last = (
                    SchedulePlace.objects.filter(schedule=schedule)
                    .order_by('-visit_order', '-sp_id')
                    .first()
                )

                arrival = None

                if pin.get('time'):
                    try:
                        arrival = datetime.strptime(pin['time'], '%H:%M').time()
                    except ValueError:
                        arrival = None

                if arrival is None:
                    arrival = (last.start_time if last and last.start_time else None) or time(10, 0)

                stay_time = _default_stay_minutes(place.p_kind)
                start_time = (datetime.combine(schedule.s_day, arrival) + timedelta(minutes=stay_time)).time()

                schedule_place = SchedulePlace.objects.create(
                    schedule=schedule,
                    place=place,
                    visit_order=(last.visit_order + 1) if last else 1,
                    stay_time=stay_time,
                    arrive_time=arrival,
                    start_time=start_time,
                )

                reorder_schedule_places_by_time(schedule)
                recalculate_schedule_timeline(schedule, anchor_sp_id=schedule_place.sp_id)
        except Exception:
            chat_logger.exception('AI 대화 담은 장소를 일정에 넣지 못함: %s', name)
            failed.append(name or '(이름 없음)')

    return failed


def _chat_clean_order(raw):
    """브라우저가 보낸 '사용자가 바꾼 순서' 목록을 정리한다. [{day, names:[...]}]"""
    result = []

    if not isinstance(raw, list):
        return result

    for item in raw[:31]:
        if not isinstance(item, dict):
            continue

        day = item.get('day')
        names = item.get('names')

        if isinstance(day, bool) or not isinstance(day, int) or not 1 <= day <= 31:
            continue

        if not isinstance(names, list):
            continue

        clean = []

        for name in names[:40]:
            if isinstance(name, str) and name.strip() and name.strip()[:100] not in clean:
                clean.append(name.strip()[:100])

        if clean:
            result.append({'day': day, 'names': clean})

    return result


def _chat_apply_order(travel, order):
    """사용자가 정한 장소 순서대로 바꾸고, 이동시간과 방문시간을 다시 계산한다."""
    for item in order:
        day_date = travel.t_start + timedelta(days=item['day'] - 1)
        schedule = Schedule.objects.filter(travel=travel, s_day=day_date).first()

        if not schedule:
            continue

        rows = list(
            SchedulePlace.objects
            .filter(schedule=schedule)
            .select_related('place')
            .order_by('visit_order', 'sp_id')
        )

        if len(rows) < 2:
            continue

        by_name = {}

        for row in rows:
            by_name.setdefault(row.place.p_name, []).append(row)

        ordered = []

        for name in item['names']:
            if by_name.get(name):
                ordered.append(by_name[name].pop(0))

        picked = {row.sp_id for row in ordered}
        ordered += [row for row in rows if row.sp_id not in picked]

        if [row.sp_id for row in ordered] == [row.sp_id for row in rows]:
            continue

        # 하루의 시작 시각은 그대로 두고, 첫 장소가 바뀌어도 그 시각부터 이어서 계산한다
        first_arrival = next((row.arrive_time for row in rows if row.arrive_time), None)

        for new_order, row in enumerate(ordered, start=1):
            row.visit_order = new_order

        if first_arrival:
            ordered[0].arrive_time = first_arrival

        SchedulePlace.objects.bulk_update(ordered, ['visit_order', 'arrive_time'])
        recalculate_schedule_timeline(schedule)


def _chat_finish_schedule(travel, draft, removed, order, with_images=False):
    """자동으로 만든 일정 위에 사용자가 고른 것(담은 장소, 삭제, 순서)을 얹는다."""
    failed = _chat_add_pins(travel, draft.get('pins') or [], with_images)
    _chat_apply_removed(travel, removed)
    _chat_apply_order(travel, order)

    return failed


def _hhmm(value):
    return value.strftime('%H:%M') if value else None


def _float_or_none(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _chat_preview_days(travel, draft):
    """방금 만든 일정을 날짜별 타임라인(출발 → 장소 순서)으로 정리한다."""
    day_plan_map = get_travel_day_plans(travel)
    schedules = list(Schedule.objects.filter(travel=travel).order_by('s_day'))
    dates = [schedule.s_day for schedule in schedules]
    stays = resolve_effective_accommodations(travel, dates, day_plan_map)
    pin_keys = {(pin.get('day'), pin.get('name')) for pin in draft.get('pins') or []}
    days = []

    for index, schedule in enumerate(schedules):
        rows = list(
            SchedulePlace.objects
            .filter(schedule=schedule)
            .select_related('place')
            .order_by('visit_order', 'sp_id')
        )

        if index == 0:
            start_name = travel.start_place or '출발지'
        else:
            previous_stay = stays.get(dates[index - 1])
            start_name = previous_stay['name'] if previous_stay else '전날 숙소'

        items = []
        for row in rows:
            place = row.place
            kind = place.p_kind or ''

            items.append({
                'name': place.p_name,
                'kind': kind,
                'addr': place.p_addr or '',
                'lat': _float_or_none(place.p_lat),
                'lon': _float_or_none(place.p_lon),
                'arrive': _hhmm(row.arrive_time),
                'leave': _hhmm(row.start_time),
                'stay': row.stay_time,
                'move': row.travel_time,
                'is_stay': '숙' in kind,
                'pin': (index + 1, place.p_name) in pin_keys,
            })

        days.append({
            'day': index + 1,
            'date': schedule.s_day.isoformat(),
            'label': schedule.s_day.strftime('%m.%d'),
            'weekday': WEEKDAY_KO[schedule.s_day.weekday()],
            'start_time': _hhmm(get_day_start_time(travel, schedule.s_day, index, day_plan_map)),
            'start_name': start_name,
            'items': items,
        })

    return days


@require_POST
def travel_chat_preview(request):
    member = _chat_member(request)

    if not member:
        return _chat_error('로그인이 필요해요.', 401, login=True)

    body = _chat_json_body(request)

    if body is None:
        return _chat_error('요청 형식이 올바르지 않아요.', 400)

    category_names = list(
        Category.objects.order_by('c_id').values_list('c_name', flat=True)
    )

    draft = chat_service.normalize_draft(
        body.get('draft'),
        None,
        category_names,
        date.today(),
        resolve=False,
    )

    missing = chat_service.missing_fields(draft)

    if missing:
        return _chat_error('아직 필요한 정보가 있어요: ' + ', '.join(missing), 400)

    removed = _chat_clean_removed(body.get('removed'))
    order = _chat_clean_order(body.get('order'))

    # 같은 초안 + 같은 삭제 조건이면 다시 계산하지 않고 저장해 둔 결과를 돌려준다.
    # (저장된 결과를 쓰는 건 요청 횟수로 세지 않는다)
    cache_key = 'chat_preview:%s:%s' % (
        member.pk,
        hashlib.sha1(
            json.dumps([draft, removed, order], ensure_ascii=False, sort_keys=True, default=str).encode('utf-8')
        ).hexdigest(),
    )
    cached = cache.get(cache_key)

    if cached:
        return JsonResponse(cached)

    if not chat_service.check_rate_limit(
        request.session,
        key='ai_preview_calls',
        count=PREVIEW_RATE_COUNT,
    ):
        recent = request.session.get('ai_preview_calls') or []
        wait = 30

        if recent:
            wait = max(5, int(chat_service.RATE_LIMIT_SECONDS - (datetime.now().timestamp() - min(recent))) + 1)

        return _chat_error(
            '미리보기 요청이 많아요. %d초 뒤에 다시 시도해 주세요.' % wait,
            429,
            retry_after=wait,
        )

    days = []

    try:
        # 진짜 일정 생성 로직을 한 번 돌려 결과만 읽고, 저장은 전부 취소(롤백)한다.
        with transaction.atomic():
            travel = _chat_create_travel(member, draft)
            generate_schedule(travel)
            _chat_finish_schedule(travel, draft, removed, order)
            days = _chat_preview_days(travel, draft)
            transaction.set_rollback(True)
    except ValueError as error:
        return _chat_error(str(error), 400)
    except Exception:
        chat_logger.exception('AI 대화 일정 미리보기 실패')
        return _chat_error('일정 미리보기를 만들지 못했어요. 잠시 후 다시 시도해 주세요.', 500)

    transport = (draft.get('transport') or '').strip()

    result = {
        'ok': True,
        'days': days,
        'transport': PREVIEW_TRANSPORT_LABEL.get(transport, ''),
    }
    cache.set(cache_key, result, PREVIEW_CACHE_SECONDS)

    return JsonResponse(result)
