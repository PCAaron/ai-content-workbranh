"""Exercise the local Compose entry point on a disposable, empty CI checkout."""

import json
import os
import secrets
import subprocess
from http.cookiejar import CookieJar
from urllib.request import HTTPCookieProcessor, Request, build_opener

import pexpect


def first_start(password, expected_status):
    terminal = pexpect.spawn("sh", ["start.sh"], encoding="utf-8", timeout=720)
    try:
        terminal.expect_exact("首次启动，请设置登录名")
        terminal.sendline("ci-reviewer")
        terminal.expect_exact("新密码:")
        terminal.sendline(password)
        terminal.expect(pexpect.EOF)
        if expected_status == 0:
            assert "http://127.0.0.1:8000/" in terminal.before, terminal.before[-1800:]
    except (pexpect.TIMEOUT, pexpect.EOF):
        raise RuntimeError(terminal.before[-3000:].replace(password, "***")) from None
    finally:
        terminal.close()
    assert terminal.exitstatus == expected_status, terminal.exitstatus


def main():
    if os.environ.get("GITHUB_ACTIONS") != "true" or not os.environ.get(
        "COMPOSE_PROJECT_NAME", ""
    ).startswith("ci-quickstart-"):
        raise SystemExit("This test requires an isolated CI project.")
    first_start("short", 1)
    password = secrets.token_urlsafe(24)
    first_start(password, 0)
    base = "http://127.0.0.1:8000"
    client = build_opener(HTTPCookieProcessor(CookieJar()))

    def get(path):
        with client.open(base + path, timeout=8) as response:
            return response.read()

    def post(path, data, csrf):
        req = Request(
            base + path,
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json", "X-CSRFToken": csrf},
        )
        with client.open(req, timeout=8) as response:
            return json.load(response)

    assert b'id="root"' in get("/")
    assert json.loads(get("/health/ready"))["status"] == "ready"
    csrf = json.loads(get("/api/session"))["csrf"]
    auth = post("/api/login", {"username": "ci-reviewer", "password": password}, csrf)
    assert auth["role"] == "reviewer"
    source = post(
        "/api/sources",
        {
            "url": "https://example.org/quickstart",
            "title": "容器验收",
            "origin": "本地测试",
            "excerpt": "重启后保留",
        },
        auth["csrf"],
    )
    assert source["created"]
    assert (
        subprocess.check_output(
            ["docker", "compose", "port", "web", "8000"], text=True
        ).strip()
        == "127.0.0.1:8000"
    )
    subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "web",
            "test",
            "-r",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        ],
        check=True,
    )
    subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "web",
            "python",
            "manage.py",
            "migrate",
            "--check",
        ],
        check=True,
    )
    subprocess.run(["sh", "start.sh"], stdin=subprocess.DEVNULL, check=True)
    subprocess.run(["docker", "compose", "down"], check=True)
    subprocess.run(["sh", "start.sh"], stdin=subprocess.DEVNULL, check=True)
    assert "manage.py worker" in subprocess.check_output(
        ["docker", "compose", "top", "worker"], text=True
    )
    assert json.loads(get("/api/session"))["user"] == "ci-reviewer"
    assert any(
        s["id"] == source["id"] for s in json.loads(get("/api/library"))["sources"]
    )
    print(
        "PASS: clean install, account recovery, login, durable session and source, worker, font, loopback port"
    )


if __name__ == "__main__":
    main()
