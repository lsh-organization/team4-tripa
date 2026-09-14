from django.http import HttpResponse,JsonResponse
from django.template import loader
from django.db.models import Q
from .models import Member
from .models import Travel
from .models import Place
from .models import Schedule
from .models import Pay
from .models import Category
from .models import SchedulePlace
from django.shortcuts import render, redirect
import requests
from django.conf import settings
from django.shortcuts import render

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

    #GET 방식으로 검색어 받기
    query = request.GET.get("query", "").strip()

    #GET 검색 결과 저장
    places = []

    #검색어가 없으면
    if not query:
        return render(
            request,
            "sherpaapp/place_search.html",
            {
                "places": places,
                "query": query
            }
        )
    # ============================================
    # 카카오 REST API KEY
    # ============================================
    REST_API_KEY = settings.KAKAO_REST_API_KEY

    headers = {
        "Authorization":
        f"KakaoAK {REST_API_KEY}"
    }
    # ============================================
    # 1. 카카오 장소 검색
    # ============================================
    place_url = (
        "https://dapi.kakao.com/"
        "v2/local/search/keyword.json"
    )
    params = {
        "query": query,
        # 검색 결과 개수
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
        # -------------------------
        # 장소명
        # -------------------------
        place_name = place.get(
            "place_name",
            ""
        )
        # -------------------------
        # 이미지 검색
        # -------------------------
        image_url = (
            "https://dapi.kakao.com/"
            "v2/search/image"
        )
        image_params = {
            "query":place_name,
            # 이미지 1개만 검색
            "size": 1
        }
        image_response = requests.get(
            image_url,
            headers=headers,
            params=image_params
        )
        image_data = image_response.json()

        #기본 이미지
        image = None

        #이미지가 존재하면
        if image_data.get("documents"):
            image = image_data[
                "documents"
            ][0].get(
                "thumbnail_url"
            )

        # -------------------------
        # 장소 정보 저장 
        # -------------------------    
        places.append({
            # 장소명
            "name":place_name,
            # 주소
            "address":
            place.get("road_address_name")
            or
            place.get("address_name"),
            # 카테고리
            "category":
            place.get("category_name"),
            # 전화번호
            "phone":
            place.get("phone"),
            # 카카오맵 장소 상세 페이지
            "place_url":
            place.get("place_url"),
            # 경도
            "x":
            place.get("x"),
            # 위도
            "y":
            place.get("y"),
            # 이미지
            "image":
            image

        })
    # ============================================
    # HTML 전달
    # ============================================
    context = {
        "places": places,
        "query": query
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
    template = loader.get_template('sherpaapp/travel_create.html')
    return HttpResponse(template.render({}, request))

# ==============================================
# 여행 목록
# ==============================================

def travel_list(request):  
    template = loader.get_template('sherpaapp/travel_list.html')
    return HttpResponse(template.render({}, request))

# ==============================================
# 여행 상세
# ==============================================

def travel_detail(request, travel_id):
    travel = Travel.objects.get(t_id=travel_id)
    login_user = request.session.get('login_ok_user')
    member = None
    if login_user:
        try:
            member = Member.objects.get(email=login_user)
        except Member.DoesNotExist:
            member = None

    return render(request, 'sherpaapp/travel_detail.html', {
        'travel': travel,
        'member': member
    })

# ==============================================
# 여행 수정
# ==============================================

def travel_update(request, travel_id):
    pass

# ==============================================
# 여행 삭제
# ==============================================

def travel_delete(request, travel_id):
    pass

# ==============================================
# 홈페이지
# ==============================================

def index(request):
    template = loader.get_template('index.html')
    login_user = request.session.get('login_ok_user')
    member = None
    if login_user:
        try:
            member = Member.objects.get(email=login_user)
        except Member.DoesNotExist:
            member = None
    return HttpResponse(template.render({'member': member}, request))

# ==============================================
# 예산
# ==============================================

def budget(request):
    template = loader.get_template('sherpaapp/budget.html')
    return HttpResponse(template.render({}, request))



def check_email(request):
    email = request.GET.get('email')
    exists = Member.objects.filter(email=email).exists()
    return JsonResponse({'is_exists': exists})

def join_ok(request):
    email = request.POST.get('email')
    pwd = request.POST.get('pwd')
    name = request.POST.get('name')
    nickname = request.POST.get('nickname')
    # 이메일 중복 확인
    if Member.objects.filter(email=email).exists():
        return HttpResponse("""
            <script>
                alert('이미 사용 중인 이메일입니다.');
                history.back();
            </script>
        """)
    # 회원가입
    Member.objects.create(email=email,pwd=pwd,name=name,nickname=nickname)
    # 회원가입 완료
    return HttpResponse("""
        <script>
            alert('회원가입이 완료되었습니다!');
            location.href = '../login/';
        </script>
    """)

def login_ok(request):
    email = request.POST.get('email')
    pwd = request.POST.get('pwd')
    try:
        member = Member.objects.get(email=email)
        # 비밀번호 확인
        if member.pwd == pwd:
            # 로그인 세션 저장
            request.session['login_ok_user'] = member.email
            # return redirect('index')
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
    
def mypage(request):
    login_user = request.session.get('login_ok_user')
    if not login_user:
        return redirect('login')
    try:
        member = Member.objects.get(email=login_user)
    except Member.DoesNotExist:
        return redirect('login')
    return render(request, 'mypage.html', {'member': member})  

def logout(request):
    request.session.flush()
    return HttpResponse("""
        <script>
            alert('로그아웃되었습니다.');
            location.href = '../';
        </script>
    """)

# ID/PW 찾기 페이지
def idpw(request):
    template = loader.get_template('idpw.html')
    return HttpResponse(template.render({}, request))

# 아이디 찾기
def id_find(request):
    name = request.POST.get('name')
    nickname = request.POST.get('nickname')
    members = Member.objects.filter(name=name,nickname=nickname)
    if members.exists():
        emails = [member.email for member in members]
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

# 비밀번호 찾기
def pw_find(request):
    email = request.POST.get('email')
    name = request.POST.get('name')
    new_pwd = request.POST.get('new_pwd')
    new_pwd_check = request.POST.get('new_pwd_check')
    try:
        member = Member.objects.get(email=email,name=name)
        # 새 비밀번호 확인
        if new_pwd != new_pwd_check:
            return HttpResponse("""
                <script>
                    alert('비밀번호가 일치하지 않습니다.');
                    history.back();
                </script>
            """)
        # 비밀번호 변경
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

    login_user = request.session.get('login_ok_user')

    # 로그인하지 않았다면 로그인 페이지로 이동
    if not login_user:
        return redirect('login')

    try:
        member = Member.objects.get(email=login_user)
    except Member.DoesNotExist:
        return redirect('login')

    # 수정 페이지에서 저장 버튼을 눌렀을 때
    if request.method == 'POST':

        name = request.POST.get('name')
        nickname = request.POST.get('nickname')

        member.name = name
        member.nickname = nickname

        member.save()

        return redirect('mypage')

    # 처음 수정 페이지에 들어왔을 때
    return render(request, 'mypage_edit.html', {
        'member': member
    })
