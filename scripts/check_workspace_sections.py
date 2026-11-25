"""Read-only browser regression for shared periods and section shells."""
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main():
    base = os.environ.get('MICE_UI_URL', 'http://localhost:8080')
    output = Path(os.environ.get('MICE_UI_SCREENSHOTS', '/tmp/mice-workspace-sections'))
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get('MICE_CHROMIUM_PATH'), headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 960})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(base)
        page.locator('[name="username"]').fill('admin')
        page.locator('[name="password"]').fill(os.environ['ADMIN_PASSWORD'])
        page.get_by_role('button', name='Войти', exact=True).click()
        page.wait_for_url('**/overview/')
        page.locator('[data-period]').select_option('168')
        page.wait_for_url('**range=168*')
        for route in ('incidents', 'messages', 'analytics'):
            page.locator(f'#workspace-navigation a[href^="/{route}/"]').click()
            expect(page.locator('[data-period]')).to_have_value('168')
        page.reload()
        expect(page.locator('[data-period]')).to_have_value('168')
        page.go_back()
        expect(page.locator('[data-period]')).to_have_value('168')
        page.go_forward()
        page.goto(base + '/incidents/?q=example&sort=risk&page=3&range=168')
        page.locator('[data-period]').select_option('720')
        page.wait_for_url('**range=720*')
        assert 'q=example' in page.url and 'sort=risk' in page.url and 'page=' not in page.url
        page.get_by_role('link', name='Сбросить', exact=True).click()
        page.wait_for_timeout(500)
        expect(page.locator('[data-period]')).to_have_value('720')
        page.locator('[data-period]').select_option('custom')
        page.locator('[name="start"]').fill('2026-11-01T10:00')
        page.locator('[name="end"]').fill('2026-11-20T10:00')
        page.locator('[name="end"]').blur()
        page.wait_for_url('**range=custom*')
        page.goto(base + '/analytics/')
        expect(page.locator('[data-period]')).to_have_value('custom')
        response = page.request.get(base + '/analytics/?export=timeline')
        assert response.status == 200 and 'text/csv' in response.headers['content-type']
        routes = ['/overview/', '/incidents/', '/messages/', '/analytics/',
                  '/models/?tab=models', '/datasets/', '/models/?tab=examples', '/models/?tab=label',
                  '/models/?tab=training', '/models/?tab=quality',
                  '/operations/?tab=queues', '/operations/?tab=jobs', '/operations/?tab=flow',
                  '/operations/?tab=resources', '/operations/?tab=database',
                  '/settings/', '/retention/', '/llm/']
        for width in (1024, 1280, 1920):
            page.set_viewport_size({'width': width, 'height': 960})
            for theme in ('light', 'dark'):
                for route in routes:
                    response = page.goto(base + route)
                    assert response.status == 200, (route, response.status)
                    page.wait_for_timeout(250)
                    page.evaluate('x => document.documentElement.dataset.theme = x', theme)
                    assert page.locator('main').count() == 1, route
                    expect(page.locator('#workspace-navigation a[aria-current="page"]')).to_have_count(1)
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (width, route)
                    name = route.strip('/').replace('/?', '-').replace('?', '-').replace('=', '-')
                    page.screenshot(path=str(output / f'{name}-{width}-{theme}.png'))
        assert not errors, errors
        browser.close()
    print('PASS: shared session period, HTMX, history, filters/reset, custom dates, CSV and 18 section routes in 6 viewport/theme combinations; no training or data writes')


if __name__ == '__main__':
    main()