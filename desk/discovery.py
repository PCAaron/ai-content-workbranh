"""One explicit, bounded search of a public topic. Provider previews are ephemeral."""

import json
import os
import re
from statistics import median
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import UUID

from django.core import signing
from django.db import transaction

from .http import Problem, endpoint, string
from .intake import date, fetch_bytes, record
from .models import DiscoveryRun

X_URL = "https://api.x.com/2/tweets/search/recent"
BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"
LIMITS = {"x": (10, 20, 50), "wechat": (10, 20)}
KEYS = {"x": "PRESS_X_READ_TOKEN", "wechat": "PRESS_BRAVE_SEARCH_KEY"}
METRICS = ("like_count", "retweet_count", "reply_count", "quote_count")
SIGNING_SALT = "desk.topic-discovery.v1"
PREVIEW_SECONDS = 1800


def keywords(value):
    terms = list(dict.fromkeys(value.split()))
    if not 1 <= len(terms) <= 5 or any(
        not re.fullmatch(r"[\w]+(?:[.-][\w]+)*", term)
        or len(term) > 40
        or term.upper() in {"AND", "OR", "NOT"}
        for term in terms
    ):
        raise Problem("请输入 1–5 个用空格分隔的主题词，每词最多 40 字")
    return terms


def x_sample(terms, limit, key):
    query = " ".join(f'"{term}"' for term in terms) + " -is:retweet"
    page = json.loads(
        fetch_bytes(
            X_URL,
            params={
                "query": query,
                "max_results": limit,
                "sort_order": "recency",
                "expansions": "author_id",
                "user.fields": "username",
                "tweet.fields": "created_at,author_id,public_metrics",
            },
            headers={"Authorization": "Bearer " + key},
        )
    )
    count = page["meta"]["result_count"]
    posts = page.get("data", [])
    if (
        page.get("errors")
        or type(count) is not int
        or not isinstance(posts, list)
        or count != len(posts)
    ):
        raise ValueError
    users = {u["id"]: u["username"] for u in page.get("includes", {}).get("users", [])}
    seen = set()
    results = []
    for post in posts[:limit]:
        post_id = post["id"]
        body = post["text"].strip()
        if not re.fullmatch(r"[0-9]{1,22}", post_id) or not body:
            raise ValueError
        if post_id in seen:
            continue
        seen.add(post_id)
        author = post.get("author_id") or ""
        handle = users.get(author, "")
        if handle and not re.fullmatch(r"[A-Za-z0-9_]{1,15}", handle):
            raise ValueError
        raw = post.get("public_metrics") or {}
        metrics = {name: raw.get(name) for name in METRICS}
        for n in metrics.values():
            if n is not None and (type(n) is not int or n < 0):
                raise ValueError
        published = post.get("created_at") or ""
        if published:
            date(published)
        results.append(
            {
                "url": f"https://x.com/{handle or 'i/web'}/status/{post_id}",
                "title": body[:120],
                "preview": body[:12000],
                "byline": handle,
                "author_id": author,
                "published": published,
                "metrics": metrics,
                "engagement": (
                    sum(metrics.values()) if None not in metrics.values() else None
                ),
            }
        )
    results.sort(key=lambda row: (row["engagement"] is None, -(row["engagement"] or 0)))
    return results


def article_url(value):
    if (
        not isinstance(value, str)
        or len(value) > 2048
        or re.search(r"[\s\\\x00-\x1f]", value)
    ):
        return None
    try:
        parts = urlsplit(value)
        if parts.scheme != "https" or parts.netloc.lower() != "mp.weixin.qq.com":
            return None
        base = "https://mp.weixin.qq.com" + parts.path
        if re.fullmatch(r"/s/[A-Za-z0-9_-]+", parts.path):
            return base
        if parts.path != "/s":
            return None
        query = parse_qs(parts.query, max_num_fields=60)
        allowed = {
            "__biz": r"[A-Za-z0-9+/=_-]+",
            "mid": r"[0-9]+",
            "idx": r"[0-9]+",
            "sn": r"[A-Za-z0-9]+",
        }
        ids = {}
        for field, pattern in allowed.items():
            if field in query:
                values = query[field]
                if len(values) != 1 or not re.fullmatch(pattern, values[0]):
                    return None
                ids[field] = values[0]
        if {"__biz", "mid", "idx"} <= ids.keys():
            return base + "?" + urlencode(ids)
    except ValueError:
        pass
    return None


def wechat_sample(terms, limit, key):
    page = json.loads(
        fetch_bytes(
            BRAVE_URL,
            params={
                "q": "site:mp.weixin.qq.com " + " ".join(terms),
                "count": limit,
                "freshness": "pw",
                "result_filter": "web",
                "text_decorations": "false",
                "spellcheck": "false",
                "country": "ALL",
                "search_lang": "zh-hans",
            },
            headers={"X-Subscription-Token": key, "Accept": "application/json"},
        )
    )
    if page.get("type") != "search" or page.get("error"):
        raise ValueError
    entries = page["web"]["results"] if page.get("web") is not None else []
    if not isinstance(entries, list):
        raise ValueError
    rows = []
    seen = set()
    for entry in entries[:limit]:
        url = article_url(entry["url"])
        title = entry.get("title") or ""
        if not url or not title.strip() or url in seen:
            continue
        seen.add(url)
        rows.append(
            {
                "url": url,
                "title": title.strip()[:300],
                "preview": (entry.get("description") or "").strip()[:2000],
            }
        )
    return rows


def analyze(rows, terms, platform):
    texts = [(r["title"] + "\n" + r["preview"]).casefold() for r in rows]
    summary = {
        "count": len(rows),
        "with_preview": sum(bool(r["preview"]) for r in rows),
        "mentions": {t: sum(t.casefold() in text for text in texts) for t in terms},
    }
    if platform == "x":
        totals = [r["engagement"] for r in rows if r["engagement"] is not None]
        summary.update(
            authors=len({r["author_id"] for r in rows if r["author_id"]}),
            measured=len(totals),
            median=median(totals) if totals else None,
        )
    return summary


def ticket(actor, platform, row):
    source = {"url": row["url"]}
    if platform == "x":
        source.update(
            title=row["title"],
            origin="X",
            excerpt=row["preview"],
            byline=row["byline"],
            published=row["published"],
        )
    return signing.dumps(
        {"user": actor.pk, "platform": platform, "source": source},
        salt=SIGNING_SALT,
        compress=True,
    )


@endpoint("POST")
def search(request, data):
    platform = string(data, "platform", 10)
    limit = data.get("limit")
    if (
        platform not in LIMITS
        or type(limit) is not int
        or limit not in LIMITS[platform]
    ):
        raise Problem("不支持的平台或样本上限")
    terms = keywords(string(data, "query", 120))
    try:
        request_id = UUID(string(data, "request_id", 36))
    except ValueError:
        raise Problem("需要有效的请求号")
    key = os.getenv(KEYS[platform], "").strip()
    if not key:
        raise Problem("部署端尚未配置 " + KEYS[platform], 503)
    receipt, created = DiscoveryRun.objects.get_or_create(
        request_id=request_id,
        defaults={"actor": request.user, "platform": platform, "limit": limit},
    )
    if not created:
        raise Problem("该请求号已经使用。重新检索会消耗新额度。", 409)
    try:
        rows = (x_sample if platform == "x" else wechat_sample)(terms, limit, key)
        summary = analyze(rows, terms, platform)
        for row in rows:
            row["ticket"] = ticket(request.user, platform, row)
    except (TypeError, ValueError, KeyError, AttributeError, Problem) as exc:
        receipt.status = "failed"
        receipt.save(update_fields=["status"])
        if isinstance(exc, Problem) and exc.status == 502:
            raise
        raise Problem("检索服务返回的样本无法核验", 502) from exc
    receipt.status = "done"
    receipt.count = len(rows)
    receipt.save(update_fields=["status", "count"])
    return {
        "platform": platform,
        "query": " ".join(terms),
        "limit": limit,
        "observed": receipt.started,
        "summary": summary,
        "rows": rows,
    }


@endpoint("POST")
@transaction.atomic
def capture(request, data):
    token = string(data, "ticket", 100000)
    try:
        payload = signing.loads(token, salt=SIGNING_SALT, max_age=PREVIEW_SECONDS)
    except signing.BadSignature:
        raise Problem("候选已过期或无效，请重新检索", 400)
    if payload["user"] != request.user.pk:
        raise Problem("候选属于其他编辑", 403)
    source = payload["source"]
    if payload["platform"] == "wechat":
        source.update(
            origin="微信公众号",
            title=string(data, "title", 300),
            excerpt=string(data, "excerpt", 12000, optional=True),
        )
    pk, created = record(source, request.user)
    return {"id": pk, "created": created}
