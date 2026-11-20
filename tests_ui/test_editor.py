"""Isolated browser acceptance. Requires a built web/dist and Playwright Chromium."""

import os
from io import BytesIO
from zipfile import ZipFile

from django.contrib.auth.models import Group, User
from django.test import LiveServerTestCase, override_settings
from PIL import Image
from playwright.sync_api import expect, sync_playwright


@override_settings(STATIC_URL="/static/", MEDIA_URL="/media/")
class EditorialBrowserTest(LiveServerTestCase):
    host = "127.0.0.1"

    def test_evidence_to_approved_artifact(self):
        user = User.objects.create_user("test-chief", password="fixture-pass-only")
        user.groups.add(Group.objects.create(name="reviewer"))
        with sync_playwright() as driver:
            browser = driver.chromium.launch(
                executable_path=os.getenv("CHROMIUM_BIN") or None,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            page = browser.new_page(viewport={"width": 1365, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(self.live_server_url)
            page.get_by_label("账号", exact=True).fill("test-chief")
            page.get_by_label("密码", exact=True).fill("fixture-pass-only")
            page.get_by_role("button", name="登录", exact=True).click()
            page.get_by_role("link", name="素材与选题").click()
            page.get_by_label("材料标题").fill("样本：系统升级说明")
            page.get_by_label("原文链接").fill("https://example.org/release")
            page.get_by_label("原文节选").fill("公开说明新增了版本核对。")
            page.get_by_role("button", name="保存记录").click()
            expect(page.get_by_role("link", name="样本：系统升级说明")).to_be_visible()
            page.get_by_role("button", name="本人原话", exact=True).click()
            quote = "我会先比较两版差异。"
            page.get_by_label("本人原话", exact=True).fill(quote)
            page.get_by_label("出处或定位").fill("合成笔记第 3 段")
            page.get_by_role("checkbox").check()
            page.get_by_role("button", name="保存记录").click()
            expect(page.locator("blockquote")).to_have_text(quote)
            page.get_by_role("button", name="选题池").click()
            page.get_by_label("选题标题").fill("升级前应该核对什么")
            page.get_by_label("引用本人原话").select_option(index=1)
            sources = page.get_by_label("关联来源（可多选）")
            source_id = sources.locator("option").first.get_attribute("value")
            sources.select_option(source_id)
            page.get_by_role("checkbox").check()
            page.get_by_role("button", name="确认选题", exact=True).click()
            page.get_by_role("button", name="打开母稿").click()
            body = quote + "\n\n公开说明新增了版本核对。[S" + source_id + "]"
            page.get_by_label("正文", exact=True).fill(body)
            page.get_by_label("本次改稿理由").fill("首次人工编写")
            page.get_by_role("button", name="保存修订").click()
            page.get_by_role("button", name="审核母稿").click()
            page.reload()
            expect(page.get_by_label("正文", exact=True)).to_have_value(body)
            page.get_by_role("button", name="渠道稿件").click()
            for label in ("微信公众号", "X 长文", "知识星球", "小红书"):
                page.get_by_role("button", name=label, exact=True).click()
                page.get_by_role("button", name="从审核版生成").click()
                page.get_by_role("button", name="审核渠道稿").click()
                with page.expect_download() as result:
                    page.get_by_role(
                        "button", name="导出图文包" if label == "小红书" else "导出文件"
                    ).click()
                content = result.value.path().read_bytes()
                if label == "小红书":
                    with ZipFile(BytesIO(content)) as archive:
                        self.assertEqual(
                            Image.open(BytesIO(archive.read("01.png"))).size,
                            (1080, 1440),
                        )
                else:
                    self.assertIn("https://example.org/release", content.decode())
            page.set_viewport_size({"width": 390, "height": 844})
            self.assertTrue(
                page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            )
            page.get_by_role("link", name="文风实验室").click()
            expect(page.get_by_role("heading", name="文风实验室")).to_be_visible()
            self.assertEqual(errors, [])
            browser.close()
