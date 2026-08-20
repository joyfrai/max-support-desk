from django.conf import settings


def demo_login(request):
    if not settings.DEMO_LOGIN_HINTS:
        return {"demo_login": None}

    username = settings.DEMO_LOGIN_USERNAME
    password = settings.DEMO_LOGIN_PASSWORD
    if not username or not password:
        return {"demo_login": None}

    return {"demo_login": {"username": username, "password": password}}
