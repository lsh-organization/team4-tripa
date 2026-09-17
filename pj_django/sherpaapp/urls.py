from django.urls import path
from . import views


urlpatterns = [

    # ==========================================
    # 메인
    # ==========================================

    path(
        '',
        views.index,
        name='index'
    ),


    # ==========================================
    # 회원
    # ==========================================

    path(
        'join/',
        views.join,
        name='join'
    ),

    path(
        'login/',
        views.login,
        name='login'
    ),

    path(
        'check_email/',
        views.check_email,
        name='check_email'
    ),

    path(
        'join_ok/',
        views.join_ok,
        name='join_ok'
    ),

    path(
        'login_ok/',
        views.login_ok,
        name='login_ok'
    ),

    path(
        'logout/',
        views.logout,
        name='logout'
    ),

    path(
        'idpw/',
        views.idpw,
        name='idpw'
    ),

    path(
        'id_find/',
        views.id_find,
        name='id_find'
    ),

    path(
        'pw_find/',
        views.pw_find,
        name='pw_find'
    ),


    # ==========================================
    # 마이페이지
    # ==========================================

    path(
        'mypage/',
        views.mypage,
        name='mypage'
    ),

    path(
        'mypage_edit/',
        views.mypage_edit,
        name='mypage_edit'
    ),


    # ==========================================
    # 장소 검색
    # ==========================================

    path(
        'place_search/',
        views.place_search,
        name='place_search'
    ),

    path(
        'place_search_search',
        views.place_search_search,
        name='place_search_search'
    ),


    # ==========================================
    # 여행
    # ==========================================

    path(
        'travel_create/',
        views.travel_create,
        name='travel_create'
    ),

    path(
        'travel_list/',
        views.travel_list,
        name='travel_list'
    ),

    path(
        'travel_detail/<int:travel_id>/',
        views.travel_detail,
        name='travel_detail'
    ),

    path(
        'travel_detail_day/<int:travel_id>/<int:day>/',
        views.travel_detail_day,
        name='travel_detail_day'
    ),

    path(
        'travel_update/<int:travel_id>/',
        views.travel_update,
        name='travel_update'
    ),

    path(
        'travel_delete/<int:travel_id>/',
        views.travel_delete,
        name='travel_delete'
    ),


    # ==========================================
    # 일정 장소
    # ==========================================

    path(
        'schedule_place_search/',
        views.schedule_place_search,
        name='schedule_place_search'
    ),

    path(
        'schedule_place_add/',
        views.schedule_place_add,
        name='schedule_place_add'
    ),

    path(
        'schedule_place_delete/',
        views.schedule_place_delete,
        name='schedule_place_delete'
    ),

    path(
        'schedule_place_time_update/',
        views.schedule_place_time_update,
        name='schedule_place_time_update'
    ),


    # ==========================================
    # 경로 계산
    # ==========================================

    path(
        'api/route/<int:schedule_id>/',
        views.travel_route,
        name='travel_route'
    ),


    # ==========================================
    # 비용 관리
    # ==========================================

    path(
        'budget/',
        views.budget,
        name='budget'
    ),

    path(
        'budget/<int:travel_id>/',
        views.budget,
        name='budget_travel'
    ),

    path(
        'budget/<int:travel_id>/update-total/',
        views.budget_update_total,
        name='budget_update_total'
    ),

    path(
        'budget/<int:travel_id>/add/',
        views.budget_add,
        name='budget_add'
    ),

    path(
        'budget/<int:travel_id>/delete/<int:pay_id>/',
        views.budget_delete,
        name='budget_delete'
    ),
]
