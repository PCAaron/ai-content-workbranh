import re

from django.db import transaction

from .http import Problem, audit, endpoint, number, string
from .intake import window
from .models import Draft, Job, Note, Revision, Topic


def evidence(topic):
    return {
        "title": topic.title,
        "quote": topic.quote.text,
        "locator": topic.quote.locator,
        "author": topic.quote.author.username,
        "sources": list(
            topic.sources.order_by("id")
            .values("id", "url", "title", "excerpt", "byline", "published")
            .iterator()
        ),
    }


def check_body(body, inputs):
    if not body or len(body) > 40000:
        raise Problem("正文须为 1–40000 字符")
    if inputs["quote"] not in body:
        raise Problem("请保留已确认的本人原话")
    cited = set(re.findall(r"\[S(\d+)\]", body))
    allowed = {str(s["id"]) for s in inputs["sources"]}
    if not cited or cited - allowed:
        raise Problem("请用 [S编号] 引用至少一条选题来源，并移除未知引用")


@transaction.atomic
def revise(draft, base, body, reason, actor):
    if not Draft.objects.filter(pk=draft.pk, version=base).update(
        version=base + 1, approved=None
    ):
        raise Problem("母稿已有新版本，请刷新并比对", 409)
    obj = Revision.objects.create(
        draft=draft, version=base + 1, body=body, reason=reason, actor=str(actor)
    )
    audit(actor, "revision.save", obj)
    return obj


@endpoint("POST")
@transaction.atomic
def open_draft(request, data):
    topic = Topic.objects.get(pk=number(data, "topic"))
    draft, created = Draft.objects.get_or_create(topic=topic)
    if created:
        audit(request.user, "draft.open", draft)
    return {"id": draft.pk}


@endpoint("GET")
def drafts(request, data):
    return list(
        window(request, Draft.objects.select_related("topic")).values(
            "id", "topic_id", "topic__title", "version", "approved"
        )
    )


@endpoint("GET")
def detail(request, data, pk):
    draft = Draft.objects.select_related("topic__quote__author").get(pk=pk)
    revisions = list(
        draft.revisions.order_by("-version").values(
            "id", "version", "actor", "reason", "at"
        )
    )
    return {
        "id": pk,
        "version": draft.version,
        "approved": draft.approved,
        "evidence": evidence(draft.topic),
        "body": draft.revisions.filter(version=draft.version)
        .values_list("body", flat=True)
        .first()
        or "",
        "samples": list(
            Draft.objects.filter(
                topic__quote__author_id=draft.topic.quote.author_id,
                approved__isnull=False,
            )
            .exclude(pk=pk)
            .order_by("-pk")
            .values("id", "topic__title")[:60]
        ),
        "revisions": revisions,
        "notes": list(
            Note.objects.filter(revision__draft=draft)
            .order_by("-id")
            .values("anchor", "text", "revision__version", "actor")
        ),
        "jobs": list(
            Job.objects.filter(draft=draft)
            .order_by("-id")
            .values("id", "state", "detail", "base", "budget", "model", "updated")
        ),
    }


@endpoint("GET")
def revision(request, data, pk, version):
    return Revision.objects.values("body", "reason", "actor", "version").get(
        draft_id=pk, version=version
    )


@endpoint("POST")
def save(request, data, pk):
    draft = Draft.objects.get(pk=pk)
    body = string(data, "body", 40000)
    rev = revise(
        draft, number(data, "base", 0), body, string(data, "reason", 500), request.user
    )
    return {"version": rev.version}


@endpoint("POST")
def restore(request, data, pk):
    rev = Revision.objects.select_related("draft").get(
        draft_id=pk, version=number(data, "version")
    )
    new = revise(
        rev.draft,
        number(data, "base", 0),
        rev.body,
        f"恢复版本 {rev.version}",
        request.user,
    )
    return {"version": new.version}


@endpoint("POST")
@transaction.atomic
def note(request, data, pk):
    rev = Revision.objects.get(draft_id=pk, version=number(data, "version"))
    anchor = string(data, "anchor", 500, optional=True)
    if anchor and anchor not in rev.body:
        raise Problem("批注引文与选定版本不匹配")
    item = Note.objects.create(
        revision=rev,
        actor=request.user.username,
        text=string(data, "text", 1500),
        anchor=anchor,
    )
    audit(request.user, "note.add", item)
    return {"id": item.pk}


@endpoint("POST", "reviewer")
@transaction.atomic
def approve(request, data, pk):
    base = number(data, "base")
    draft = Draft.objects.select_for_update().get(pk=pk)
    if draft.version != base:
        raise Problem("请核对当前版本", 409)
    rev = draft.revisions.get(version=base)
    check_body(rev.body, evidence(draft.topic))
    draft.approved = base
    draft.save(update_fields=["approved"])
    audit(request.user, "revision.approve", rev)
    return {"approved": base}


@endpoint("GET")
def overview(request, data):
    from .models import Source

    return {
        "sources": Source.objects.count(),
        "topics": Topic.objects.count(),
        "drafts": Draft.objects.count(),
        "review": Draft.objects.filter(version__gt=0, approved=None).count(),
        "recent": list(
            Draft.objects.order_by("-id").values("id", "topic__title", "version")[:8]
        ),
    }
