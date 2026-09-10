from django.shortcuts import render
from django.http import HttpResponse
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
    template = loader.get_template('sherpaapp/join.html')
    return HttpResponse(template.render({}, request))

# ==============================================
# 로그인asdasdasdasdsasdsa
# ==============================================

def login(request):
    template = loader.get_template('sherpaapp/login.html')
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
    travel = Travel.objects.get(t_id=travel_id)

    return render(request, 'sherpaapp/travel_detail.html', {
        'travel': travel
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

def index(request):
    travel = Travel.objects.first()

    if travel:
        return redirect('travel_detail', travel_id=travel.t_id)
    return redirect('travel_list')
  