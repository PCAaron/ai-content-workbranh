import os
from datetime import timedelta
from unittest.mock import patch

import httpx
from django.utils.timezone import now

from desk.editorial import revise
from desk.models import Edition, Job, Revision
from desk.runner import recover, step

from .base import DeskCase


@patch.dict(
    os.environ,
    PRESS_MODEL_URL="https://example.org/chat",
    PRESS_MODEL="fixture",
    PRESS_MODEL_KEY="fixture",
)
class WritingTests(DeskCase):
    def submit(self, budget=2):
        return self.post(
            f"drafts/{self.draft.pk}/generate",
            {"base": 0, "budget": budget, "consent": True},
        )

    def test_feedback_loop_and_dedup(self):
        self.assertEqual(self.submit(), self.submit())
        with patch("desk.runner.generate", side_effect=["缺少证据", self.body]) as gen:
            self.assertTrue(step())
            job = Job.objects.get()
            self.assertEqual(job.state, "queued")
            self.assertIn("原话", job.detail)
            self.assertTrue(step())
            self.assertFalse(step())
            self.assertEqual(gen.call_count, 2)
        job.refresh_from_db()
        self.assertEqual(
            list(job.attempts.order_by("sequence").values_list("state", flat=True)),
            ["invalid", "valid"],
        )
        self.assertEqual(job.state, "done")
        self.assertEqual(Revision.objects.get().body, self.body)

    def test_budget_and_ambiguous_response(self):
        self.submit(1)
        with patch("desk.runner.generate", side_effect=httpx.ReadTimeout("test")):
            step()
            self.assertFalse(step())
        self.assertEqual(Job.objects.get().state, "unknown")
        self.assertEqual(self.submit()["state"], "unknown")

    def test_crash_recovery_no_double_spend(self):
        self.submit()
        job = Job.objects.get()
        job.attempts.create(sequence=1)
        Job.objects.update(state="running", updated=now() - timedelta(minutes=11))
        recover()
        self.assertFalse(step())
        self.assertEqual(job.attempts.get().state, "unknown")

    def test_conflict_retains_output(self):
        self.submit()
        revise(self.draft, 0, "人工先保存", "人工初稿", self.author)
        with patch("desk.runner.generate", return_value=self.body):
            step()
        job = Job.objects.get()
        self.assertEqual(job.state, "conflict")
        self.assertEqual(job.attempts.get().result, self.body)
        self.assertEqual(Revision.objects.get().body, "人工先保存")

    def test_stale_editor_approval_and_restore(self):
        path = f"drafts/{self.draft.pk}"
        self.ready()
        self.post(path + "/save", {"body": "续稿", "reason": "修改", "base": 1})
        self.post(path + "/save", {"body": "过期", "reason": "冲突", "base": 1}, 409)
        self.post(path + "/approve", {"base": 2}, 400)
        self.post(path + "/restore", {"version": 1, "base": 2})
        self.post(
            path + "/notes", {"version": 3, "anchor": "不存在", "text": "注"}, 400
        )
        self.post(
            path + "/notes", {"version": 3, "anchor": self.quote.text, "text": "确认"}
        )
        result = self.client.get("/api/" + path).json()
        self.assertEqual(result["version"], 3)
        self.assertIsNone(result["approved"])
        self.assertEqual(result["notes"][0]["revision__version"], 3)

    def test_channel_rewrite_and_budget(self):
        import json

        self.ready()
        ed = self.edition("xhs")
        data = {"base": 1, "version": 1, "consent": True, "budget": 2}
        self.post(f"editions/{ed}/generate", dict(data, sample=self.draft.pk), 400)
        self.post(f"editions/{ed}/generate", data)
        good = json.dumps(
            {"title": "如何核查", "body": self.body, "cards": ["导读", "出处"]}
        )
        with patch("desk.runner.generate", side_effect=["{}", good]):
            step()
            step()
        edition = Edition.objects.get()
        self.assertEqual(
            (edition.version, edition.cards, edition.approved),
            (2, ["导读", "出处"], False),
        )
        self.assertEqual(self.draft.revisions.count(), 1)
        self.assertEqual(Job.objects.get().state, "done")

    def test_exhausted_validation_marks_failed(self):
        self.submit(1)
        with patch("desk.runner.generate", return_value="无引用"):
            self.assertTrue(step())
            self.assertFalse(step())
        self.assertEqual(Job.objects.get().state, "failed")
