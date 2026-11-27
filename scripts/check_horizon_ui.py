"""Chromium editing check. Run ONLY against a disposable test deployment."""

import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main():
    base = os.environ["MICE_HORIZON_TEST_URL"]
    output = Path(os.environ.get("MICE_HORIZON_UI_OUTPUT", "/tmp/horizon-ui"))
    output.mkdir(exist_ok=True, parents=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 960})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(base)
        page.locator("[name=username]").fill("horizon-ui")
        page.locator("[name=password]").fill(os.environ["MICE_HORIZON_TEST_PASSWORD"])
        page.get_by_role("button", name="Войти", exact=True).click()
        page.wait_for_url("**/overview/")
        page.goto(base + "/categories/pack-ru2-financial-plans/?edit=1")
        page.get_by_role("tab", name="Правила").click()
        rules = page.locator(".category-rule-form")
        horizon = rules.filter(has=page.locator('select[name$="-kind"] option:checked[value=horizon]'))
        horizon.locator("summary").click()
        field = horizon.locator('textarea[name$="-positive_hypotheses"]')
        expect(field).to_be_visible()
        field.fill("Письмо содержит внутренние финансовые планы.\nThe sender shares an internal budget.")
        horizon.locator('input[name$="-horizon_threshold"]').fill("0.65")
        horizon.locator('select[name$="-combine"]').select_option("mean")
        horizon.locator('select[name$="-aggregation"]').select_option("max")
        page.screenshot(path=str(output / "edit.png"))
        page.get_by_role("button", name="Сохранить", exact=True).click()
        page.wait_for_url("**/categories/pack-ru2-financial-plans/")
        page.goto(base + "/categories/pack-ru2-financial-plans/?edit=1")
        page.get_by_role("tab", name="Правила").click()
        horizon = page.locator(".category-rule-form").filter(
            has=page.locator('select[name$="-kind"] option:checked[value=horizon]')
        )
        horizon.locator("summary").click()
        expect(horizon.locator('textarea[name$="-positive_hypotheses"]')).to_have_value(
            "Письмо содержит внутренние финансовые планы.\nThe sender shares an internal budget."
        )
        expect(horizon.locator('input[name$="-horizon_threshold"]')).to_have_value("0.65")
        page.goto(base + "/detectors/?edit=horizon")
        expect(page.locator("dialog")).to_contain_text("не подтверждает работоспособность")
        for width in (1024, 1280, 1920):
            page.set_viewport_size({"width": width, "height": 960})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(output / f"detector-{width}.png"))
        assert not errors, errors
        (output / "results.json").write_text(
            json.dumps(
                {
                    "browser": "Chromium",
                    "saved_and_reloaded": True,
                    "widths": [1024, 1280, 1920],
                    "page_errors": errors,
                },
                indent=2,
            )
            + "\n"
        )
        browser.close()
        print("Horizon browser save/reload and readiness checks passed")


if __name__ == "__main__":
    main()
