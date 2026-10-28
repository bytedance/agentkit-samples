"""Browser integration test against a local fixture; requires Chrome + playwright."""

import tempfile
import threading
from pathlib import Path

import yaml
from playwright.sync_api import expect, sync_playwright
from test_console import fixture, make_server


def main():
    with tempfile.TemporaryDirectory() as directory:
        upstream, console = fixture(directory)
        server = make_server(console, 0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        errors = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(channel="chrome", headless=True)
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{server.server_port}")
                expect(page.locator("#quickstart-panel")).to_be_visible()
                page.locator('[data-start="existing"]').click()
                page.locator("#quick-next").click()
                expect(page.locator("#quick-harnesses")).to_have_value("harness-one")
                page.locator("#quick-next").click()
                expect(page.locator("#quick-keys")).to_have_value("key-one")
                expect(page.locator("#quick-stores")).to_have_value("ss-one")
                page.locator("#quick-next").click()
                expect(page.locator("#quick-review")).to_contain_text("runtime-one")
                page.locator("#quick-next").click()
                expect(page.locator('[data-path="agent.id"]')).to_have_value(
                    "harness-one"
                )
                expect(page.locator('[data-path="environment_id"]')).to_have_value(
                    "env-one"
                )
                page.locator("#editor .close-dialog").last.click()
                page.locator('[data-view="endpoints"]').click()
                expect(page.locator("#load-more")).to_be_visible()
                page.locator("#load-more").click()
                expect(page.locator("#rows")).to_contain_text("ep-one")
                page.get_by_role("button", name="详情", exact=True).click()
                expect(page.locator("#detail-body")).to_contain_text("ep-one")
                page.locator("#detail .close-dialog").last.click()
                page.locator('[data-view="harnesses"]').click()
                expect(page.locator("#rows")).to_contain_text("通用助手")
                page.locator("#create").click()
                expect(page.locator("#editor")).to_be_visible()
                page.locator('[data-path="Name"]').fill("浏览器测试助手")
                page.locator("#submit-create").click()
                expect(page.locator("#detail-body")).to_contain_text("harnesses-new")
                page.locator("#detail .close-dialog").last.click()
                row = page.locator("tr", has_text="浏览器测试助手")
                expect(
                    row.get_by_role("button", name="删除", exact=True)
                ).to_be_disabled()
                row.get_by_role("button", name="归档", exact=True).click()
                expect(page.locator("#confirm-title")).to_have_text("归档 Harness")
                page.locator("#confirm-id").fill("harnesses-new")
                page.locator("#confirm-delete").click()
                expect(page.locator("#confirm")).not_to_be_visible()
                expect(row).to_contain_text("harnesses-new")
                expect(row).to_contain_text("Archived")
                expect(
                    row.get_by_role("button", name="归档", exact=True)
                ).to_be_disabled()
                row.get_by_role("button", name="详情", exact=True).click()
                expect(page.locator("#detail-body")).to_contain_text(
                    '"Status": "Archived"'
                )
                page.locator("#detail .close-dialog").last.click()
                page.locator("#status-filter").select_option("Active")
                expect(page.locator("#rows")).to_contain_text("harness-one")
                expect(page.locator("#rows")).not_to_contain_text("harnesses-new")
                page.locator("#status-filter").select_option("Archived")
                expect(page.locator("#rows")).to_contain_text("harnesses-new")
                expect(page.locator("#rows")).not_to_contain_text("harness-one")
                page.locator("#status-filter").select_option("")
                expect(page.locator("#rows tr")).to_have_count(2)
                screenshot = (
                    Path(__file__).resolve().parents[1]
                    / ".local"
                    / "resource-preview.png"
                )
                screenshot.parent.mkdir(exist_ok=True)
                page.screenshot(path=str(screenshot), full_page=True)
                page.locator('[data-view="templates"]').click()
                expect(page.locator("#rows")).to_contain_text("runtime-one")
                page.locator("#create").click()
                expect(page.locator("#editor")).to_be_visible()
                page.locator('[data-path="Name"]').fill("browser-delete-template")
                page.locator('[data-path="SessionStoreId"]').select_option("ss-one")
                page.locator("#submit-create").click()
                expect(page.locator("#detail-body")).to_contain_text("templates-new")
                page.locator("#detail .close-dialog").last.click()
                template_row = page.locator("tr", has_text="browser-delete-template")
                template_row.get_by_role("button", name="删除", exact=True).click()
                expect(page.locator("#delete-reason-field")).to_be_visible()
                page.locator("#confirm-id").fill("templates-new")
                page.locator("#confirm-delete").click()
                expect(page.locator("#confirm")).to_be_visible()
                page.locator("#delete-reason").fill("本地浏览器测试资源清理")
                page.locator("#confirm-delete").click()
                expect(page.locator("#confirm")).not_to_be_visible()
                expect(page.locator("#rows")).not_to_contain_text("templates-new")
                config = yaml.safe_load(console.path.read_text())
                saved_key = config["environment"]["env_api_key"]
                config["environment"]["env_api_key"] = {"id": "", "value": ""}
                console.path.write_text(yaml.safe_dump(config))
                page.locator('[data-view="chat"]').click()
                expect(page.locator("#key-select option")).to_have_count(1)
                config["environment"]["env_api_key"] = saved_key
                config["session"]["id"] = "session-one"
                console.path.write_text(yaml.safe_dump(config))
                page.locator("#refresh").click()
                expect(page.locator("#session-list")).to_contain_text(
                    "Harness Infra 工作空间"
                )
                page.locator("#session-list button").first.click()
                expect(page.locator("#prompt")).to_be_enabled()
                page.locator("#prompt").fill("你好")
                page.locator("#send").click()
                expect(page.locator("#messages")).to_contain_text(
                    "你好，本地协议测试成功。"
                )
                expect(page.locator("#chat-status")).to_contain_text("本轮完成")
                page.screenshot(
                    path=str(screenshot.with_name("chat-preview.png")), full_page=True
                )
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= window.innerWidth"
                )
                assert not errors, errors
                print(
                    "PASS: pagination, detail, create, archive, chat/end_turn, mobile layout; no browser errors"
                )
                browser.close()
        finally:
            for s in (server, upstream):
                s.shutdown()
                s.server_close()


if __name__ == "__main__":
    main()
