from django.urls import path
from django.http import FileResponse, HttpResponse
from django.conf import settings
from desk import auth

def index(request):
    file = settings.WHITENOISE_ROOT / "index.html"
    return FileResponse(file.open("rb"), content_type="text/html") if file.exists() else HttpResponse("请先构建 web 前端", status=503)

urlpatterns = [
    path("", index), path("health/ready",auth.ready),
    path("api/session",auth.session), path("api/login",auth.sign_in), path("api/logout",auth.sign_out),
    path("api/audit",auth.events),
]
