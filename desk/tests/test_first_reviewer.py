from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase


class FirstReviewerTests(TestCase):
    def test_first_run_requires_terminal_and_reuses_role_validation(self):
        with patch("sys.stdin.isatty", return_value=False), self.assertRaises(
            CommandError
        ):
            call_command("first_reviewer", stdout=StringIO())
        inactive = User.objects.create_user(
            "inactive", password="fixture-only", is_active=False, is_superuser=True
        )
        dormant = User.objects.create_user("dormant")
        dormant.groups.add(Group.objects.create(name="reviewer"))
        with patch("sys.stdin.isatty", return_value=True), patch(
            "builtins.input", return_value=""
        ), patch(
            "desk.management.commands.account.getpass",
            return_value="local-fixture-only-37",
        ):
            call_command("first_reviewer", stdout=StringIO())
        created = User.objects.get(username="chief")
        self.assertTrue(created.groups.filter(name="reviewer").exists())
        self.assertTrue(created.check_password("local-fixture-only-37"))
        with patch(
            "builtins.input", side_effect=AssertionError("restart prompted for account")
        ):
            call_command("first_reviewer", stdout=StringIO())
        self.assertEqual(User.objects.get(pk=created.pk).password, created.password)
        self.assertFalse(User.objects.get(pk=inactive.pk).is_active)
