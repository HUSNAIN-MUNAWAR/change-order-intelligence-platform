"""Exercise the live localhost demo in a real browser and save an unmodified screenshot.

Optional test dependency: pip install playwright
Uses installed Edge by default; --browser-channel chromium uses Playwright's bundled Chromium.
Start Streamlit separately before running this script.
"""

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright

from changeorder.jsonio import write_json
from changeorder.schemas import ExtractionResult

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8501")
    parser.add_argument("--browser-channel", default="msedge")
    args = parser.parse_args()
    if urlparse(args.url).hostname not in {"localhost", "127.0.0.1"}:
        parser.error("This verification script targets a local demo only")
    output = ROOT / "docs/images/streamlit-demo.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    (ROOT / "tmp").mkdir(exist_ok=True)
    external_requests = set()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            channel=None if args.browser_channel == "chromium" else args.browser_channel,
            headless=True,
        )
        context = browser.new_context(
            viewport={"width": 1512, "height": 1700},
            permissions=["clipboard-read", "clipboard-write"],
        )
        page = context.new_page()
        page.on(
            "request",
            lambda request: (
                external_requests.add(request.url)
                if urlparse(request.url).hostname not in {None, "localhost", "127.0.0.1"}
                else None
            ),
        )
        page.goto(args.url)
        page.get_by_role("combobox").first.click()
        page.get_by_role("option", name="Scanned PDF - real local OCR", exact=True).click()
        page.get_by_role("button", name="Extract Change Order", exact=True).click()
        expect(page.get_by_role("tab", name="Document Review", exact=True)).to_be_visible(
            timeout=60_000
        )
        expect(page.get_by_text("CO-003", exact=True)).to_be_visible()
        # Use the live page's accessible labels rather than internal session state.
        page.get_by_role("combobox", name="Field group").click()
        page.get_by_role("option", name="Financial information", exact=True).click()
        expect(page.get_by_text("6400.00", exact=True).first).to_be_visible()
        page.get_by_text("Evidence · Total change amount", exact=True).click()
        expect(page.get_by_text("Final Amount: EUR 6,400.00", exact=True).first).to_be_visible()
        page.get_by_role(
            "heading", name="CHANGE ORDER INTELLIGENCE", exact=True
        ).scroll_into_view_if_needed()
        page.screenshot(path=str(output), full_page=True)
        page.get_by_role("tab", name="JSON Output", exact=True).click()
        with page.expect_download() as download_info:
            page.get_by_role("button", name="Download JSON", exact=True).click()
        downloaded = ROOT / "tmp/browser-downloaded.json"
        download_info.value.save_as(str(downloaded))
        result = ExtractionResult.model_validate_json(downloaded.read_bytes())
        assert result.status == "success" and result.source.pages[0].text_origin == "ocr"
        assert (
            result.data.change_order_number.value == "CO-003"
            and result.data.total_change_amount.value == 6400
        )
        code_panel = page.get_by_role("tabpanel", name="JSON Output").get_by_role("code")
        code_panel.hover(position={"x": 20, "y": 10})
        copy_button = page.get_by_role("button", name="Copy to clipboard", exact=True)
        expect(copy_button).to_be_visible()
        copy_button.click()
        copied = page.evaluate("navigator.clipboard.readText()")
        copied_result = ExtractionResult.model_validate_json(copied)
        assert copied_result == result
        # A second fresh context verifies the mobile layout without changing the desktop session.
        mobile = browser.new_context(
            viewport={"width": 390, "height": 844}, is_mobile=True, device_scale_factor=1
        )
        mobile_page = mobile.new_page()
        mobile_page.goto(args.url)
        expect(
            mobile_page.get_by_role("button", name="Extract Change Order", exact=True)
        ).to_be_visible()
        assert mobile_page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        mobile_page.screenshot(path=str(ROOT / "tmp/streamlit-mobile.png"), full_page=True)
        mobile_page.get_by_role("button", name="Extract Change Order", exact=True).click()
        expect(mobile_page.get_by_role("tab", name="Document Review", exact=True)).to_be_visible(
            timeout=60_000
        )
        assert mobile_page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        source_heading = mobile_page.get_by_role("heading", name="Source document", exact=True)
        fields_heading = mobile_page.get_by_role(
            "heading", name="Extracted information", exact=True
        )
        assert abs(source_heading.bounding_box()["x"] - fields_heading.bounding_box()["x"]) < 3
        source_heading.scroll_into_view_if_needed()
        mobile_page.screenshot(path=str(ROOT / "tmp/streamlit-mobile-result.png"), full_page=True)
        assert not external_requests, external_requests
        report = {
            "url": args.url,
            "browser": args.browser_channel,
            "desktop_viewport": [1512, 1700],
            "mobile_viewport": [390, 844],
            "real_ocr_through_streamlit": True,
            "source_preview_visible": True,
            "field_value_6400_visible": True,
            "evidence_quote_visible": True,
            "json_download_schema_validated": True,
            "json_copy_matches_download": True,
            "mobile_no_horizontal_overflow": True,
            "mobile_results_stack_vertically": True,
            "app_external_requests": sorted(external_requests),
            "screenshot": "docs/images/streamlit-demo.png",
            "scanned_total_confidence": result.data.total_change_amount.confidence,
        }
        write_json(ROOT / "examples/ui-verification.json", report)
        print(json.dumps(report, indent=2))
        context.close()
        mobile.close()
        browser.close()


if __name__ == "__main__":
    main()
