import json
import os
from unittest.mock import patch

from django.test import Client

from desk.http import Problem
from desk.intake import collect, feed_items
from desk.models import Cursor, Source

from .base import DeskCase


class AccessTests(DeskCase):
    def test_csrf_login_and_revoke(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.get("/api/library").status_code, 401)
        self.author.set_password("test-access-only")
        self.author.save()
        data = {"username": self.author.username, "password": "test-access-only"}
        self.assertEqual(
            client.post(
                "/api/login", data, content_type="application/json"
            ).status_code,
            403,
        )
        token = client.get("/api/session").json()["csrf"]
        r = client.post(
            "/api/login", data, content_type="application/json", HTTP_X_CSRFTOKEN=token
        )
        self.assertEqual(r.status_code, 200)
        self.assertNotEqual(token, r.json()["csrf"])
        self.author.is_active = False
        self.author.save()
        self.assertEqual(client.get("/api/library").status_code, 401)

    def test_limits_editor_and_invalid_json(self):
        self.post(f"drafts/{self.draft.pk}/approve", {"base": 1}, 403)
        self.assertEqual(self.client.get("/api/audit").status_code, 403)
        self.assertEqual(
            self.client.post(
                "/api/quotes", data="[]", content_type="application/json"
            ).status_code,
            400,
        )
        self.assertEqual(self.client.get("/health/ready").status_code, 200)

    def test_login_failed_attempts_are_persisted(self):
        for _ in range(8):
            self.post("login", {"username": "no-such-user", "password": "wrong"}, 401)
        self.post("login", {"username": "no-such-user", "password": "wrong"}, 429)


class IntakeTests(DeskCase):
    def test_manual_supplement_preserves_first_record(self):
        item = {
            "url": "https://EXAMPLE.org/story-2#a",
            "title": "Key",
            "origin": "微信公众号",
        }
        first = self.post("sources", item)
        second = self.post(
            "sources", dict(item, url="https://example.org/story-2", excerpt="补录")
        )
        self.assertEqual(first["id"], second["id"])
        self.assertFalse(second["created"])
        s = Source.objects.get(pk=first["id"])
        self.assertEqual(s.excerpt, "补录")
        self.assertIsNone(s.published)

    def test_evidence_gate_and_topic_open(self):
        self.post("quotes", {"text": "第三方", "locator": "一段"}, 400)
        self.client.force_login(self.editor)
        data = {
            "quote": self.quote.pk,
            "title": "角度",
            "sources": [self.source.pk],
            "confirmed": True,
        }
        self.post("topics", data, 403)
        self.client.force_login(self.author)
        self.post("topics", dict(data, sources=[999999]), 400)
        topic = self.post("topics", data)
        self.assertEqual(
            self.post("drafts/open", {"topic": topic["id"]}),
            self.post("drafts/open", {"topic": topic["id"]}),
        )

    def test_rss_atom_and_empty_dates(self):
        rss = b"<rss><channel><item><link>https://example.org/s</link><title>One</title></item></channel></rss>"
        self.assertEqual(len(list(feed_items(rss, "feed/test"))), 1)
        atom = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><link href="https://example.org/a"/><link rel="self" href="https://example.org/api"/><title>Atom</title></entry></feed>'
        self.assertEqual(
            list(feed_items(atom, "feed/test"))[0]["url"], "https://example.org/a"
        )
        with (
            patch.dict(os.environ, PRESS_FEEDS='{"test":"https://example.org/feed"}'),
            patch("desk.intake.fetch_bytes", return_value=rss),
        ):
            self.assertEqual(collect("feed/test", self.author)["added"], 1)
            self.assertEqual(collect("feed/test", self.author)["added"], 0)

    def test_x_pagination_is_per_account_and_atomic(self):
        def page(ids, token=""):
            return json.dumps(
                {
                    "meta": {"newest_id": ids[0], "next_token": token},
                    "data": [{"id": i, "text": "公共资料"} for i in ids],
                }
            ).encode()

        with (
            patch.dict(
                os.environ, PRESS_X_ACCOUNTS="a,b", PRESS_X_READ_TOKEN="fixture"
            ),
            patch("desk.intake.fetch_bytes") as fetch,
        ):
            fetch.side_effect = [
                page(["30", "29"], "page2"),
                b"{}",
                page(["28"]),
                page(["10"]),
                page(["40"]),
            ]
            self.assertTrue(collect("x/a", self.author)["more"])
            with self.assertRaises(Problem):
                collect("x/a", self.author)
            self.assertEqual(Cursor.objects.get(name="x/a").token, "page2")
            collect("x/a", self.author)
            self.assertEqual(fetch.call_args.kwargs["params"]["next_token"], "page2")
            collect("x/b", self.author)
            collect("x/a", self.author)
            self.assertEqual(fetch.call_args.kwargs["params"]["since_id"], "30")
            self.assertEqual(Cursor.objects.get(name="x/b").watermark, "10")
