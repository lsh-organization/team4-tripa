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

# ==============================================
# 회원가입
# ==============================================

def join(request):
    template = loader.get_template('join.html')
    return HttpResponse(template.render({}, request))

# ==============================================
<<<<<<< HEAD
# 로그인 gg
=======
# 로그인asdasdasdasdsasdsa
>>>>>>> origin/master
# ==============================================

def login(request):
    template = loader.get_template('login.html')
    return HttpResponse(template.render({}, request))

# ==============================================
# 장소 검색
# ==============================================

def place_search(request):
    template = loader.get_template('sherpaapp/place_search.html')

# ==============================================
# 여행 생성
# ==============================================

def travel_create(request):
    template = loader.get_template('sherpaapp/travel_create.html')

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
    # travel = Travel.objects.get(t_id=travel_id)
    # return render(request, 'sherpaapp/travel_detail.html', {
    #     'travel': travel
    # })
    template = loader.get_template('travel_detail.html')
    login_user = request.session.get('login_ok_user')
    member = None
    if login_user:
        try:
            member = Member.objects.get(email=login_user)
        except Member.DoesNotExist:
            member = None
    return HttpResponse(template.render({'member': member}, request))

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

def index(request):
    travel = Travel.objects.first()
    if travel:
        return redirect('travel_detail', travel_id=travel.t_id)
    return redirect('travel_list')

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