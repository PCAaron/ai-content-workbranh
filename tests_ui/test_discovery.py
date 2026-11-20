import os
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import LiveServerTestCase, override_settings
from playwright.sync_api import expect, sync_playwright

from desk.discovery import X_URL
from desk.tests.test_discovery import wechat_response, x_response


@override_settings(STATIC_URL="/static/", MEDIA_URL="/media/")
class DiscoveryBrowserTest(LiveServerTestCase):
    @patch.dict(
        os.environ,
        {"PRESS_X_READ_TOKEN": "fixture", "PRESS_BRAVE_SEARCH_KEY": "fixture"},
    )
    @patch("desk.discovery.fetch_bytes")
    def test_search_review_and_save(self, fetch):
        fetch.side_effect = lambda url, **_: (
            x_response() if url == X_URL else wechat_response()
        )
        user = User.objects.create_user("discovery-editor")
        user.groups.add(Group.objects.create(name="editor"))
        self.client.force_login(user)
        with sync_playwright() as driver:
            browser = driver.chromium.launch(
                executable_path=os.getenv("CHROMIUM_BIN") or None,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            context = browser.new_context(viewport={"width": 390, "height": 844})
            context.add_cookies(
                [
                    {
                        "name": "sessionid",
                        "value": self.client.cookies["sessionid"].value,
                        "url": self.live_server_url,
                    }
                ]
            )
            context.route(
                "https://mp.weixin.qq.com/**",
                lambda route: route.fulfill(
                    content_type="text/html; charset=utf-8", body="<h1>原文标题</h1>"
                ),
            )
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.goto(self.live_server_url)
            page.get_by_role("link", name="素材与选题").click()
            page.get_by_role("button", name="主题发现").click()
            page.get_by_label("主题词").fill("模型 AI")
            page.get_by_role("button", name="检索主题").click()
            expect(page.get_by_text("去重样本 3 条")).to_be_visible()
            page.get_by_role("button", name="加入来源材料").first.click()
            expect(page.get_by_text("已加入来源材料", exact=False)).to_be_visible()
            page.get_by_label("检索平台").select_option("wechat")
            page.get_by_role("button", name="检索主题").click()
            expect(page.get_by_text("去重样本 2 条")).to_be_visible()
            with page.expect_popup() as popup:
                page.get_by_role("link", name="模型更新").click()
            expect(popup.value.get_by_role("heading", name="原文标题")).to_be_visible()
            popup.value.close()
            page.get_by_role("button", name="核对原文并入库").first.click()
            page.get_by_label("核对后的原文标题").fill("原文标题")
            page.get_by_label("原文节选（可稍后补录）").fill("核对过的节选")
            page.get_by_role("button", name="保存核对结果").click()
            expect(page.get_by_text("已加入来源材料", exact=False)).to_be_visible()
            self.assertTrue(
                page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            )
            fetch.side_effect = None
            fetch.return_value = b"{}"
            page.get_by_role("button", name="检索主题").click()
            expect(page.get_by_text("检索服务返回的样本无法核验")).to_be_visible()
            expect(page.get_by_text("去重样本 2 条")).to_have_count(0)
            page.get_by_role("button", name="来源材料", exact=True).click()
            expect(page.get_by_role("link", name="原文标题")).to_be_visible()
            expect(page.get_by_text("核对过的节选")).to_be_visible()
            expect(page.get_by_text("AI 索引摘要")).to_have_count(0)
            self.assertEqual(fetch.call_count, 3)
            self.assertEqual(errors, [])
            browser.close()
