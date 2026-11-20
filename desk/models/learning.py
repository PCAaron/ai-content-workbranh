from django.db import models

from .editorial import Revision


class Rule(models.Model):
    training = models.ForeignKey(Revision, on_delete=models.PROTECT)
    old = models.CharField(max_length=120)
    new = models.CharField(max_length=120)
    reason = models.CharField(max_length=500)
    parent = models.ForeignKey("self", null=True, on_delete=models.PROTECT)
    baseline_epoch = models.PositiveIntegerField(null=True)
    evaluation = models.JSONField(default=list)
    status = models.CharField(max_length=20, default="candidate")


class Profile(models.Model):
    active = models.ForeignKey(Rule, null=True, on_delete=models.PROTECT)
    epoch = models.PositiveIntegerField(default=0)
