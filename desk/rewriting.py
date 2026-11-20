import json
import re

from django.db import transaction

from . import channels
from .http import Problem, number, string
from .models import Draft

DIRECTIONS = {
    "wechat": "先以导语交代真实变化，再用小标题组织事实、作者判断与具体例子，结尾说明读者可以怎样使用这些信息。",
    "x": "第一段作为独立可读的开篇，直接给出有依据的判断。后续以短段展开证据与限制，适配 X Articles。",
    "zsxq": "面向已经熟悉作者的社群，说明实践中的取舍与具体经验，结尾提出一个和证据有关的开放问题。",
    "xhs": "输出不超20字的具体标题、不超1000字的配文与1–9张要点卡，每张最多160字。每张卡只讲一件事。",
}


def attach_sample(inputs, draft, data):
    if not data.get("sample"):
        return
    sample = (
        Draft.objects.filter(
            pk=number(data, "sample"),
            topic__quote__author_id=draft.topic.quote.author_id,
        )
        .exclude(pk=draft.pk)
        .first()
    )
    if not sample or not sample.version or sample.approved != sample.version:
        raise Problem("请选择同作者、已审核的其他母稿")
    inputs["style_sample"] = {
        "draft": sample.pk,
        "version": sample.version,
        "excerpt": sample.revisions.get(version=sample.version).body[:3500],
    }


def validate_answer(answer, job):
    try:
        obj = json.loads(answer)
        if not isinstance(obj, dict):
            raise ValueError
    except ValueError:
        raise Problem("请仅返回一个包含 title、body、cards 的 JSON 对象")
    key = job.inputs["platform"]
    title = string(obj, "title", 20 if key == "xhs" else 300)
    body = string(obj, "body", 1000 if key == "xhs" else 40000)
    ids = {str(s["id"]) for s in job.inputs["sources"]}
    cites = set(re.findall(r"\[S(\d+)\]", body))
    if not cites or cites - ids:
        raise Problem("渠道正文需使用真实来源编号 [S数字]")
    cards = obj.get("cards", [])
    if key == "xhs" and (
        not isinstance(cards, list)
        or not 1 <= len(cards) <= 9
        or any(not isinstance(c, str) or not c.strip() or len(c) > 160 for c in cards)
    ):
        raise Problem("请提供 1–9 张图卡，每张 1–160 字")
    return {"title": title, "body": body, "cards": cards if key == "xhs" else []}


@transaction.atomic
def save_answer(job, result):
    item = channels.locked_edition(job.edition_id, {"version": job.edition_version})
    for k, v in result.items():
        setattr(item, k, v)
    item.version += 1
    item.approved = False
    item.save()
    channels.audit(job.actor, "edition.model_rewrite", item)
