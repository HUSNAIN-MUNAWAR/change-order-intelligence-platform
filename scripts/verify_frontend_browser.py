"""Verify the running Next.js + FastAPI workspace in a real local browser."""

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright

from changeorder.jsonio import write_json
from changeorder.schemas import ExtractionResult

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:3000")
    parser.add_argument("--browser-channel", default="msedge")
    args = parser.parse_args()
    if urlparse(args.url).hostname not in {"localhost", "127.0.0.1"}:
        parser.error("This verification script targets a local frontend only")

    screenshot = ROOT / "docs" / "images" / "nextjs-demo.png"
    screenshot.parent.mkdir(parents=True, exist_ok=True)
    report_path = ROOT / "examples" / "nextjs-ui-verification.json"
    external_requests: set[str] = set()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            channel=None if args.browser_channel == "chromium" else args.browser_channel,
            headless=True,
        )
        desktop = browser.new_context(viewport={"width": 1512, "height": 1000})
        page = desktop.new_page()
        page.on(
            "request",
            lambda request: (
                external_requests.add(request.url)
                if urlparse(request.url).hostname not in {None, "localhost", "127.0.0.1"}
                else None
            ),
        )
        page.goto(args.url, wait_until="networkidle")
        expect(page.get_by_role("heading", name="SLEDGE CHANGE ORDER INTELLIGENCE")).to_be_visible()
        page.get_by_text("Clean change order", exact=True).click()
        expect(page.get_by_text("01_clean.txt", exact=True)).to_be_visible()
        page.get_by_role("button", name="Extract change order", exact=True).click()
        expect(page.get_by_text("CO-001", exact=True)).to_be_visible(timeout=60_000)
        page.locator("#field-group").select_option(label="Financial details")
        expect(page.get_by_text("12500", exact=True)).to_be_visible()
        page.get_by_role("button", name="Show formatted JSON", exact=True).click()
        page.screenshot(path=str(screenshot), full_page=True)
        with page.expect_download() as download_info:
            page.get_by_role("button", name="Download", exact=True).click()
        downloaded = ROOT / "tmp" / "nextjs-browser-downloaded.json"
        downloaded.parent.mkdir(exist_ok=True)
        download_info.value.save_as(str(downloaded))
        result = ExtractionResult.model_validate_json(downloaded.read_bytes())
        assert result.data.change_order_number.value == "CO-001"
        assert result.data.total_change_amount.value == 12500

        mobile = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True)
        mobile_page = mobile.new_page()
        mobile_page.goto(args.url, wait_until="networkidle")
        expect(
            mobile_page.get_by_role("button", name="Extract change order", exact=True)
        ).to_be_visible()
        assert mobile_page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        mobile_page.get_by_text("Clean change order", exact=True).click()
        mobile_page.get_by_role("button", name="Extract change order", exact=True).click()
        expect(mobile_page.get_by_text("CO-001", exact=True)).to_be_visible(timeout=60_000)
        assert mobile_page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        desktop.close()
        mobile.close()
        browser.close()

    report = {
        "url": args.url,
        "browser": args.browser_channel,
        "desktop_viewport": [1512, 1000],
        "mobile_viewport": [390, 844],
        "real_api_fixture_extraction": True,
        "fixture_label": "synthetic repository fixture, not an external benchmark",
        "field_value_visible": True,
        "json_download_schema_validated": True,
        "mobile_no_horizontal_overflow": True,
        "external_requests": sorted(external_requests),
        "screenshot": "docs/images/nextjs-demo.png",
    }
    write_json(report_path, report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
