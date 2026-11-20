import io
import os
from unittest.mock import patch
from zipfile import ZipFile

import httpx
from PIL import Image

from desk.models import Delivery

from .base import DeskCase


class ChannelTests(DeskCase):
    def setUp(self):
        super().setUp()
        self.ready()

    def test_all_formats_and_reapproval(self):
        for platform in ("wechat", "x", "zsxq", "xhs"):
            with self.subTest(platform=platform):
                ed = self.edition(platform)
                p = f"editions/{ed}/"
                self.post(p + "download", {"version": 1}, 409)
                self.post(p + "approve", {"version": 1})
                exported = self.post(p + "download", {"version": 1})
                if platform == "xhs":
                    z = ZipFile(io.BytesIO(exported.content))
                    self.assertIn("caption.txt", z.namelist())
                    self.assertEqual(
                        Image.open(io.BytesIO(z.read("01.png"))).size, (1080, 1440)
                    )
                else:
                    self.assertIn(self.source.url, exported.content.decode())
                self.post(
                    p + "save",
                    {
                        "version": 1,
                        "title": "编辑稿",
                        "body": "经过修改",
                        "cards": ["可编辑"],
                    },
                )
                self.post(p + "download", {"version": 2}, 409)
                self.post(p + "approve", {"version": 1}, 409)

    def test_stale_channels_cannot_leave_workspace(self):
        ed = self.edition()
        p = f"editions/{ed}/"
        self.post(p + "approve", {"version": 1})
        self.post(
            f"drafts/{self.draft.pk}/save",
            {"base": 1, "body": "新母稿", "reason": "更正"},
        )
        self.post(p + "download", {"version": 1}, 409)
        self.post(p + "deliver", {"version": 1, "consent": True}, 409)

    @patch.dict(os.environ, PRESS_X_DRAFT_TOKEN="fixture")
    def test_uncertain_delivery_dedup_and_reconcile(self):
        ed = self.edition()
        p = f"editions/{ed}/"
        self.post(p + "approve", {"version": 1})
        with patch(
            "desk.channels.create_remote", side_effect=httpx.ReadTimeout("interrupted")
        ) as adapter:
            first = self.post(p + "deliver", {"version": 1, "consent": True})
            second = self.post(p + "deliver", {"version": 1, "consent": True})
            self.assertEqual(first["state"], "unknown")
            self.assertEqual(second["id"], first["id"])
            self.assertEqual(adapter.call_count, 1)
        self.post(
            f"deliveries/{first['id']}/reconcile",
            {"found": True, "reason": "后台人工核对", "remote_id": "draft123"},
        )
        self.assertEqual(
            self.post(p + "deliver", {"version": 1, "consent": True})["remote_id"],
            "draft123",
        )

    def test_config_and_consent_precede_external_io(self):
        ed = self.edition("zsxq")
        p = f"editions/{ed}/"
        self.post(p + "approve", {"version": 1})
        self.post(p + "deliver", {"version": 1}, 400)
        self.post(p + "deliver", {"version": 1, "consent": True}, 409)
        self.assertFalse(Delivery.objects.exists())

    def test_official_http_payloads_only_target_drafts(self):
        import json

        from desk.channels import create_remote

        calls = []

        def handler(req):
            calls.append((req.url.path, req.content))
            if "token" in req.url.path:
                return httpx.Response(200, json={"access_token": "test"})
            if "weixin" in req.url.host:
                return httpx.Response(200, json={"media_id": "wx1"})
            return httpx.Response(201, json={"data": {"id": "x1"}})

        client_factory = httpx.Client

        def client(**kwargs):
            return client_factory(transport=httpx.MockTransport(handler), **kwargs)

        snapshot = {"title": "稿", "body": "<b>资料</b>", "sources": "[S1]"}
        with patch("desk.channels.httpx.Client", side_effect=client):
            self.assertEqual(create_remote("x", snapshot, {"token": "test"}), "x1")
            self.assertEqual(
                create_remote(
                    "wechat",
                    snapshot,
                    {"app": "id", "secret": "test", "cover": "cover"},
                ),
                "wx1",
            )
        self.assertEqual(
            [p for p, _ in calls],
            ["/2/articles/draft", "/cgi-bin/token", "/cgi-bin/draft/add"],
        )
        self.assertIn("&lt;b&gt;", json.loads(calls[-1][1])["articles"][0]["content"])
