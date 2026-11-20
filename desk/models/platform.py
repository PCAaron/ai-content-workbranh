from django.db import models

class Audit(models.Model):
    at = models.DateTimeField(auto_now_add=True)
    actor = models.CharField(max_length=150)
    action = models.CharField(max_length=80)
    target = models.CharField(max_length=120)

class LoginFailure(models.Model):
    username = models.CharField(max_length=150, unique=True)
    count = models.PositiveIntegerField(default=0)
    since = models.DateTimeField()
