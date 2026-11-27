"""Read-only category UI regression in the existing Playwright environment."""
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main():
    base = os.environ.get('MICE_UI_URL', 'http://localhost:8080')
    output = Path(os.environ.get('MICE_UI_SCREENSHOTS', '/tmp/mice-category-ui'))
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=os.environ.get('MICE_CHROMIUM_PATH'))
        page = browser.new_page(viewport={'width': 1280, 'height': 960})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(base)
        page.locator('[name="username"]').fill('admin')
        page.locator('[name="password"]').fill(os.environ['ADMIN_PASSWORD'])
        page.get_by_role('button', name='Войти', exact=True).click()
        page.wait_for_url('**/overview/')
        for width in (1024, 1280, 1920):
            page.set_viewport_size({'width': width, 'height': 960})
            for theme in ('light', 'dark'):
                page.evaluate('x => document.documentElement.dataset.theme = x', theme)
                page.locator('#workspace-navigation a[href="/categories/"]').click()
                page.wait_for_timeout(400)
                page.locator('.ui-data-table-compact').first.wait_for()
                page.evaluate('window.scrollTo(0, 0)')
                assert page.locator('.ui-data-table-compact tbody tr').count() == 12
                first = page.locator('main > section > .ui-disclosure').first
                first.locator('summary').first.click()
                expect(first.locator('table')).not_to_be_visible()
                first.locator('summary').first.click()
                expect(first.locator('table')).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.screenshot(path=str(output / f'categories-{width}-{theme}.png'))
                page.goto(f'{base}/categories/pack-ru2-financial-plans/?edit=1')
                page.evaluate('x => document.documentElement.dataset.theme = x', theme)
                dialog = page.locator('dialog[open]')
                dialog.wait_for()
                assert dialog.locator('[role="tab"]').count() == 2
                body = dialog.locator('.editor-dialog-body')
                assert body.evaluate('x => x.scrollHeight <= x.clientHeight + 2'), (width, theme)
                original = dialog.locator('[name="name"]').input_value()
                dialog.locator('[name="name"]').fill(original + ' UI test')
                page.screenshot(path=str(output / f'category-main-{width}-{theme}.png'))
                dialog.get_by_role('tab', name='Правила').click()
                rules = dialog.locator('.category-rule-form')
                assert rules.count() == 3  # no implicit extra form
                weighted = rules.filter(has=page.locator('input[name$="title"][value="Прогноз выручки с внутренним контекстом"]'))
                weighted.locator('summary').click()
                terms = weighted.locator('[data-term-row]:visible')
                assert terms.count() == 5
                weight = terms.first.locator('input[name$="_weight"]')
                weight.fill('9')
                panel = dialog.locator('[role="tabpanel"]:visible')
                panel.evaluate('x => x.scrollTop = 150')
                scroll = panel.evaluate('x => x.scrollTop')
                tab_top = dialog.locator('[role="tablist"]').bounding_box()['y']
                dialog.get_by_role('tab', name='Основное').click()
                assert dialog.locator('[name="name"]').input_value() == original + ' UI test'
                dialog.get_by_role('tab', name='Правила').click()
                assert weight.input_value() == '9'
                assert abs(panel.evaluate('x => x.scrollTop') - scroll) <= 2
                assert dialog.locator('[role="tablist"]').bounding_box()['y'] == tab_top
                page.once('dialog', lambda prompt: prompt.accept())
                rules.first.locator('[data-delete-rule]').click()
                assert rules.first.locator('[name$="-DELETE"]').is_checked()
                rules.first.locator('[data-undo-rule]').click()
                assert not rules.first.locator('[name$="-DELETE"]').is_checked()
                page.screenshot(path=str(output / f'category-rules-{width}-{theme}.png'))
                dialog.locator('[data-add-rule]').click()
                assert rules.last.get_attribute('open') is not None
                page.once('dialog', lambda prompt: prompt.accept())
                rules.last.locator('[data-delete-rule]').click()
                assert not rules.last.is_visible()
                assert dialog.locator('dialog').count() == 0
                assert not errors, errors
                page.goto(f'{base}/categories/')  # discard unsaved edits
        page.goto(f'{base}/categories/?kind=system')
        assert page.locator('.ui-data-table-compact tbody tr').count() == 19
        assert page.locator('.ui-row-actions a[title="Редактировать"]').count() == 0
        # Read-only descriptions: test every visible category via the real
        # popover and HTMX navigation, including builtin and custom catalogs.
        for kind in ("system", "custom"):
            page.goto(f"{base}/categories/?kind={kind}")
            links = page.locator('.category-actions-popover a').filter(has_text="Просмотр и описание")
            urls = links.evaluate_all("nodes => nodes.map(node => node.getAttribute('href'))")
            for index, url in enumerate(urls):
                page.goto(f"{base}/categories/?kind={kind}")
                link = page.locator('.category-actions-popover a').filter(has_text="Просмотр и описание")
                link = link.nth(index)
                assert link.get_attribute("href") == url
                menu_id = link.evaluate("node => node.closest('[popover]').id")
                page.locator(f'button[popovertarget="{menu_id}"]').click()
                link.click()
                dialog = page.locator('dialog.category-description-dialog[open]')
                expect(dialog).to_be_visible()
                expect(page.locator('#category-detail-panel')).to_have_count(0)
                expect(dialog.locator('button[type="submit"].primary')).to_have_count(0)
                page.keyboard.press("Escape")
                expect(dialog).to_have_count(0)
                page.wait_for_url(f"**/categories/?kind={kind}*")
        assert not errors, errors
        browser.close()
    print('PASS: category tables/groups, system permissions, tabs preserve unsaved fields/weights, inline rules, responsive themes; no writes')


if __name__ == '__main__':
    main()