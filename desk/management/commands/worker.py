import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from desk.runner import recover, step


class Command(BaseCommand):
    help = "执行已授权的模型任务；--once 最多执行一次外呼"

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")

    def handle(self, once, **options):
        while True:
            close_old_connections()
            recover()
            worked = step()
            if once:
                return
            if not worked:
                time.sleep(2)
