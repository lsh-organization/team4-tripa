from django.http import HttpResponse, JsonResponse
from django.template import loader
from django.db.models import Prefetch
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from .services.schedule_service import generate_schedule
from .services.route_service import get_kakao_route
from .models import Member
from .models import Travel
from .models import Place
from .models import Schedule
from .models import Pay
from .models import Category
from .models import SchedulePlace
from .models import TravelCategory

import requests
from datetime import datetime, timedelta


# ==============================================
# 회원가입
# ==============================================

def join(request):
    template = loader.get_template('sherpaapp/join.html')
    return HttpResponse(template.render({}, request))


# ==============================================
# 로그인
# ==============================================

def login(request):
    template = loader.get_template('sherpaapp/login.html')
    return HttpResponse(template.render({}, request))


# ==============================================
# 장소 검색
# ==============================================

def place_search(request):
    template = loader.get_template('sherpaapp/place_search.html')
    return HttpResponse(template.render({}, request))


def place_search_search(request):

    # GET 방식으로 검색어 받기
    query = request.GET.get("query", "").strip()

    # 검색 결과 저장
    places = []

    # 검색어가 없으면
    if not query:
        return render(
            request,
            "sherpaapp/place_search.html",
            {
                "places": places,
                "query": query,

                "KAKAO_MAP_API_KEY":
                    settings.KAKAO_MAP_API_KEY
            }
        )

    # ============================================
    # 카카오 REST API KEY
    # ============================================

    REST_API_KEY = settings.KAKAO_REST_API_KEY

    headers = {
        "Authorization": f"KakaoAK {REST_API_KEY}"
    }

    # ============================================
    # 카카오 장소 검색
    # ============================================

    place_url = (
        "https://dapi.kakao.com/"
        "v2/local/search/keyword.json"
    )

    params = {
        "query": query,
        "size": 5
    }

    response = requests.get(
        place_url,
        headers=headers,
        params=params
    )

    data = response.json()

    # ============================================
    # 검색된 장소 반복
    # ============================================

    for place in data.get("documents", []):

        # 장소명
        place_name = place.get(
            "place_name",
            ""
        )

        # ========================================
        # 이미지 검색
        # ========================================

        image_url = (
            "https://dapi.kakao.com/"
            "v2/search/image"
        )

        image_params = {
            "query": place_name,
            "size": 1
        }

        image_response = requests.get(
            image_url,
            headers=headers,
            params=image_params
        )

        image_data = image_response.json()

        image = None

        if image_data.get("documents"):
            image = image_data["documents"][0].get(
                "thumbnail_url"
            )

        # ========================================
        # 장소 정보 저장
        # ========================================

        places.append({
            "name": place_name,

            "address":
                place.get("road_address_name")
                or place.get("address_name"),

            "category":
                place.get("category_name"),

            "phone":
                place.get("phone"),

            "place_url":
                place.get("place_url"),

            "x":
                place.get("x"),

            "y":
                place.get("y"),

            "image":
                image
        })

    # ============================================
    # HTML 전달
    # ============================================

    context = {
        "places": places,
        "query": query,
        "KAKAO_MAP_API_KEY": settings.KAKAO_MAP_API_KEY
    }

    return render(
        request,
        "sherpaapp/place_search.html",
        context
    )


# ==============================================
# 여행 생성
# ==============================================

def travel_create(request):

    login_user = request.session.get('login_ok_user')

    # 로그인하지 않은 경우
    if not login_user:
        return redirect('login')

    try:
        member = Member.objects.get(
            email=login_user
        )

    except Member.DoesNotExist:
        return redirect('login')

    # 여행 생성
    if request.method == 'POST':

        title = request.POST.get('t_title')
        place = request.POST.get('t_place')
        start = request.POST.get('t_start')
        end = request.POST.get('t_end')

        traffic = ','.join(
            request.POST.getlist('traffic')
        )

        travel = Travel.objects.create(
            member=member,
            t_title=title,
            t_place=place,
            t_start=start,
            t_end=end,
            t_day=start,
            t_way=traffic
        )

        # 자동 일정 생성
        generate_schedule(travel)

        return redirect(
            'travel_detail',
            travel_id=travel.t_id
        )
    categories = Category.objects.all()
    return render(
        request,
        'sherpaapp/travel_create.html',
        {
            'member': member,
            'categories': categories
        }
    )

    


# ==============================================
# 여행 목록
# ==============================================

def travel_list(request):

    login_user = request.session.get('login_ok_user')

    if not login_user:
        return redirect('login')

    try:
        member = Member.objects.get(
            email=login_user
        )

    except Member.DoesNotExist:
        return redirect('login')

    # 로그인 회원의 여행만 조회
    travels = Travel.objects.filter(
        member=member
    )

    return render(
        request,
        'sherpaapp/travel_list.html',
        {
            'member': member,
            'travels': travels
        }
    )


# ==============================================
# 여행 상세 + 일정 관리
# ==============================================


def travel_detail_day(request, travel_id, day):

    # 여행 정보
    travel = get_object_or_404(
        Travel,
        t_id=travel_id
    )

    # 해당 여행의 DAY 목록
    schedules = (
        Schedule.objects
        .filter(travel=travel)
        .order_by('s_day')
    )

    # DAY가 존재하지 않는 경우
    if not schedules.exists():
        return JsonResponse({
            'success': False,
            'message': '등록된 여행 일정이 없습니다.'
        }, status=404)

    # DAY 번호 범위 확인
    if day < 1 or day > schedules.count():
        return JsonResponse({
            'success': False,
            'message': '존재하지 않는 DAY입니다.'
        }, status=404)

    # 해당 DAY
    schedule = schedules[day - 1]

    # 해당 DAY의 장소 일정
    schedule_places = (
        SchedulePlace.objects
        .filter(schedule=schedule)
        .select_related('place')
        .order_by('visit_order')
    )

    # 해당 DAY의 비용
    pays = Pay.objects.filter(
        schedule=schedule
    )

    # 총 비용
    total_pay = sum(
        pay.pay_pay for pay in pays
    )

    # 장소 데이터
    places = []

    for sp in schedule_places:
        place = sp.place

        places.append({
            'sp_id': sp.sp_id,
            'visit_order': sp.visit_order,
            'arrive_time': (
                sp.arrive_time.strftime('%H:%M')
                if sp.arrive_time else ''
            ),
            'stay_time': sp.stay_time,
            'start_time': (
                sp.start_time.strftime('%H:%M')
                if sp.start_time else ''
            ),
            'place_id': place.p_id,
            'place_name': place.p_name,
            'place_addr': place.p_addr,
            'place_kind': place.p_kind,
            'place_image': getattr(place, 'p_image', '') or '',
        })

    # 비용 데이터
    payments = []

    for pay in pays:
        payments.append({
            'pay_context': pay.pay_context,
            'pay_pay': pay.pay_pay,
        })

    return JsonResponse({
        'success': True,
        'travel_id': travel.t_id,
        'day': day,
        'schedule_id': schedule.s_id,
        's_day': schedule.s_day.strftime('%Y.%m.%d'),
        'places': places,
        'pays': payments,
        'total_pay': total_pay,
    })


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
# 여행 수정
# ==============================================

def travel_update(request, travel_id):

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

        travel.t_title = request.POST.get(
            't_title'
        )

        travel.t_place = request.POST.get(
            't_place'
        )

        travel.t_start = request.POST.get(
            't_start'
        )

        travel.t_end = request.POST.get(
            't_end'
        )

        traffic = request.POST.getlist('traffic')

        travel.t_way = traffic

        # T_DAY도 시작일 기준으로 맞춤
        travel.t_day = request.POST.get(
            't_start'
        )

        travel.save()

        return redirect(
            'travel_detail',
            travel_id=travel.t_id
        )

    # ==========================================
    # 수정 페이지
    # ==========================================

    return render(
        request,
        'sherpaapp/travel_update.html',
        {
            'travel': travel,
            'member': member
        }
    )


# ==============================================
# 여행 삭제
# ==============================================

def travel_delete(request, travel_id):

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
                'member': member
            },
            request
        )
    )


# ==============================================
# 비용 관리
# ==============================================

def budget(request):

    template = loader.get_template(
        'sherpaapp/budget.html'
    )

    return HttpResponse(
        template.render(
            {},
            request
        )
    )


# ==============================================
# 이메일 중복 확인
# ==============================================

def check_email(request):

    email = request.GET.get(
        'email'
    )

    exists = Member.objects.filter(
        email=email
    ).exists()

    return JsonResponse({
        'is_exists': exists
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

    # ==========================================
    # 이메일 중복 확인
    # ==========================================

    if Member.objects.filter(
        email=email
    ).exists():

        return HttpResponse("""
            <script>
                alert('이미 사용 중인 이메일입니다.');
                history.back();
            </script>
        """)

    # ==========================================
    # 회원가입
    # ==========================================

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

        # ======================================
        # 비밀번호 확인
        # ======================================

        if member.pwd == pwd:

            # 로그인 세션 저장
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
            'member': member
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
# ID / PW 찾기 페이지
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

    members = Member.objects.filter(
        name=name,
        nickname=nickname
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

    else:

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

        # ======================================
        # 새 비밀번호 확인
        # ======================================

        if new_pwd != new_pwd_check:

            return HttpResponse("""
                <script>
                    alert('비밀번호가 일치하지 않습니다.');
                    history.back();
                </script>
            """)

        # ======================================
        # 비밀번호 변경
        # ======================================

        member.pwd = new_pwd

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

    # 로그인하지 않았다면 로그인 페이지로 이동
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
    # 수정 페이지에서 저장 버튼 눌렀을 때
    # ==========================================

    if request.method == 'POST':

        name = request.POST.get(
            'name'
        )

        nickname = request.POST.get(
            'nickname'
        )

        member.name = name
        member.nickname = nickname

        member.save()

        return redirect(
            'mypage'
        )

    # 처음 수정 페이지에 들어왔을 때
    return render(request, 'mypage_edit.html', {
        'member': member
    })

def travel_detail(request, travel_id):
    travel = get_object_or_404(
        Travel,
        t_id=travel_id
    )

    # 로그인 사용자
    login_user = request.session.get('login_ok_user')

    member = None

    if login_user:
        try:
            member = Member.objects.get(
                email=login_user
            )
        except Member.DoesNotExist:
            member = None

    # 해당 여행의 DAY 목록
    schedules = (
        Schedule.objects
        .filter(travel=travel)
        .order_by('s_day')
    )

    return render(
        request,
        'sherpaapp/travel_detail.html',
        {
            'travel': travel,
            'member': member,

            # DAY
            'schedules': schedules,
    
            # 카카오맵
            'KAKAO_MAP_API_KEY': settings.KAKAO_MAP_API_KEY,
        }
    )

def schedule_place_add(request):
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': '잘못된 요청입니다.'
        }, status=400)

    schedule_id = request.POST.get('schedule_id')
    place_id = request.POST.get('place_id')
    arrive_time = request.POST.get('arrive_time')

    # 방문시간 확인
    if not arrive_time:
        return JsonResponse({
            'success': False,
            'message': '방문 시간을 먼저 입력해주세요'
        }, status=400)

    # 필수값 확인
    if not schedule_id or not place_id:
        return JsonResponse({
            'success': False,
            'message': '필수 정보가 없습니다.'
        }, status=400)

    # Schedule 조회
    schedule = get_object_or_404(
        Schedule,
        s_id=schedule_id
    )

    # Place 조회
    place = get_object_or_404(
        Place,
        p_id=place_id
    )

    # 방문시간 변환
    try:
        arrival = datetime.strptime(
            arrive_time,
            '%H:%M'
        ).time()
    except ValueError:
        return JsonResponse({
            'success': False,
            'message': '방문시간 형식이 올바르지 않습니다.'
        }, status=400)

    # --------------------------------
    # 체류시간 기본값
    # --------------------------------
    kind = place.p_kind or ''

    if '관광' in kind:
        stay_time = 120
    elif '쇼핑' in kind:
        stay_time = 120
    elif '공원' in kind:
        stay_time = 90
    elif '카페' in kind:
        stay_time = 60
    elif '음식' in kind or '식당' in kind:
        stay_time = 60
    else:
        stay_time = 60

    # --------------------------------
    # 방문 순서
    # --------------------------------
    last_place = (
        SchedulePlace.objects
        .filter(schedule=schedule)
        .order_by('-visit_order')
        .first()
    )

    if last_place:
        visit_order = last_place.visit_order + 1
    else:
        visit_order = 1

    # --------------------------------
    # 출발시간 계산
    # 방문시간 + 체류시간
    # --------------------------------
    arrival_datetime = datetime.combine(
        schedule.s_day,
        arrival
    )

    start_datetime = (
        arrival_datetime +
        timedelta(minutes=stay_time)
    )

    start_time = start_datetime.time()

    # --------------------------------
    # 일정 저장
    # --------------------------------
    schedule_place = SchedulePlace.objects.create(
        schedule=schedule,
        place=place,
        visit_order=visit_order,
        stay_time=stay_time,
        arrive_time=arrival,
        start_time=start_time
    )

    return JsonResponse({
        'success': True,
        'message': '일정이 추가되었습니다.',
        'sp_id': schedule_place.sp_id,
        'visit_order': visit_order,
        'place_name': place.p_name,
        'address': place.p_addr,
        'kind': place.p_kind,
        'arrive_time': arrival.strftime('%H:%M'),
        'stay_time': stay_time,
        'start_time': start_time.strftime('%H:%M')
    })

def schedule_place_delete(request):
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': '잘못된 요청입니다.'
        }, status=400)

    sp_id = request.POST.get('sp_id')

    if not sp_id:
        return JsonResponse({
            'success': False,
            'message': '삭제할 일정 정보가 없습니다.'
        }, status=400)

    # 삭제할 일정 조회
    schedule_place = get_object_or_404(
        SchedulePlace,
        sp_id=sp_id
    )

    # 같은 DAY의 Schedule 저장
    schedule = schedule_place.schedule

    # 일정 삭제
    schedule_place.delete()

    # 삭제 후 방문 순서 다시 정렬
    remaining_places = (
        SchedulePlace.objects
        .filter(schedule=schedule)
        .order_by('visit_order', 'sp_id')
    )

    for index, item in enumerate(remaining_places, start=1):
        if item.visit_order != index:
            item.visit_order = index
            item.save(update_fields=['visit_order'])

    return JsonResponse({
        'success': True,
        'message': '일정이 삭제되었습니다.'
    })

def schedule_place_time_update(request):
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': '잘못된 요청입니다.'
        }, status=400)

    sp_id = request.POST.get('sp_id')
    arrive_time = request.POST.get('arrive_time')

    # 필수값 확인
    if not sp_id or not arrive_time:
        return JsonResponse({
            'success': False,
            'message': '방문시간을 입력해주세요.'
        }, status=400)

    # 일정 조회
    schedule_place = get_object_or_404(
        SchedulePlace,
        sp_id=sp_id
    )

    # 방문시간 변환
    try:
        arrival = datetime.strptime(
            arrive_time,
            '%H:%M'
        ).time()
    except ValueError:
        return JsonResponse({
            'success': False,
            'message': '방문시간 형식이 올바르지 않습니다.'
        }, status=400)

    # 체류시간
    stay_time = schedule_place.stay_time or 0

    # 방문시간 + 체류시간 계산
    arrival_datetime = datetime.combine(
        schedule_place.schedule.s_day,
        arrival
    )

    start_datetime = (
        arrival_datetime +
        timedelta(minutes=stay_time)
    )

    start_time = start_datetime.time()

    # DB 업데이트
    schedule_place.arrive_time = arrival
    schedule_place.start_time = start_time
    schedule_place.save(
        update_fields=[
            'arrive_time',
            'start_time'
        ]
    )

    return JsonResponse({
        'success': True,
        'message': '방문시간이 변경되었습니다.',
        'arrive_time': arrival.strftime('%H:%M'),
        'start_time': start_time.strftime('%H:%M')
    })
