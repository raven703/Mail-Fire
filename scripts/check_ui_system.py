"""Read-only Chromium smoke test of the shared MICE UI; no live data writes."""
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    base = os.environ.get('MICE_UI_URL', 'http://localhost:8080')
    output = Path(os.environ.get('MICE_UI_SCREENSHOTS', '/tmp/mice-ui-system'))
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
        page.evaluate("window.uiSwaps = 0; document.addEventListener('htmx:afterSwap', () => window.uiSwaps++)")
        for width in (1024, 1280, 1920):
            page.set_viewport_size({'width': width, 'height': 960})
            for theme in ('light', 'dark'):
                page.evaluate('theme => document.documentElement.dataset.theme = theme', theme)
                page.locator('#workspace-navigation a[href="/incidents/"]').click()
                page.locator('.ui-filter-grid').wait_for()
                page.wait_for_timeout(150)
                filters = page.locator('.ui-filter-grid')
                assert filters.evaluate("x => getComputedStyle(x).position") == 'static'
                assert page.locator('.ui-data-table th').count() == 7
                assert page.locator('.ui-data-table').bounding_box()['y'] >= filters.bounding_box()['y'] + filters.bounding_box()['height']
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (width, theme)
                assert page.locator('main > section').evaluate("x => getComputedStyle(x).overflowY") == 'visible'
                page.screenshot(path=str(output / f'incidents-{width}-{theme}.png'))
                page.locator('.ui-filter-advanced > summary').click()
                page.locator('[name="sender"]').fill('no-match@example.invalid')
                page.get_by_role('button', name='Найти', exact=True).last.click()
                page.wait_for_url('**/*sender=no-match%40example.invalid*')
                assert page.locator('.ui-filter-advanced').get_attribute('open') is not None
                assert page.locator('[name="sender"]').input_value() == 'no-match@example.invalid'
                page.get_by_role('link', name='Сбросить', exact=True).click()
                page.wait_for_url('**/incidents/')
                page.locator('#workspace-navigation a[href="/messages/"]').click()
                page.locator('h1').filter(has_text='Почтовые сообщения').wait_for()
                assert page.locator('.ui-data-table').count() == 1
        assert page.evaluate('window.uiSwaps') >= 6
        # Visit every permitted navigation destination through HTMX, without actions.
        links = page.locator('#workspace-navigation a').evaluate_all('xs => xs.map(x => x.getAttribute("href"))')
        for width in (1024, 1280, 1920):
            page.set_viewport_size({'width': width, 'height': 960})
            for theme in ('light', 'dark'):
                page.evaluate('theme => document.documentElement.dataset.theme = theme', theme)
                for href in dict.fromkeys(links):
                    page.locator(f'#workspace-navigation a[href="{href}"]').first.click()
                    page.wait_for_timeout(150)
                    assert page.locator('#mice-content main').count(), href
                    assert page.locator('.layout').count() == 1, href
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (href, width, theme)
                    assert not page.locator('body').inner_text().startswith('Server Error'), href
        # Shared Modal + weighted editor, GET only. Leave live configuration intact.
        from uuid import NAMESPACE_URL, uuid5
        rule = uuid5(NAMESPACE_URL, 'mice:original-dlp:pack-ru2-financial-plans:0:Прогноз выручки с внутренним контекстом')
        page.goto(f'{base}/categories/pack-ru2-financial-plans/rules/{rule}/')
        for width in (1024, 1280, 1920):
            page.set_viewport_size({'width': width, 'height': 960})
            for theme in ('light', 'dark'):
                page.evaluate('theme => document.documentElement.dataset.theme = theme', theme)
                assert page.locator('dialog[open]').count() == 1
                page.locator('[data-flexible-terms]').scroll_into_view_if_needed()
                assert page.locator('[data-term-row]:visible').count() == 5
                page.screenshot(path=str(output / f'rule-{width}-{theme}.png'))
        last = page.locator('[data-term-row]:visible').last.locator('input[name$="_text"]')
        last.press('Enter')
        assert page.locator('[data-term-row]:visible').count() == 6
        assert page.locator('[data-term-row]:visible').last.locator('input[name$="_text"]').evaluate('x => x === document.activeElement')
        page.reload()
        assert page.locator('[data-term-row]:visible').count() == 5
        assert not errors, errors
        browser.close()
    print('PASS: 1024/1280/1920, both themes, incident filters/reset, no overlaps, tables, HTMX navigation; no data writes')


if __name__ == '__main__':
    main()