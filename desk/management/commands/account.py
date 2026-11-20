from getpass import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "新建命名账号并分配编辑/审核角色"

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("role", choices=["editor", "reviewer"])

    @transaction.atomic
    def handle(self, username, role, **options):
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            raise CommandError("账号已存在；修改密码请用 changepassword")
        user = User(username=username)
        password = getpass("新密码: ")
        try:
            validate_password(password, user)
            user.full_clean(exclude=["password"])
        except ValidationError as exc:
            raise CommandError(" / ".join(exc.messages)) from exc
        user.set_password(password)
        user.save()
        user.groups.add(Group.objects.get_or_create(name=role)[0])
        self.stdout.write(f"已创建 {username}（{role}）")
