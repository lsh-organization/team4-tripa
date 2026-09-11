from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('join/', views.join, name='join'),
    path('login/', views.login, name='login'),
    path('place_search/', views.place_search, name='place_search'),
    path('travel_create/', views.travel_create, name='travel_create'),
    path('travel_list/', views.travel_list, name='travel_list'),
    path('travel_detail/<int:travel_id>/', views.travel_detail, name='travel_detail'),
    path('travel_update/<int:travel_id>/', views.travel_update, name='travel_update'),
    path('travel_delete/<int:travel_id>/', views.travel_delete, name='travel_delete'),   
    path('budget/', views.budget, name='budget'),
    path('check_email/', views.check_email, name='check_email'),
    path('join_ok/', views.join_ok, name='join_ok'),
    path('login_ok/', views.login_ok, name='login_ok'),
    path('mypage/', views.mypage, name='mypage'),
    path('logout/', views.logout, name='logout'),
    path('idpw/', views.idpw, name='idpw'),
    path('id_find/', views.id_find, name='id_find'),
    path('pw_find/', views.pw_find, name='pw_find'),
]