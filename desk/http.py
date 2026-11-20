import json
from functools import wraps

from django.core.exceptions import ObjectDoesNotExist, RequestDataTooBig
from django.http import HttpResponseBase, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .models import Audit


class Problem(Exception):
    def __init__(self, message, status=400):
        self.message = message
        self.status = status


def role(user):
    if user.is_superuser or user.groups.filter(name="reviewer").exists():
        return "reviewer"
    if user.groups.filter(name="editor").exists():
        return "editor"
    return "viewer"


def endpoint(method, access="editor"):
    def decorate(view):
        @never_cache
        @require_http_methods([method])
        @wraps(view)
        def handle(request, *args, **kwargs):
            if access and not request.user.is_authenticated:
                return JsonResponse({"error":"请先登录"}, status=401)
            if access and role(request.user) not in ({"reviewer"} if access=="reviewer" else {"editor","reviewer"}):
                return JsonResponse({"error":"此账号没有操作权限"}, status=403)
            try:
                data = json.loads(request.body or b"{}") if method == "POST" else {}
                if not isinstance(data, dict):
                    raise Problem("需要 JSON 对象")
                result = view(request, data, *args, **kwargs)
                return result if isinstance(result, HttpResponseBase) else JsonResponse(result, safe=False)
            except (json.JSONDecodeError, UnicodeDecodeError):
                return JsonResponse({"error":"无效 JSON"}, status=400)
            except ObjectDoesNotExist:
                return JsonResponse({"error":"记录不存在"}, status=404)
            except RequestDataTooBig:
                return JsonResponse({"error":"输入超过限制"}, status=413)
            except Problem as exc:
                return JsonResponse({"error":exc.message}, status=exc.status)
        return handle
    return decorate


def string(data, key, limit, *, optional=False):
    value = data.get(key, "")
    if not isinstance(value, str) or len(value) > limit or (not optional and not value.strip()):
        raise Problem(f"{key} 不能为空或超过 {limit} 字符")
    return value.strip()


def number(data, key, minimum=1):
    value = data.get(key)
    if type(value) is not int or not minimum <= value < 2**63:
        raise Problem(f"无效的 {key}")
    return value


def audit(user, action, obj):
    Audit.objects.create(actor=str(user), action=action, target=f"{obj._meta.model_name}/{obj.pk}")
