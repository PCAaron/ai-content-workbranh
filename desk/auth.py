from datetime import timedelta

from django.contrib.auth import authenticate, login, logout
from django.db import connection, transaction
from django.middleware.csrf import get_token
from django.utils.timezone import now

from .http import Problem, audit, endpoint, role, string
from .models import Audit, LoginFailure


@endpoint("GET", None)
def session(request, data):
    return {"user":request.user.get_username(), "role":role(request.user) if request.user.is_authenticated else None,
            "csrf":get_token(request)}


@endpoint("POST", None)
def sign_in(request, data):
    username = string(data, "username", 150)
    password = data.get("password")
    if not isinstance(password,str) or len(password)>1024:
        raise Problem("无效的登录信息")
    with transaction.atomic():
        attempts, _ = LoginFailure.objects.select_for_update().get_or_create(username=username, defaults={"since":now()})
        if attempts.since < now()-timedelta(minutes=10):
            attempts.count, attempts.since = 0, now()
        if attempts.count >= 8:
            raise Problem("尝试次数过多，十分钟后重试", 429)
        user = authenticate(request, username=username, password=password)
        if user is None:
            attempts.count += 1
            attempts.save()
        else:
            attempts.delete()
            login(request,user)
            audit(user,"login",user)
    if user is None:
        raise Problem("账号或密码有误", 401)
    return {"user":user.username,"role":role(user),"csrf":get_token(request)}


@endpoint("POST", None)
def sign_out(request, data):
    logout(request)
    return {"csrf":get_token(request)}


@endpoint("GET", "reviewer")
def events(request, data):
    return list(Audit.objects.order_by("-id").values("id","actor","at","action","target")[:100])


def ready(request):
    from django.http import JsonResponse
    from django.db import DatabaseError
    try:
        Audit.objects.exists()
    except DatabaseError:
        return JsonResponse({"status":"unavailable"},status=503)
    return JsonResponse({"status":"ready"})
