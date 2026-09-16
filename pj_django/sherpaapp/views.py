from django.http import HttpResponse, JsonResponse
from django.template import loader
from django.db.models import Prefetch
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings

from .models import Member
from .models import Travel
from .models import Place
from .models import Schedule
from .models import Pay
from .models import Category
from .models import SchedulePlace
from datetime import timedelta
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

        return redirect(
            'travel_detail',
            travel_id=travel.t_id
        )

    return render(
        request,
        'sherpaapp/travel_create.html',
        {
            'member': member
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
    # 해당 여행의 일정 조회
    #
    # TRAVEL
    #   ↓
    # SCHEDULE
    #   ↓
    # PLACE
    # ==========================================

    schedules = (
        Schedule.objects
        .filter(travel=travel)
        .select_related('place')
        .order_by('s_day', 's_turn')
    )

    # ==========================================
    # DAY별 일정
    # ==========================================

    days = []

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

    # ==========================================
    # 방문 장소 목록
    # ==========================================

    visited_places = []
    visited_place_ids = set()

    for schedule in schedules:

        if schedule.place:

            if schedule.place.p_id not in visited_place_ids:

                visited_place_ids.add(
                    schedule.place.p_id
                )

                visited_places.append(
                    schedule.place
                )

    # ==========================================
    # 여행 기간
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

        'schedules': schedules,

        'days': days,

        'visited_places': visited_places,

        'travel_days': travel_days,

        'place_count': len(visited_places),

    }

    return render(
        request,
        'sherpaapp/travel_detail.html',
        context
    )


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

        traffic = ','.join(
            request.POST.getlist('traffic')
        )

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

def schedule_update_time(request):

    if request.method == 'POST':
        schedule_id = request.POST.get('schedule_id')
        arrive_time = request.POST.get('arrive_time')
        schedule = get_object_or_404(
            Schedule,
            s_id=schedule_id
        )
        schedule.arrive_time = arrive_time
        schedule.save()
        return JsonResponse({
            'success': True
        })
    return JsonResponse({
        'success': False
    })

def schedule_place_search(request):

    query = request.GET.get("query", "").strip()

    places = []

    if not query:
        return JsonResponse({
            "places": []
        })


    # ==========================================
    # 카카오 REST API
    # ==========================================

    REST_API_KEY = settings.KAKAO_REST_API_KEY

    headers = {
        "Authorization": f"KakaoAK {REST_API_KEY}"
    }


    # ==========================================
    # 카카오 장소 검색
    # ==========================================

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


    # ==========================================
    # 장소 반복
    # ==========================================

    for place in data.get("documents", []):

        place_name = place.get(
            "place_name",
            ""
        )


        # ======================================
        # 이미지 검색
        # ======================================

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

            image = image_data[
                "documents"
            ][0].get(
                "thumbnail_url"
            )


        # ======================================
        # 결과 저장
        # ======================================

        places.append({

            "name":
                place_name,

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


    return JsonResponse({
        "places": places
    })

def schedule_place_add(request):

    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': '잘못된 요청입니다.'
        })


    # =====================================
    # 전달받은 데이터
    # =====================================

    travel_id = request.POST.get('travel_id')
    s_day = request.POST.get('s_day')

    place_name = request.POST.get('place_name')
    place_addr = request.POST.get('place_addr')
    place_kind = request.POST.get('place_kind')

    place_lat = request.POST.get('place_lat')
    place_lon = request.POST.get('place_lon')

    place_image = request.POST.get('place_image')


    # =====================================
    # 여행 가져오기
    # =====================================

    travel = get_object_or_404(
        Travel,
        t_id=travel_id
    )


    # =====================================
    # PLACE 저장
    # =====================================

    place = Place.objects.create(

        travel=travel,

        p_name=place_name,

        p_addr=place_addr,

        p_kind=place_kind,

        p_lat=place_lat or None,

        p_lon=place_lon or None,

        p_image=place_image or None
    )


    # =====================================
    # 현재 DAY의 마지막 순서 확인
    # =====================================

    last_schedule = (
        Schedule.objects
        .filter(
            travel=travel,
            s_day=s_day
        )
        .order_by('-s_turn')
        .first()
    )


    if last_schedule:

        next_turn = last_schedule.s_turn + 1

    else:

        next_turn = 1


    # =====================================
    # SCHEDULE 저장
    # =====================================

    Schedule.objects.create(

        s_day=s_day,

        s_turn=next_turn,

        travel=travel,

        place=place
    )


    # =====================================
    # JS로 성공 응답
    # =====================================

    return JsonResponse({

        'success': True,

        'message':
            f'{place_name} 장소가 일정에 추가되었습니다.'

    })
    #DAY 1 일정 시간 저장
def schedule_time_update(request):
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': '잘못된 요청입니다.'
        })
    schedule_id = request.POST.get('schedule_id')
    arrive_time = request.POST.get('arrive_time')

    print("========== 시간 저장 ==========") #임시
    print("schedule_id:", schedule_id) #임시
    print("arrive_time:", arrive_time) #임시

    try:
        schedule = Schedule.objects.get(
            s_id=schedule_id
        )
        schedule.arrive_time = arrive_time
        schedule.save(
            update_fields=['arrive_time']
        )
        print("DB 저장 완료:", schedule.arrive_time) #임시
        
        return JsonResponse({
            'success': True
        })
    except Schedule.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': '일정을 찾을 수 없습니다.'
        })