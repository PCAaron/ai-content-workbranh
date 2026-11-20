import signal
from threading import Event

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from desk.runner import recover, step


class Command(BaseCommand):
    help = "执行已授权的模型任务；--once 最多执行一次外呼"

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")

    def handle(self, once, **options):
        stop = Event()

        def request_stop(signum, frame):
            stop.set()

        previous = {
            sig: signal.signal(sig, request_stop)
            for sig in (signal.SIGINT, signal.SIGTERM)
        }
        try:
            while not stop.is_set():
                close_old_connections()
                recover()
                if stop.is_set():
                    break
                worked = step()
                if once:
                    break
                if not worked:
                    stop.wait(2)
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
