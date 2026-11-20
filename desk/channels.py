import os
from datetime import timedelta

import httpx
from django.db import transaction
from django.http import HttpResponse
from django.utils.timezone import now

from .formats import PLATFORMS, adapt, article_html, render, sections, sources_text
from .http import Problem, audit, endpoint, number, string
from .models import Delivery, Draft, Edition


def platform(data):
    key = string(data, "platform", 16)
    if key not in PLATFORMS:
        raise Problem("未知平台")
    return key


def locked_edition(pk, data, *, approved=False):
    hint = (
        Edition.objects.only("revision__draft_id").select_related("revision").get(pk=pk)
    )
    draft = Draft.objects.select_for_update().get(pk=hint.revision.draft_id)
    item = Edition.objects.select_for_update().select_related("revision").get(pk=pk)
    if (
        draft.approved != item.revision.version
        or draft.version != item.revision.version
    ):
        raise Problem("此渠道版本关联的母稿已过期，请从最新审核版重新生成", 409)
    if item.version != number(data, "version") or (approved and not item.approved):
        raise Problem("请核对并审批最新渠道稿", 409)
    return item


@endpoint("POST")
@transaction.atomic
def compile_edition(request, data, pk):
    draft = Draft.objects.select_for_update().get(pk=pk)
    base = number(data, "base")
    if draft.approved != base or draft.version != base:
        raise Problem("请先审核当前母稿", 409)
    key = platform(data)
    rev = draft.revisions.get(version=base)
    item, new = Edition.objects.get_or_create(
        revision=rev, platform=key, defaults=adapt(rev, key)
    )
    if new:
        audit(request.user, "edition.compile", item)
    return {"id": item.pk}


@endpoint("GET")
def editions(request, data, pk):
    return list(
        Edition.objects.filter(revision__draft_id=pk)
        .order_by("-id")
        .values(
            "id",
            "revision__version",
            "platform",
            "version",
            "approved",
            "body",
            "title",
            "cards",
        )[:80]
    )


@endpoint("POST")
@transaction.atomic
def edit(request, data, pk):
    item = locked_edition(pk, data)
    xhs = item.platform == "xhs"
    item.title = string(data, "title", 20 if xhs else 300)
    item.body = string(data, "body", 1000 if xhs else 50000)
    if xhs:
        cards = data.get("cards")
        if (
            not isinstance(cards, list)
            or not 1 <= len(cards) <= 9
            or any(
                not isinstance(c, str) or not c.strip() or len(c) > 160 for c in cards
            )
        ):
            raise Problem("需要 1–9 张图卡，每张最多 160 字")
        item.cards = cards
    item.version += 1
    item.approved = False
    item.save()
    audit(request.user, "edition.edit", item)
    return {"version": item.version}


@endpoint("POST", "reviewer")
@transaction.atomic
def accept(request, data, pk):
    item = locked_edition(pk, data)
    item.approved = True
    item.save(update_fields=["approved"])
    audit(request.user, "edition.approve", item)
    return {"version": item.version}


@endpoint("POST", "reviewer")
def download(request, data, pk):
    with transaction.atomic():
        item = locked_edition(pk, data, approved=True)
    ext, mime, body = render(item)
    audit(request.user, "edition.export", item)
    resp = HttpResponse(body, content_type=mime)
    resp["Content-Disposition"] = (
        f'attachment; filename="{item.platform}-{pk}-v{item.version}.{ext}"'
    )
    return resp


def remote_config(key):
    if key == "x" and os.getenv("PRESS_X_DRAFT_TOKEN"):
        return {"token": os.environ["PRESS_X_DRAFT_TOKEN"]}
    if key == "wechat" and all(
        os.getenv(k)
        for k in ("PRESS_WX_APP_ID", "PRESS_WX_SECRET", "PRESS_WX_COVER_ID")
    ):
        return {
            "app": os.environ["PRESS_WX_APP_ID"],
            "secret": os.environ["PRESS_WX_SECRET"],
            "cover": os.environ["PRESS_WX_COVER_ID"],
        }
    raise Problem("此渠道未启用远端草稿，请导出文件或配置账号", 409)


def create_remote(platform, snapshot, cfg):
    title, body = snapshot["title"], snapshot["body"] + "\n\n" + snapshot["sources"]
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        if platform == "x":
            blocks = [
                {
                    "type": "unstyled",
                    "text": p,
                    "entity_ranges": [],
                    "inline_style_ranges": [],
                }
                for p in sections(body)
            ]
            resp = client.post(
                "https://api.x.com/2/articles/draft",
                headers={"Authorization": "Bearer " + cfg["token"]},
                json={
                    "title": title,
                    "content_state": {"blocks": blocks, "entities": []},
                },
            )
            resp.raise_for_status()
            return resp.json()["data"]["id"]
        token = client.get(
            "https://api.weixin.qq.com/cgi-bin/token",
            params={
                "grant_type": "client_credential",
                "appid": cfg["app"],
                "secret": cfg["secret"],
            },
        )
        token.raise_for_status()
        access = token.json().get("access_token")
        if not access:
            raise Problem("公众号授权失败，尚未发送草稿")
        resp = client.post(
            "https://api.weixin.qq.com/cgi-bin/draft/add",
            params={"access_token": access},
            json={
                "articles": [
                    {
                        "title": title,
                        "content": article_html(title, body),
                        "thumb_media_id": cfg["cover"],
                    }
                ]
            },
        )
        resp.raise_for_status()
        reply = resp.json()
        if reply.get("errcode"):
            raise Problem("公众号拒绝草稿，错误码 " + str(reply["errcode"])[:12])
        return reply["media_id"]


@endpoint("POST", "reviewer")
def deliver(request, data, pk):
    if data.get("consent") is not True:
        raise Problem("请明确确认创建此版本的远端草稿")
    with transaction.atomic():
        item = locked_edition(pk, data, approved=True)
        existing = Delivery.objects.filter(edition=item, version=item.version).first()
        if existing:
            return {
                "id": existing.pk,
                "state": existing.state,
                "remote_id": existing.remote_id,
                "detail": existing.detail,
            }
        cfg = remote_config(item.platform)
        snapshot = {
            "title": item.title,
            "body": item.body,
            "sources": sources_text(item),
        }
        delivery = Delivery.objects.create(
            edition=item, version=item.version, state="sending", snapshot=snapshot
        )
        audit(request.user, "delivery.start", delivery)
    try:
        remote = create_remote(item.platform, snapshot, cfg)
        if not isinstance(remote, (str, int)) or not remote or len(str(remote)) > 256:
            raise ValueError
        state, detail = "sent", "已收到平台草稿编号"
    except Problem as exc:
        state, detail, remote = "failed", exc.message, ""
    except httpx.HTTPStatusError as exc:
        state = "failed" if 400 <= exc.response.status_code < 500 else "unknown"
        detail, remote = f"上游 HTTP {exc.response.status_code}", ""
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        state, detail, remote = "unknown", "请到平台草稿箱核对，系统不会自动重发", ""
    with transaction.atomic():
        Delivery.objects.filter(pk=delivery.pk, state="sending").update(
            state=state, detail=detail, remote_id=remote, updated=now()
        )
        delivery.refresh_from_db()
        audit(request.user, "delivery." + delivery.state, delivery)
    return {
        "id": delivery.pk,
        "state": delivery.state,
        "remote_id": delivery.remote_id,
        "detail": delivery.detail,
    }


@endpoint("GET", "reviewer")
def deliveries(request, data):
    return list(
        Delivery.objects.order_by("-id").values(
            "id",
            "edition__platform",
            "edition_id",
            "version",
            "state",
            "remote_id",
            "detail",
            "updated",
        )[:100]
    )


@endpoint("POST", "reviewer")
@transaction.atomic
def reconcile(request, data, pk):
    obj = Delivery.objects.select_for_update().get(pk=pk)
    if obj.state != "unknown" and not (
        obj.state == "sending" and obj.updated < now() - timedelta(minutes=5)
    ):
        raise Problem("此回执当前无需人工对账", 409)
    found = data.get("found")
    if type(found) is not bool:
        raise Problem("请确认对账结果")
    obj.remote_id = string(data, "remote_id", 256) if found else ""
    obj.detail = string(data, "reason", 400)
    obj.state = "sent" if found else "absent"
    obj.save()
    audit(request.user, "delivery.reconcile." + obj.state, obj)
    return {"state": obj.state}
