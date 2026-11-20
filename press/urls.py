from django.conf import settings
from django.http import FileResponse, HttpResponse
from django.urls import path

from desk import auth, channels, discovery, editorial, intake, learning, runner


def index(request):
    file = settings.WHITENOISE_ROOT / "index.html"
    return (
        FileResponse(file.open("rb"), content_type="text/html")
        if file.exists()
        else HttpResponse("请先构建 web 前端", status=503)
    )


urlpatterns = [
    path("", index),
    path("health/ready", auth.ready),
    path("api/session", auth.session),
    path("api/login", auth.sign_in),
    path("api/logout", auth.sign_out),
    path("api/audit", auth.events),
]
urlpatterns += [
    path("api/library", intake.library),
    path("api/sources", intake.add_source),
    path("api/quotes", intake.add_quote),
    path("api/topics", intake.add_topic),
    path("api/pull", intake.pull),
    path("api/discovery/search", discovery.search),
    path("api/discovery/capture", discovery.capture),
]
urlpatterns += [
    path("api/drafts", editorial.drafts),
    path("api/drafts/open", editorial.open_draft),
    path("api/drafts/<int:pk>", editorial.detail),
    path("api/drafts/<int:pk>/save", editorial.save),
    path("api/drafts/<int:pk>/restore", editorial.restore),
    path("api/drafts/<int:pk>/versions/<int:version>", editorial.revision),
    path("api/drafts/<int:pk>/notes", editorial.note),
    path("api/drafts/<int:pk>/approve", editorial.approve),
    path("api/drafts/<int:pk>/generate", runner.enqueue),
    path("api/jobs", runner.jobs),
    path("api/jobs/<int:pk>", runner.receipt),
]
urlpatterns += [
    path("api/drafts/<int:pk>/compile", channels.compile_edition),
    path("api/drafts/<int:pk>/editions", channels.editions),
    path("api/editions/<int:pk>/save", channels.edit),
    path("api/editions/<int:pk>/approve", channels.accept),
    path("api/editions/<int:pk>/download", channels.download),
    path("api/editions/<int:pk>/deliver", channels.deliver),
    path("api/deliveries", channels.deliveries),
    path("api/deliveries/<int:pk>/reconcile", channels.reconcile),
]
urlpatterns += [
    path("api/learning", learning.overview),
    path("api/learning/examples/<int:pk>", learning.suggest),
    path("api/rules", learning.propose),
    path("api/rules/<int:pk>/evaluate", learning.evaluate),
    path("api/rules/<int:pk>/activate", learning.activate),
    path("api/rules/<int:pk>/rollback", learning.rollback),
]
urlpatterns.append(path("api/overview", editorial.overview))
urlpatterns.append(
    path("api/editions/<int:pk>/generate", runner.enqueue, {"channel": True})
)
