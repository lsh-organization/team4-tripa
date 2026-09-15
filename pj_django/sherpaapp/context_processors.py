from .models import Member
from django.conf import settings

def login_member(request):
    login_user = request.session.get('login_ok_user')

    member = None

    if login_user:
        try:
            member = Member.objects.get(email=login_user)
        except Member.DoesNotExist:
            member = None

    return {
        'member': member
    }

def kakao_api_key(request):
    return {
        "KAKAO_MAP_API_KEY":
            settings.KAKAO_MAP_API_KEY
    }