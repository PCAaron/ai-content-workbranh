import json
import os
import re
from datetime import timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit

import httpx
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from django.db import transaction
from django.db.models import Q
from django.utils.dateparse import parse_datetime

from .http import Problem, audit, endpoint, number, string
from .models import Cursor, Quote, Source, Topic


def link(value):
    try:
        parts = urlsplit(value)
        if (
            parts.scheme not in {"https", "http"}
            or not parts.hostname
            or parts.username
            or parts.password
            or any(char.isspace() or ord(char) < 32 for char in value)
            or "\\" in value
        ):
            raise ValueError
        _ = parts.port
    except ValueError:
        raise Problem("需要有效的 http(s) 原文地址")
    return urlunsplit(
        (parts.scheme, parts.netloc.lower(), parts.path or "/", parts.query, "")
    )


def date(value):
    if not value:
        return None
    try:
        when = parse_datetime(value) or parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        when = None
    if not when or not when.tzinfo:
        raise Problem("原文时间需带时区")
    return when.astimezone(timezone.utc)


def record(data, user):
    url = link(string(data, "url", 2048))
    values = dict(
        title=string(data, "title", 300),
        origin=string(data, "origin", 40),
        byline=string(data, "byline", 150, optional=True),
        excerpt=string(data, "excerpt", 12000, optional=True),
        published=date(string(data, "published", 80, optional=True)),
    )
    source, created = Source.objects.get_or_create(url=url, defaults=values)
    if created:
        audit(user, "source.add", source)
    elif values["excerpt"] and Source.objects.filter(pk=source.pk, excerpt="").update(
        excerpt=values["excerpt"]
    ):
        audit(user, "source.supplement", source)
    return source.pk, created


@endpoint("POST")
@transaction.atomic
def add_source(request, data):
    pk, created = record(data, request.user)
    return {"id": pk, "created": created}


@endpoint("POST")
@transaction.atomic
def add_quote(request, data):
    if data.get("confirmed") is not True:
        raise Problem("请确认是你本人且授权使用的原话")
    obj = Quote.objects.create(
        author=request.user,
        text=string(data, "text", 3000),
        locator=string(data, "locator", 300),
    )
    audit(request.user, "quote.confirm", obj)
    return {"id": obj.pk}


@endpoint("POST")
@transaction.atomic
def add_topic(request, data):
    quote = Quote.objects.get(pk=number(data, "quote"))
    if quote.author_id != request.user.pk or data.get("confirmed") is not True:
        raise Problem("选题需要原话作者确认", 403)
    ids = data.get("sources")
    if (
        not isinstance(ids, list)
        or not 1 <= len(ids) <= 12
        or any(type(i) is not int or not 0 < i < 2**63 for i in ids)
    ):
        raise Problem("请选 1–12 条外部证据")
    sources = list(Source.objects.filter(pk__in=ids).exclude(excerpt=""))
    if len(sources) != len(set(ids)):
        raise Problem("有来源缺少节选或不存在")
    obj = Topic.objects.create(title=string(data, "title", 300), quote=quote)
    obj.sources.set(sources)
    audit(request.user, "topic.confirm", obj)
    return {"id": obj.pk}


def source_config():
    try:
        feeds = json.loads(os.getenv("PRESS_FEEDS", "{}"))
        if not isinstance(feeds, dict) or any(
            not isinstance(k, str)
            or len(k) > 110
            or not isinstance(v, str)
            or urlsplit(v).scheme != "https"
            for k, v in feeds.items()
        ):
            raise ValueError
        handles = [
            x.strip() for x in os.getenv("PRESS_X_ACCOUNTS", "").split(",") if x.strip()
        ]
        if any(not re.fullmatch(r"[A-Za-z0-9_]{1,15}", x) for x in handles):
            raise ValueError
        return {
            **{"feed/" + k: v for k, v in feeds.items()},
            **{"x/" + h: h for h in handles},
        }
    except (ValueError, TypeError):
        raise Problem("采集配置格式有误", 503)


def fetch_bytes(url, **kwargs):
    try:
        with httpx.stream(
            "GET", url, timeout=12, follow_redirects=False, **kwargs
        ) as response:
            response.raise_for_status()
            body = bytearray()
            for block in response.iter_bytes(65536):
                body.extend(block)
                if len(body) > 2_000_000:
                    raise Problem("响应超过 2 MB", 502)
            return bytes(body)
    except httpx.HTTPError:
        raise Problem("信源请求失败，请检查授权、配额或订阅地址", 502)


def feed_items(body, name):
    try:
        root = ElementTree.fromstring(body)
    except (ElementTree.ParseError, DefusedXmlException):
        raise Problem("订阅 XML 无法解析", 502)
    if root.tag.split("}")[-1] not in {"rss", "feed", "RDF"}:
        raise Problem("订阅响应格式不受支持", 502)
    for item in [*root.findall(".//{*}entry"), *root.findall(".//{*}item")][:150]:
        parts = {child.tag.split("}")[-1]: child for child in item}

        def field(*names):
            return next(
                (
                    "".join(parts[key].itertext()).strip()
                    for key in names
                    if key in parts
                ),
                "",
            )

        address = next(
            (
                child.get("href") or (child.text or "").strip()
                for child in item
                if child.tag.split("}")[-1] == "link"
                and child.get("rel", "alternate") == "alternate"
            ),
            "",
        )
        if not address or not field("title"):
            continue
        # Keep excerpts as text; React and export renderers escape markup.
        yield dict(
            url=address,
            title=field("title")[:300],
            excerpt=field("summary", "description", "content")[:12000],
            byline=field("creator", "author")[:150],
            origin=name[:40],
            published=field("pubDate", "published", "updated"),
        )


def collect(name, user):
    target = source_config().get(name)
    if not target:
        raise Problem("未知信源", 404)
    cursor, _ = Cursor.objects.get_or_create(name=name)
    token = pending = watermark = ""
    if name.startswith("feed/"):
        items = list(feed_items(fetch_bytes(target), name))
    else:
        key = os.getenv("PRESS_X_READ_TOKEN")
        if not key:
            raise Problem("尚未配置 X 读取凭证", 503)
        params = {
            "query": f"from:{target} -is:retweet",
            "tweet.fields": "created_at",
            "max_results": 100,
        }
        if cursor.watermark:
            params["since_id"] = cursor.watermark
        if cursor.token:
            params["next_token"] = cursor.token
        try:
            page = json.loads(
                fetch_bytes(
                    "https://api.x.com/2/tweets/search/recent",
                    params=params,
                    headers={"Authorization": "Bearer " + key},
                )
            )
            if page.get("errors") or "meta" not in page:
                raise ValueError
            posts = page.get("data", [])
            items = [
                dict(
                    url=f"https://x.com/{target}/status/{p['id']}",
                    title=p["text"][:120],
                    excerpt=p["text"],
                    byline=target,
                    origin="X",
                    published=p.get("created_at", ""),
                )
                for p in posts
            ]
            token = page["meta"].get("next_token", "")
            pending = cursor.pending or page["meta"].get("newest_id", "")
            watermark = cursor.watermark if token else pending or cursor.watermark
        except (KeyError, TypeError, ValueError, AttributeError):
            raise Problem("X 返回了无法确认的结果，水位已保留", 502)
    with transaction.atomic():
        if not Cursor.objects.filter(pk=cursor.pk, version=cursor.version).update(
            version=cursor.version + 1,
            watermark=watermark,
            pending=pending if token else "",
            token=token,
        ):
            raise Problem("另一轮采集已完成，请刷新", 409)
        added = sum(record(item, user)[1] for item in items)
        audit(user, "source.collect", cursor)
    return {"added": added, "received": len(items), "more": bool(token)}


@endpoint("POST")
def pull(request, data):
    return collect(string(data, "name", 128), request.user)


def window(request, query):
    try:
        before = int(request.GET.get("before", 2**63 - 1))
        if not 0 < before < 2**63:
            raise ValueError
    except ValueError:
        raise Problem("无效分页位置")
    return query.filter(pk__lt=before).order_by("-pk")[:60]


@endpoint("GET")
def library(request, data):
    term = request.GET.get("q", "")[:200]
    sources = window(
        request,
        Source.objects.filter(Q(title__icontains=term) | Q(excerpt__icontains=term)),
    )
    quotes = window(
        request, Quote.objects.select_related("author").filter(text__icontains=term)
    )
    topics = window(
        request, Topic.objects.filter(title__icontains=term).prefetch_related("sources")
    )
    return {
        "sources": list(sources.values()),
        "quotes": [
            {
                "id": q.pk,
                "text": q.text,
                "locator": q.locator,
                "author": q.author.username,
            }
            for q in quotes
        ],
        "topics": [
            {
                "id": t.pk,
                "title": t.title,
                "quote": t.quote_id,
                "sources": [s.pk for s in t.sources.all()],
            }
            for t in topics
        ],
        "feeds": list(source_config()),
    }
