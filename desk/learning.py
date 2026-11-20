import re
from difflib import SequenceMatcher

from django.db import transaction

from .http import Problem,audit,endpoint,number,string
from .models import Profile,Revision,Rule


def profile(locked=False):
    query=Profile.objects.select_for_update() if locked else Profile.objects
    return query.get_or_create(pk=1)[0]


def chain(active):
    rules=[]
    while active:
        rules.append({"id":active.pk,"old":active.old,"new":active.new})
        active=active.parent
    return rules[::-1]


def current_rules():
    return chain(profile().active)


def apply_rules(body,inputs):
    if not inputs.get("rules"):
        return body
    protected=r"("+re.escape(inputs["quote"])+r"|\[S\d+\]|https?://\S+)"
    parts=re.split(protected,body)
    for index in range(0,len(parts),2):
        for rule in inputs["rules"]:
            parts[index]=parts[index].replace(rule["old"],rule["new"])
    return "".join(parts)


def revision_pair(pk):
    after=Revision.objects.select_related("draft__topic__quote").get(pk=pk)
    if after.version<2 or after.reason=="模型起稿，待人工核对":
        raise Problem("请选择人工修改且有前版的修订")
    before=Revision.objects.get(draft=after.draft,version=after.version-1)
    if max(len(before.body),len(after.body))>8000:
        raise Problem("此文超出措辞评测 8000 字上限")
    return before,after


@endpoint("GET")
def overview(request,data):
    state=profile()
    pairs=Revision.objects.filter(version__gte=2).exclude(reason="模型起稿，待人工核对").order_by("-id")
    return {"active":state.active_id,"epoch":state.epoch,"rules":list(Rule.objects.order_by("-id").values()[:100]),
            "pairs":list(pairs.values("id","draft_id","draft__topic__title","version","reason")[:150])}


@endpoint("GET")
def suggest(request,data,pk):
    before,after=revision_pair(pk)
    options=[]
    for op,a,b,c,d in SequenceMatcher(None,before.body,after.body).get_opcodes():
        if op=="replace" and 0<b-a<=120 and 0<d-c<=120:
            options.append({"old":before.body[a:b],"new":after.body[c:d]})
    return {"reason":after.reason,"options":options[:12],"before":before.body,"after":after.body}


@endpoint("POST")
@transaction.atomic
def propose(request,data):
    before,after=revision_pair(number(data,"training"))
    old,new=string(data,"old",120),string(data,"new",120)
    if old==new or old not in before.body or new not in after.body or before.body.count(old)<=after.body.count(old) or after.body.count(new)<=before.body.count(new):
        raise Problem("候选措辞必须有实际改稿差异支持")
    item=Rule.objects.create(training=after,old=old,new=new,reason=after.reason)
    audit(request.user,"rule.propose",item)
    return {"id":item.pk}


@endpoint("POST")
@transaction.atomic
def evaluate(request,data,pk):
    state=profile(True)
    rule=Rule.objects.select_for_update().get(pk=pk)
    if rule.status not in ("candidate","evaluated"):
        raise Problem("只能评测候选规则",409)
    examples=data.get("examples")
    if not isinstance(examples,list) or not 1<=len(examples)<=12 or any(type(i) is not int or not 0<i<2**63 for i in examples):
        raise Problem("请选择 1–12 篇独立修订样本")
    used={rule.training.draft_id}
    past=chain(state.active)
    candidate=past+[{"old":rule.old,"new":rule.new}]
    scores=[]
    train_before,train_after=revision_pair(rule.training_id)
    seen_text={train_before.body.strip(),train_after.body.strip()}
    for sample in examples:
        before,after=revision_pair(sample)
        if after.draft_id in used or {before.body.strip(),after.body.strip()} & seen_text:
            raise Problem("评测文章与文本须独立于训练稿及其他留出稿")
        used.add(after.draft_id)
        seen_text.update([before.body.strip(),after.body.strip()])
        def score(rules):
            text=apply_rules(before.body,{"quote":after.draft.topic.quote.text,"rules":rules})
            return round(SequenceMatcher(None,text,after.body).ratio(),6)
        scores.append({"revision":sample,"draft":after.draft_id,"baseline":score(past),"candidate":score(candidate)})
    rule.parent_id=state.active_id
    rule.baseline_epoch=state.epoch
    rule.evaluation=scores
    rule.status="evaluated"
    rule.save()
    audit(request.user,"rule.evaluate",rule)
    return {"scores":scores,"pass":passes(scores)}


def passes(scores):
    return bool(scores) and all(s["candidate"]>=s["baseline"] for s in scores) and any(s["candidate"]>s["baseline"] for s in scores)


@endpoint("POST","reviewer")
@transaction.atomic
def activate(request,data,pk):
    state=profile(True)
    rule=Rule.objects.select_for_update().get(pk=pk)
    if rule.status!="evaluated" or rule.baseline_epoch!=state.epoch or not passes(rule.evaluation):
        raise Problem("评测未通过或生效基线已变更，请重新评测",409)
    state.active=rule
    state.epoch+=1
    state.save()
    rule.status="adopted"
    rule.save(update_fields=["status"])
    audit(request.user,"rule.activate",rule)
    return {"active":pk,"epoch":state.epoch}


@endpoint("POST","reviewer")
@transaction.atomic
def rollback(request,data,pk):
    state=profile(True)
    if state.active_id!=pk or state.epoch!=number(data,"epoch",0):
        raise Problem("生效规则已变化",409)
    rule=state.active
    state.active=rule.parent
    state.epoch+=1
    state.save()
    rule.status="rolled_back"
    rule.save(update_fields=["status"])
    audit(request.user,"rule.rollback",rule)
    return {"active":state.active_id,"epoch":state.epoch}
