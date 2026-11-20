import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import Group, User
from django.db import close_old_connections, connection
from django.test import Client, TransactionTestCase

from desk.editorial import revise
from desk.http import Problem
from desk.models import DiscoveryRun, Draft, Quote, Topic


@skipUnless(
    connection.vendor == "postgresql", "requires independent PostgreSQL sessions"
)
class ConcurrentEditors(TransactionTestCase):
    def test_only_one_conditional_write_wins(self):
        user = User.objects.create_user("fixture")
        quote = Quote.objects.create(author=user, text="观点", locator="定位")
        draft = Draft.objects.create(
            topic=Topic.objects.create(title="事务", quote=quote)
        )
        gate = Barrier(2)

        def save(body):
            close_old_connections()
            try:
                local = Draft.objects.get(pk=draft.pk)
                gate.wait(timeout=10)
                revise(local, 0, body, "同时保存", "fixture")
            except Problem as exc:
                return exc.status
            finally:
                close_old_connections()
            return 200

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(
                sorted(pool.map(save, ["编辑者甲", "编辑者乙"])), [200, 409]
            )
        draft.refresh_from_db()
        self.assertEqual(draft.version, 1)
        self.assertEqual(draft.revisions.count(), 1)

    @patch.dict(os.environ, {"PRESS_X_READ_TOKEN": "fixture"})
    @patch("desk.discovery.fetch_bytes", return_value=b'{"meta":{"result_count":0}}')
    def test_same_discovery_request_calls_provider_once(self, fetch):
        user = User.objects.create_user("discovery")
        user.groups.add(Group.objects.create(name="editor"))
        clients = [Client(), Client()]
        for client in clients:
            client.force_login(user)
        data = {
            "request_id": str(uuid4()),
            "platform": "x",
            "query": "模型",
            "limit": 10,
        }
        gate = Barrier(2)

        def search(client):
            close_old_connections()
            try:
                gate.wait(timeout=10)
                return client.post(
                    "/api/discovery/search", data, content_type="application/json"
                ).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(search, clients)), [200, 409])
        fetch.assert_called_once()
        self.assertEqual(DiscoveryRun.objects.get().status, "done")
