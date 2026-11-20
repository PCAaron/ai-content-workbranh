import sys

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q


class Command(BaseCommand):
    help = "仅在没有可登录的审核员时引导创建本机首个账号"

    def handle(self, **options):
        users = get_user_model().objects
        reviewers = users.filter(is_active=True).filter(
            Q(is_superuser=True) | Q(groups__name="reviewer")
        )
        if (
            reviewers.exclude(password="")
            .exclude(password__startswith=UNUSABLE_PASSWORD_PREFIX)
            .exists()
        ):
            self.stdout.write("已有可用审核账号，可直接登录。")
            return
        if not sys.stdin.isatty():
            raise CommandError("首次开户需要交互终端。请直接运行启动脚本。")
        username = input("首次启动，请设置登录名 [chief]: ").strip() or "chief"
        self.stdout.write("请设置至少 12 位的密码，输入时不会显示字符。")
        call_command("account", username, "reviewer", stdout=self.stdout)
