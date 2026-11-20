from django.conf import settings
from django.db import models
from .intake import Topic


class Draft(models.Model):
    topic = models.OneToOneField(Topic,on_delete=models.PROTECT)
    version = models.PositiveIntegerField(default=0)
    approved = models.PositiveIntegerField(null=True)


class Revision(models.Model):
    draft = models.ForeignKey(Draft,related_name="revisions",on_delete=models.PROTECT)
    version = models.PositiveIntegerField()
    body = models.TextField()
    reason = models.CharField(max_length=500)
    actor = models.CharField(max_length=150)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints=[models.UniqueConstraint(fields=["draft","version"],name="unique_draft_version")]


class Note(models.Model):
    revision = models.ForeignKey(Revision,on_delete=models.PROTECT)
    text = models.CharField(max_length=1500)
    anchor = models.CharField(max_length=500,blank=True)
    actor = models.CharField(max_length=150)
    at = models.DateTimeField(auto_now_add=True)


class Job(models.Model):
    draft = models.ForeignKey(Draft,on_delete=models.PROTECT)
    base = models.PositiveIntegerField()
    budget = models.PositiveSmallIntegerField()
    inputs = models.JSONField()
    model = models.CharField(max_length=160)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    state = models.CharField(max_length=24,default="queued",db_index=True)
    detail = models.CharField(max_length=500,blank=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints=[models.UniqueConstraint(fields=["draft","base"],name="one_job_per_base")]


class Attempt(models.Model):
    job = models.ForeignKey(Job,related_name="attempts",on_delete=models.PROTECT)
    sequence = models.PositiveSmallIntegerField()
    state = models.CharField(max_length=24,default="calling")
    result = models.TextField(blank=True)
    detail = models.CharField(max_length=500,blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints=[models.UniqueConstraint(fields=["job","sequence"],name="one_call_per_step")]
