from django.http import HttpRequest, HttpResponseNotFound


def demo_admin_route_disabled(request: HttpRequest, *args, **kwargs) -> HttpResponseNotFound:
    return HttpResponseNotFound("Not found")
