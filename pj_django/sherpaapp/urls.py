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
]