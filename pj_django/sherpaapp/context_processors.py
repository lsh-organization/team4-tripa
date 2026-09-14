from .models import Member


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