from desk.editorial import revise
from desk.learning import apply_rules, current_rules
from desk.models import Draft, Topic

from .base import DeskCase


class LearningTests(DeskCase):
    def pair(self, title, old, new):
        topic = Topic.objects.create(title=title, quote=self.quote)
        topic.sources.add(self.source)
        draft = Draft.objects.create(topic=topic)
        revise(draft, 0, old, "人工起稿", self.author)
        return revise(draft, 1, new, "让表述更直接", self.author)

    def setUp(self):
        super().setUp()
        self.train = self.pair("训练稿", "总体而言需要核实", "具体来说需要核实")
        self.test = self.pair("独立稿", "总体而言航班有变化", "具体来说航班有变化")
        self.rule = self.post(
            "rules", {"training": self.train.pk, "old": "总体而言", "new": "具体来说"}
        )["id"]
        self.path = f"rules/{self.rule}/"

    def test_independent_eval_role_and_rollback(self):
        self.post(self.path + "evaluate", {"examples": [self.train.pk]}, 400)
        self.assertTrue(
            self.post(self.path + "evaluate", {"examples": [self.test.pk]})["pass"]
        )
        self.post(self.path + "activate", {}, 403)
        self.client.force_login(self.reviewer)
        self.post(self.path + "activate")
        inputs = {"quote": "总体而言作者原话", "rules": current_rules()}
        self.assertEqual(
            apply_rules("总体而言，例子：总体而言作者原话 [S3]", inputs),
            "具体来说，例子：总体而言作者原话 [S3]",
        )
        self.post(self.path + "rollback", {"epoch": 1})
        self.assertEqual(current_rules(), [])
        self.assertTrue(inputs["rules"])

    def test_regression_in_one_sample_blocks_promotion(self):
        other = self.pair("反例", "总体而言信息还少", "总体而言信息很少")
        self.assertFalse(
            self.post(self.path + "evaluate", {"examples": [self.test.pk, other.pk]})[
                "pass"
            ]
        )
        self.client.force_login(self.reviewer)
        self.post(self.path + "activate", {}, 409)

    def test_identical_text_in_different_article_is_not_held_out(self):
        twin = self.pair("副本", "总体而言需要核实", "具体来说需要核实")
        self.post(self.path + "evaluate", {"examples": [twin.pk]}, 400)

    def test_baseline_change_invalidates_outstanding_eval(self):
        other = self.post(
            "rules", {"training": self.train.pk, "old": "总体而言", "new": "具体来说"}
        )["id"]
        for pk in (other, self.rule):
            self.post(f"rules/{pk}/evaluate", {"examples": [self.test.pk]})
        self.client.force_login(self.reviewer)
        self.post(self.path + "activate")
        self.post(f"rules/{other}/activate", {}, 409)
