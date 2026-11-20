from django.conf import settings
from django.db import models


class Source(models.Model):
    url = models.URLField(max_length=2048, unique=True)
    title = models.CharField(max_length=300)
    origin = models.CharField(max_length=40)
    byline = models.CharField(max_length=150, blank=True)
    excerpt = models.TextField(blank=True)
    published = models.DateTimeField(null=True)
    collected = models.DateTimeField(auto_now_add=True)


class Quote(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    text = models.TextField()
    locator = models.CharField(max_length=300)
    created = models.DateTimeField(auto_now_add=True)


class Topic(models.Model):
    title = models.CharField(max_length=300)
    quote = models.ForeignKey(Quote, on_delete=models.PROTECT)
    sources = models.ManyToManyField(Source)
    created = models.DateTimeField(auto_now_add=True)


class Cursor(models.Model):
    name = models.CharField(max_length=128, unique=True)
    watermark = models.CharField(max_length=128, blank=True)
    pending = models.CharField(max_length=128, blank=True)
    token = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=0)


class DiscoveryRun(models.Model):
    request_id = models.UUIDField(primary_key=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    platform = models.CharField(max_length=10)
    limit = models.PositiveSmallIntegerField()
    started = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, default="pending")
    count = models.PositiveSmallIntegerField(null=True)
