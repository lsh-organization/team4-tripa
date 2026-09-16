from datetime import datetime, timedelta

import requests

from django.conf import settings
from django.db.models import Prefetch
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template import loader

from .services.schedule_service import generate_schedule
from .services.route_service import get_kakao_route

from .models import (
    Member,
    Travel,
    Place,
    Schedule,
    Pay,
    Category,
    SchedulePlace,
    TravelCategory,
)


# ==============================================
# 회원가입
# ==============================================

def join(request):

    template = loader.get_template(
        'sherpaapp/join.html'
    )

    return HttpResponse(
        template.render(
            {},
            request
        )
    )


# ==============================================
# 로그인
# ==============================================

def login(request):

    template = loader.get_template(
        'sherpaapp/login.html'
    )

    return HttpResponse(
        template.render(
            {},
            request
        )
    )


# ==============================================
# 장소 검색
# ==============================================

def place_search(request):

    template = loader.get_template(
        'sherpaapp/place_search.html'
    )

    return HttpResponse(
        template.render(
            {},
            request
        )
    )


# ==============================================
# 장소 검색 실행
# ==============================================

def place_search_search(request):

    query = request.GET.get(
        'query',
        ''
    ).strip()

    places = []


    # 검색어 없음
    if not query:

        return render(
            request,
            'sherpaapp/place_search.html',
            {
                'places':
                    places,

                'query':
                    query,

                'KAKAO_MAP_API_KEY':
                    settings.KAKAO_MAP_API_KEY
            }
        )


    # ==========================================
    # 카카오 REST API
    # ==========================================

    REST_API_KEY = (
        settings.KAKAO_REST_API_KEY
    )


    headers = {
        'Authorization':
            f'KakaoAK {REST_API_KEY}'
    }


    # ==========================================
    # 장소 검색
    # ==========================================

    place_url = (
        'https://dapi.kakao.com/'
        'v2/local/search/keyword.json'
    )


    params = {
        'query':
            query,

        'size':
            5
    }


    response = requests.get(
        place_url,
        headers=headers,
        params=params
    )


    data = response.json()


    # ==========================================
    # 검색 결과 반복
    # ==========================================

    for place in data.get(
        'documents',
        []
    ):

        place_name = place.get(
            'place_name',
            ''
        )


        # ======================================
        # 이미지 검색
        # ======================================

        image_url = (
            'https://dapi.kakao.com/'
            'v2/search/image'
        )


        image_params = {
            'query':
                place_name,

            'size':
                1
        }


        image_response = requests.get(
            image_url,
            headers=headers,
            params=image_params
        )


        image_data = (
            image_response.json()
        )


        image = None


        if image_data.get(
            'documents'
        ):

            image = (
                image_data[
                    'documents'
                ][0].get(
                    'thumbnail_url'
                )
            )


        # ======================================
        # 장소 정보
        # ======================================

        places.append({

            'name':
                place_name,

            'address':
                place.get(
                    'road_address_name'
                )
                or
                place.get(
                    'address_name'
                ),

            'category':
                place.get(
                    'category_name'
                ),

            'phone':
                place.get(
                    'phone'
                ),

            'place_url':
                place.get(
                    'place_url'
                ),

            'x':
                place.get(
                    'x'
                ),

            'y':
                place.get(
                    'y'
                ),

            'image':
                image
        })


    context = {

        'places':
            places,

        'query':
            query,

        'KAKAO_MAP_API_KEY':
            settings.KAKAO_MAP_API_KEY
    }


    return render(
        request,
        'sherpaapp/place_search.html',
        context
    )


# ==============================================
# 여행 생성
# ==============================================

def travel_create(request):

    login_user = request.session.get(
        'login_ok_user'
    )


    # 로그인 확인
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
    # 여행 저장
    # ==========================================

    if request.method == 'POST':

        title = request.POST.get(
            't_title'
        )

        place = request.POST.get(
            't_place'
        )

        start = request.POST.get(
            't_start'
        )

        end = request.POST.get(
            't_end'
        )


        traffic = ','.join(
            request.POST.getlist(
                'traffic'
            )
        )


        travel = Travel.objects.create(

            member=
                member,

            t_title=
                title,

            t_place=
                place,

            t_start=
                start,

            t_end=
                end,

            t_day=
                start,

            t_way=
                traffic,

            # 기본 총 예산
            t_budget=
                100000
        )


        # ======================================
        # 팀원 자동 일정 생성 기능 유지
        # ======================================

        generate_schedule(
            travel
        )


        return redirect(
            'travel_detail',
            travel_id=travel.t_id
        )


    # ==========================================
    # 카테고리
    # ==========================================

    categories = (
        Category.objects.all()
    )


    return render(
        request,
        'sherpaapp/travel_create.html',
        {
            'member':
                member,

            'categories':
                categories
        }
    )


# ==============================================
# 여행 목록
# ==============================================

def travel_list(request):

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
        'sherpaapp/travel_list.html',
        {
            'member':
                member,

            'travels':
                travels
        }
    )


# ==============================================
# 여행 상세
# ==============================================

def travel_detail(
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
    # DAY 일정
    # ==========================================

    schedules = (
        Schedule.objects
        .filter(
            travel=travel
        )
        .order_by(
            's_day'
        )
    )


    return render(
        request,
        'sherpaapp/travel_detail.html',
        {
            'travel':
                travel,

            'member':
                member,

            'schedules':
                schedules,

            'KAKAO_MAP_API_KEY':
                settings.KAKAO_MAP_API_KEY,
        }
    )



# ==============================================
# 일정별 지도 경로 API
# ==============================================


def travel_route(request, schedule_id):

    schedule = get_object_or_404(
        Schedule,
        s_id=schedule_id
    )

    travel = schedule.travel

    schedule_places = (
        SchedulePlace.objects
        .filter(schedule=schedule)
        .select_related('place')
        .order_by('visit_order')
    )

    places = []

    for sp in schedule_places:
        place = sp.place

        if (
            place.p_lat is None
            or place.p_lon is None
        ):
            continue

        places.append({
            'id': place.p_id,
            'name': place.p_name,
            'address': place.p_addr,
            'lat': float(place.p_lat),
            'lon': float(place.p_lon),
            'order': sp.visit_order,
            'arrival_time': (
                sp.arrive_time.strftime('%H:%M')
                if sp.arrive_time
                else None
            ),
            'stay_time': sp.stay_time,
        })

    # ==========================================
    # 장소 사이 실제 경로
    # ==========================================

    route_points = []
    total_duration = 0
    total_distance = 0

    for i in range(len(places) - 1):
        start_place = places[i]
        end_place = places[i + 1]

        try:
            route = get_kakao_route(
                start_place['lat'],
                start_place['lon'],
                end_place['lat'],
                end_place['lon'],
                travel.t_way
            )

        except Exception as e:
            print(
                f'경로 조회 실패: '
                f'{start_place["name"]} -> {end_place["name"]}'
            )
            print(e)
            continue

        if not route:
            continue

        route_points.extend(
            route.get('points', [])
        )

        total_duration += route.get(
            'duration',
            0
        )

        total_distance += route.get(
            'distance',
            0
        )

    return JsonResponse({
        'success': True,
        'schedule_id': schedule.s_id,
        's_day': schedule.s_day.strftime('%Y.%m.%d'),
        'transport': travel.t_way,
        'places': places,
        'route_points': route_points,
        'total_duration': total_duration,
        'total_distance': total_distance,
    })


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
                sp.place.p_image
                or '',
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
            'member':
                member
        }
    )


# ==============================================
# 일정 장소 추가
# ==============================================

def schedule_place_add(request):

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


    schedule_id = request.POST.get(
        'schedule_id'
    )

    place_id = request.POST.get(
        'place_id'
    )

    arrive_time = request.POST.get(
        'arrive_time'
    )


    if not arrive_time:

        return JsonResponse(
            {
                'success':
                    False,

                'message':
                    '방문 시간을 먼저 입력해주세요'
            },
            status=400
        )


    if (
        not schedule_id
        or
        not place_id
    ):

        return JsonResponse(
            {
                'success':
                    False,

                'message':
                    '필수 정보가 없습니다.'
            },
            status=400
        )


    schedule = get_object_or_404(
        Schedule,
        s_id=schedule_id
    )


    place = get_object_or_404(
        Place,
        p_id=place_id
    )


    # ==========================================
    # 방문시간 변환
    # ==========================================

    try:

        arrival = datetime.strptime(
            arrive_time,
            '%H:%M'
        ).time()


    except ValueError:

        return JsonResponse(
            {
                'success':
                    False,

                'message':
                    '방문시간 형식이 올바르지 않습니다.'
            },
            status=400
        )


    # ==========================================
    # 체류시간
    # ==========================================

    kind = (
        place.p_kind
        or ''
    )


    if '관광' in kind:

        stay_time = 120

    elif '쇼핑' in kind:

        stay_time = 120

    elif '공원' in kind:

        stay_time = 90

    elif '카페' in kind:

        stay_time = 60

    elif (
        '음식' in kind
        or
        '식당' in kind
    ):

        stay_time = 60

    else:

        stay_time = 60


    # ==========================================
    # 방문순서
    # ==========================================

    last_place = (
        SchedulePlace.objects
        .filter(
            schedule=schedule
        )
        .order_by(
            '-visit_order'
        )
        .first()
    )


    if last_place:

        visit_order = (
            last_place.visit_order
            + 1
        )

    else:

        visit_order = 1


    # ==========================================
    # 출발시간 계산
    # ==========================================

    arrival_datetime = (
        datetime.combine(
            schedule.s_day,
            arrival
        )
    )


    start_datetime = (
        arrival_datetime
        +
        timedelta(
            minutes=stay_time
        )
    )


    start_time = (
        start_datetime.time()
    )


    # ==========================================
    # 일정 장소 저장
    # ==========================================

    schedule_place = (
        SchedulePlace.objects.create(

            schedule=
                schedule,

            place=
                place,

            visit_order=
                visit_order,

            stay_time=
                stay_time,

            arrive_time=
                arrival,

            start_time=
                start_time
        )
    )


    return JsonResponse({

        'success':
            True,

        'message':
            '일정이 추가되었습니다.',

        'sp_id':
            schedule_place.sp_id,

        'visit_order':
            visit_order,

        'place_name':
            place.p_name,

        'address':
            place.p_addr,

        'kind':
            place.p_kind,

        'arrive_time':
            arrival.strftime(
                '%H:%M'
            ),

        'stay_time':
            stay_time,

        'start_time':
            start_time.strftime(
                '%H:%M'
            )
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
    # 순서 다시 정렬
    # ==========================================

    remaining_places = (
        SchedulePlace.objects
        .filter(
            schedule=schedule
        )
        .order_by(
            'visit_order',
            'sp_id'
        )
    )


    for index, item in enumerate(
        remaining_places,
        start=1
    ):

        if (
            item.visit_order
            !=
            index
        ):

            item.visit_order = (
                index
            )


            item.save(
                update_fields=[
                    'visit_order'
                ]
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

    arrive_time = request.POST.get(
        'arrive_time'
    )


    if (
        not sp_id
        or
        not arrive_time
    ):

        return JsonResponse(
            {
                'success':
                    False,

                'message':
                    '방문시간을 입력해주세요.'
            },
            status=400
        )


    schedule_place = (
        get_object_or_404(
            SchedulePlace,
            sp_id=sp_id
        )
    )


    try:

        arrival = datetime.strptime(
            arrive_time,
            '%H:%M'
        ).time()


    except ValueError:

        return JsonResponse(
            {
                'success':
                    False,

                'message':
                    '방문시간 형식이 올바르지 않습니다.'
            },
            status=400
        )


    stay_time = (
        schedule_place.stay_time
        or 0
    )


    arrival_datetime = (
        datetime.combine(
            schedule_place
            .schedule
            .s_day,
            arrival
        )
    )


    start_datetime = (
        arrival_datetime
        +
        timedelta(
            minutes=stay_time
        )
    )


    start_time = (
        start_datetime.time()
    )


    schedule_place.arrive_time = (
        arrival
    )

    schedule_place.start_time = (
        start_time
    )


    schedule_place.save(
        update_fields=[
            'arrive_time',
            'start_time'
        ]
    )


    return JsonResponse({

        'success':
            True,

        'message':
            '방문시간이 변경되었습니다.',

        'arrive_time':
            arrival.strftime(
                '%H:%M'
            ),

        'start_time':
            start_time.strftime(
                '%H:%M'
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


    return JsonResponse({

        'success':
            True,

        'transport':
            transport,

        'schedule_id':
            schedule.s_id,

        'points':
            all_points,

        'routes':
            routes,

        'distance':
            total_distance,

        'duration':
            total_duration
    })