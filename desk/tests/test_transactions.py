from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth.models import User
from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from desk.editorial import revise
from desk.http import Problem
from desk.models import Draft, Quote, Topic


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
