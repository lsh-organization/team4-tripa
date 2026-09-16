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
                "KAKAO_MAP_API_KEY": settings.KAKAO_MAP_API_KEY
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

def travel_detail(request, travel_id):

    # ==========================================
    # 여행 정보
    # ==========================================

    travel = get_object_or_404(
        Travel,
        t_id=travel_id
    )

    # ==========================================
    # 로그인 회원 정보
    # ==========================================

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
    # 일정 장소 조회
    #
    # SCHEDULE_PLACES
    #        ↓
    #      PLACE
    # ==========================================

    schedule_place_queryset = (
        SchedulePlace.objects
        .select_related('place')
        .order_by('visit_order')
    )

    # ==========================================
    # 해당 여행 일정 조회
    #
    # TRAVEL
    #   ↓
    # SCHEDULE
    #   ↓
    # SCHEDULE_PLACES
    #   ↓
    # PLACE
    # ==========================================

    schedules = (
        Schedule.objects
        .filter(travel=travel)
        .prefetch_related(
            Prefetch(
                'schedule_places',
                queryset=schedule_place_queryset
            )
        )
        .order_by('s_day')
    )

    # ==========================================
    # DAY별 일정
    # ==========================================

    days = []

    for index, schedule in enumerate(
        schedules,
        start=1
    ):

        days.append({
            'day_number': index,
            'schedule': schedule,
            'places': schedule.schedule_places.all()
        })

    # ==========================================
    # 방문 장소 목록
    # 같은 장소 중복 제거
    # ==========================================

    visited_places = []
    visited_place_ids = set()

    for day in days:

        for schedule_place in day['places']:

            place = schedule_place.place

            if place.p_id not in visited_place_ids:

                visited_place_ids.add(
                    place.p_id
                )

                visited_places.append(
                    place
                )

    # ==========================================
    # 여행 기간 계산
    # ==========================================

    travel_days = 0

    if travel.t_start and travel.t_end:

        travel_days = (
            travel.t_end - travel.t_start
        ).days + 1

    # ==========================================
    # HTML 전달
    # ==========================================

    context = {
        'travel': travel,
        'member': member,

        # 일정
        'schedules': schedules,

        # DAY별 일정
        'days': days,

        # 방문 장소
        'visited_places': visited_places,

        # 여행 일수
        'travel_days': travel_days,

        # 방문 장소 개수
        'place_count': len(visited_places),
    }

    return render(
        request,
        'sherpaapp/travel_detail.html',
        context
    )

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

            'arrival_time':
                sp.arrive_time.strftime('%H:%M')
                if sp.arrive_time
                else None,

            'stay_time':
                sp.stay_time,
        })


    # ==========================================
    # 장소 사이 실제 경로
    # ==========================================

    route_points = []

    total_duration = 0
    total_distance = 0


    for i in range(
        len(places) - 1
    ):

        start = places[i]
        end = places[i + 1]

        route = get_kakao_route(
            start['lat'],
            start['lon'],
            end['lat'],
            end['lon'],
            travel.t_way
        )

        if not route:
            continue

        route_points.extend(
            route['points']
        )

        total_duration += (
            route['duration']
        )

        total_distance += (
            route['distance']
        )


    return JsonResponse({
        'transport': travel.t_way,

        'places': places,

        'route_points':
            route_points,

        'total_duration':
            total_duration,

        'total_distance':
            total_distance,
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

    # ==========================================
    # 수정 페이지 처음 접속
    # ==========================================

    return render(
        request,
        'mypage_edit.html',
        {
            'member': member
        }
    )