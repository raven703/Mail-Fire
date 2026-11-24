"""Read-only browser regression: existing Playwright + local running MICE.

Run with Python providing playwright; ADMIN_PASSWORD must be supplied in env.
No form is submitted, so stored DLP configuration remains unchanged.
"""

import os
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from playwright.sync_api import sync_playwright


def main():
    base = os.environ.get("MICE_UI_URL", "http://localhost:8080")
    output = Path(os.environ.get("MICE_UI_SCREENSHOTS", "/tmp/mice-weighted-terms"))
    output.mkdir(parents=True, exist_ok=True)
    rule = uuid5(NAMESPACE_URL, "mice:original-dlp:pack-ru2-financial-plans:0:Прогноз выручки с внутренним контекстом")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=os.environ.get("MICE_CHROMIUM_PATH"))
        page = browser.new_page(viewport={"width": 1280, "height": 960})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(base)
        page.locator('[name="username"]').fill("admin")
        page.locator('[name="password"]').fill(os.environ["ADMIN_PASSWORD"])
        page.locator('button[type="submit"], button').filter(has_text="Войти").click()
        page.wait_for_url("**/overview/")
        page.goto(f"{base}/categories/pack-ru2-financial-plans/rules/{rule}/")
        editor = page.locator('[data-structured-rule]')
        editor.wait_for()
        rows = editor.locator('[data-term-row]:visible')
        assert rows.count() == 5
        assert editor.locator('[data-term-count]').inner_text() == "5 из 30"
        assert "12" in editor.locator('[data-term-summary]').inner_text()
        original = rows.locator('input[name$="_text"]').evaluate_all("xs => xs.map(x => x.value)")
        for theme in ("light", "dark"):
            page.evaluate("theme => document.documentElement.dataset.theme = theme", theme)
            editor.locator('[data-flexible-terms]').scroll_into_view_if_needed()
            first = rows.first
            boxes = [first.locator(selector).bounding_box() for selector in
                     ('input[name$="_text"]', 'input[name$="_weight"]', 'input[type="checkbox"]', '[data-remove-term]')]
            assert max(box["y"] + box["height"] / 2 for box in boxes) - min(box["y"] + box["height"] / 2 for box in boxes) < 3
            assert boxes[0]["width"] > boxes[1]["width"] * 3
            page.screenshot(path=str(output / f"terms-{theme}.png"), full_page=True)
        rows.first.locator('input[name$="_weight"]').fill("9")
        assert "18" in editor.locator('[data-term-summary]').inner_text()
        rows.first.locator('input[type="checkbox"]').uncheck()
        assert "Обязательных: 1" in editor.locator('[data-term-summary]').inner_text()
        rows.nth(1).locator('[data-remove-term]').click()
        editor.locator('[data-add-term]').click()
        rows.last.locator('input[name$="_text"]').fill("Новый термин")
        values = rows.locator('input[name$="_text"]').evaluate_all("xs => xs.map(x => x.value)")
        assert values == [original[0], *original[2:], "Новый термин"]
        indices = rows.locator('input[name$="_text"]').evaluate_all("xs => xs.map(x => x.name)")
        assert indices == [f"term_{i}_text" for i in range(5)]
        rows.last.locator('input[name$="_weight"]').fill("101")
        assert not rows.last.locator('input[name$="_weight"]').evaluate("x => x.checkValidity()")
        for _ in range(25):
            editor.locator('[data-add-term]').click()
        assert rows.count() == 30
        assert editor.locator('[data-add-term]').is_disabled()
        page.reload()  # Discard edits: do not modify live rules.
        assert page.locator('[data-term-row]:visible').count() == 5
        page.set_viewport_size({"width": 390, "height": 844})
        page.locator('[data-flexible-terms]').scroll_into_view_if_needed()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(output / "terms-mobile.png"), full_page=True)
        # Same component in category formsets and dynamically inserted rules.
        page.goto(f"{base}/categories/pack-ru2-financial-plans/?edit=1")
        for details in page.locator('.category-rule-form').all():
            if details.get_attribute('open') is None:
                details.locator('summary').click()
        assert page.locator('[data-flexible-terms]:visible').count() >= 2
        page.locator('[data-add-rule]').click()
        last = page.locator('[data-structured-rule]').last
        last.locator('[name$="match_type"]').select_option("flexible")
        last.locator('[data-add-term]').click()
        assert last.locator('[data-term-row]:visible').count() == 1
        assert not errors, errors
        browser.close()
    print("PASS: themes, horizontal alignment, counters, order, validation, 30-term limit, mobile and dynamic formset; no writes")


if __name__ == "__main__":
    main()