from django.db import models

from .editorial import Revision


class Edition(models.Model):
    revision = models.ForeignKey(Revision, on_delete=models.PROTECT)
    platform = models.CharField(max_length=16)
    version = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=300)
    body = models.TextField()
    cards = models.JSONField(default=list)
    approved = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["revision", "platform"], name="unique_platform_edition"
            )
        ]


class Delivery(models.Model):
    edition = models.ForeignKey(Edition, on_delete=models.PROTECT)
    version = models.PositiveIntegerField()
    state = models.CharField(max_length=20)
    remote_id = models.CharField(max_length=256, blank=True)
    detail = models.CharField(max_length=400, blank=True)
    snapshot = models.JSONField()
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["edition", "version"], name="one_remote_draft_request"
            )
        ]
