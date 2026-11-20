import json
import os
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import User

from desk.discovery import BRAVE_URL, METRICS, X_URL, article_url
from desk.http import Problem
from desk.models import DiscoveryRun, Source
from .base import DeskCase


def request_data(platform="x", **changes):
    return {
        "request_id": str(uuid4()),
        "platform": platform,
        "query": "模型 AI",
        "limit": 10,
        **changes,
    }


def x_response():
    zero = dict.fromkeys(METRICS, 0)
    first = dict(id="10", author_id="1", text="模型 AI", public_metrics=zero)
    second = dict(
        id="20", author_id="2", text="AI", public_metrics={**zero, "like_count": 6}
    )
    third = dict(id="30", author_id="1", text="模型", public_metrics={"reply_count": 0})
    return json.dumps(
        {
            "data": [first, second, third, first],
            "meta": {"result_count": 4},
            "includes": {
                "users": [
                    {"id": "1", "username": "one"},
                    {"id": "2", "username": "two"},
                ]
            },
        }
    ).encode()


def wechat_response():
    url = "https://mp.weixin.qq.com/s/paper-A"
    entries = [
        {"url": url + "?scene=1", "title": "模型更新", "description": "AI 索引摘要"},
        {"url": url + "#copy", "title": "另一标题"},
        {"url": "https://mp.weixin.qq.com/s/paper-B", "title": "AI 随笔"},
        {"url": "https://mp.weixin.qq.com.evil.invalid/s/wrong", "title": "无关"},
        {"url": "https://mp.weixin.qq.com/manage", "title": "非文章"},
    ]
    return json.dumps(
        {
            "type": "search",
            "query": {"original": "site:mp.weixin.qq.com 模型 AI"},
            "web": {"results": entries},
        }
    ).encode()


@patch.dict(
    os.environ,
    {
        "PRESS_X_READ_TOKEN": "fixture",
        "PRESS_BRAVE_SEARCH_KEY": "fixture",
        "PRESS_X_ACCOUNTS": "",
        "PRESS_FEEDS": "{}",
    },
)
class DiscoveryTests(DeskCase):
    @patch("desk.discovery.fetch_bytes", return_value=x_response())
    def test_cross_author_sample_ranking_missing_metrics_and_capture(self, fetch):
        args = request_data()
        result = self.post("discovery/search", args)
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(fetch.call_args.args, (X_URL,))
        params = fetch.call_args.kwargs["params"]
        self.assertEqual(params["query"], '"模型" "AI" -is:retweet')
        self.assertEqual(params["max_results"], 10)
        self.assertEqual(params["sort_order"], "recency")
        self.assertIn("public_metrics", params["tweet.fields"])
        self.assertEqual(
            result["summary"],
            {
                "count": 3,
                "authors": 2,
                "median": 3,
                "measured": 2,
                "mentions": {"模型": 2, "AI": 2},
                "with_preview": 3,
            },
        )
        self.assertEqual([r["engagement"] for r in result["rows"]], [6, 0, None])
        self.post("discovery/search", args, 409)
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(DiscoveryRun.objects.get().count, 3)
        self.assertEqual(Source.objects.count(), 1)
        choice = {"ticket": result["rows"][0]["ticket"], "excerpt": "forged"}
        new = self.post("discovery/capture", choice)
        self.assertEqual(
            self.post("discovery/capture", choice), {"id": new["id"], "created": False}
        )
        saved = Source.objects.get(pk=new["id"])
        self.assertEqual(
            (saved.url, saved.byline, saved.excerpt),
            ("https://x.com/two/status/20", "two", "AI"),
        )

    @patch("desk.discovery.fetch_bytes", return_value=wechat_response())
    def test_wechat_index_and_explicit_original_evidence(self, fetch):
        result = self.post("discovery/search", request_data("wechat"))
        self.assertEqual(fetch.call_args.args, (BRAVE_URL,))
        params = fetch.call_args.kwargs["params"]
        self.assertEqual(
            (params["q"], params["freshness"], params["count"]),
            ("site:mp.weixin.qq.com 模型 AI", "pw", 10),
        )
        self.assertEqual(
            result["summary"],
            {"count": 2, "with_preview": 1, "mentions": {"模型": 1, "AI": 2}},
        )
        self.assertEqual(Source.objects.count(), 1)
        row = result["rows"][0]
        choice = {"ticket": row["ticket"]}
        self.post("discovery/capture", choice, 400)
        saved = self.post("discovery/capture", {**choice, "title": "核对的原文标题"})
        source = Source.objects.get(pk=saved["id"])
        self.assertEqual(
            (source.excerpt, source.url, source.published),
            ("", "https://mp.weixin.qq.com/s/paper-A", None),
        )
        self.post(
            "topics",
            {
                "quote": self.quote.pk,
                "confirmed": True,
                "title": "待查",
                "sources": [source.pk],
            },
            400,
        )
        self.post(
            "discovery/capture",
            {**choice, "title": source.title, "excerpt": "经核对的原文节选"},
        )
        source.refresh_from_db()
        self.assertEqual(source.excerpt, "经核对的原文节选")

    @patch("desk.discovery.fetch_bytes", return_value=wechat_response())
    def test_ticket_ownership_signature_expiry_and_access(self, fetch):
        ticket = self.post("discovery/search", request_data("wechat"))["rows"][0][
            "ticket"
        ]
        choice = {"ticket": ticket, "title": "已核对"}
        self.client.force_login(self.editor)
        self.post("discovery/capture", choice, 403)
        self.client.force_login(self.author)
        self.post("discovery/capture", {**choice, "ticket": ticket + "x"}, 400)
        with patch("desk.discovery.PREVIEW_SECONDS", -1):
            self.post("discovery/capture", choice, 400)
        self.client.force_login(User.objects.create_user("reader"))
        self.post("discovery/search", request_data(), 403)
        self.post("discovery/capture", choice, 403)
        self.client.logout()
        self.post("discovery/search", request_data(), 401)
        fetch.assert_called_once()

    @patch("desk.discovery.fetch_bytes")
    def test_empty_malformed_and_failed_receipts(self, fetch):
        for platform, empty in (
            ("x", {"meta": {"result_count": 0}}),
            ("wechat", {"type": "search", "query": {}, "web": None}),
        ):
            fetch.return_value = json.dumps(empty).encode()
            result = self.post("discovery/search", request_data(platform))
            self.assertEqual(result["summary"]["count"], 0)
            if platform == "x":
                self.assertIsNone(result["summary"]["median"])
            for malformed in (
                b"not JSON",
                b"{}",
                b'{"web":{"results":4},"type":"search"}',
            ):
                fetch.return_value = malformed
                self.post("discovery/search", request_data(platform), 502)
        fetch.side_effect = Problem("服务请求失败", 502)
        args = request_data()
        self.post("discovery/search", args, 502)
        self.post("discovery/search", args, 409)
        self.assertEqual(
            DiscoveryRun.objects.get(request_id=args["request_id"]).status, "failed"
        )
        self.assertEqual(DiscoveryRun.objects.filter(status="done", count=0).count(), 2)

    @patch("desk.discovery.fetch_bytes")
    def test_preflight_and_input_bounds(self, fetch):
        with patch.dict(
            os.environ, {"PRESS_X_READ_TOKEN": "", "PRESS_BRAVE_SEARCH_KEY": ""}
        ):
            for platform in ("wechat", "x"):
                self.post("discovery/search", request_data(platform), 503)
        for change in (
            {"platform": "unknown"},
            {"platform": "wechat", "limit": 50},
            {"limit": True},
            {"query": "from:someone"},
            {"query": "OR"},
            {"query": ""},
            {"request_id": "bad"},
        ):
            self.post("discovery/search", request_data(**change), 400)
        self.assertFalse(DiscoveryRun.objects.exists())
        fetch.assert_not_called()

    @patch("desk.discovery.fetch_bytes")
    def test_overlong_page_clipped_locally(self, fetch):
        entries = [
            {"title": "test", "url": f"https://mp.weixin.qq.com/s/paper{i}"}
            for i in range(24)
        ]
        fetch.return_value = json.dumps(
            {"type": "search", "query": {}, "web": {"results": entries}}
        ).encode()
        result = self.post("discovery/search", request_data("wechat", limit=20))
        self.assertEqual(len(result["rows"]), 20)

    def test_legacy_article_url_identity(self):
        base = "https://mp.weixin.qq.com/s"
        self.assertEqual(
            article_url(base + "?scene=1&idx=2&mid=22&__biz=Ab%3D&sn=ac#copy"),
            base + "?__biz=Ab%3D&mid=22&idx=2&sn=ac",
        )
        for link in (
            base + "?mid=22",
            base + "/%2Felse",
            base.replace("https:", "http:") + "/x",
            base.replace("mp.weixin.qq.com", "name@mp.weixin.qq.com") + "/x",
            base + "?__biz=a&mid=1&mid=2&idx=1",
            "https://[broken",
        ):
            self.assertIsNone(article_url(link))
