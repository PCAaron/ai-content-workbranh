from django.contrib.auth.models import Group, User
from django.test import TestCase

from desk.editorial import revise
from desk.models import Draft, Quote, Source, Topic


class DeskCase(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("writer")
        self.editor = User.objects.create_user("other")
        self.reviewer = User.objects.create_user("chief")
        editors = Group.objects.create(name="editor")
        editors.user_set.add(self.author, self.editor)
        self.reviewer.groups.add(Group.objects.create(name="reviewer"))
        self.client.force_login(self.author)
        self.source = Source.objects.create(
            url="https://example.org/story",
            origin="RSS",
            title="资料",
            excerpt="公开资料节选",
        )
        self.quote = Quote.objects.create(
            author=self.author, text="我需要看到证据。", locator="测试笔记"
        )
        self.topic = Topic.objects.create(title="如何查证", quote=self.quote)
        self.topic.sources.add(self.source)
        self.draft = Draft.objects.create(topic=self.topic)
        self.body = f"我需要看到证据。\n\n公开资料节选 [S{self.source.pk}]"

    def post(self, path, body=None, status=200):
        r = self.client.post(
            "/api/" + path,
            data={} if body is None else body,
            content_type="application/json",
        )
        self.assertEqual(r.status_code, status, r.content[:500])
        return (
            r.json() if r.get("Content-Type", "").startswith("application/json") else r
        )

    def ready(self):
        revise(self.draft, 0, self.body, "初稿", self.author)
        self.client.force_login(self.reviewer)
        self.post(f"drafts/{self.draft.pk}/approve", {"base": 1})

    def edition(self, platform="x"):
        return self.post(
            f"drafts/{self.draft.pk}/compile", {"platform": platform, "base": 1}
        )["id"]
