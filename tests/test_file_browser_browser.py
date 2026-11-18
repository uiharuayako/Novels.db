"""Real Chromium file navigation, bounded pages and mounted reader round trips."""
import json
import os
import shutil
import threading
from urllib.parse import parse_qs, urlencode, urlsplit
from wsgiref.simple_server import make_server, WSGIRequestHandler

import pytest

from test_webui_integration import recoll_index, site, client_for
from test_file_browser_integration import browse_folder, listing, mixed_byte_names
from test_app_experience_browser import route_site, PREFIX

playwright_api = pytest.importorskip('playwright.sync_api')


@pytest.fixture
def browser():
    executable = os.environ.get('RECOLL_TEST_CHROMIUM') or shutil.which('chromium')
    if not executable:
        pytest.skip('Chromium is required')
    with playwright_api.sync_playwright() as playwright:
        instance = playwright.chromium.launch(headless=True, executable_path=executable, args=['--no-sandbox'])
        yield instance
        instance.close()


def wait_loaded(page):
    playwright_api.expect(page.locator('.files-list')).not_to_have_attribute('aria-busy', 'true')


@pytest.fixture
def live_origin(site):
    # Real HTTP keeps redirects and reader resources on the same test origin.
    def mounted(environ, start_response):
        environ['SCRIPT_NAME'] = PREFIX
        environ['PATH_INFO'] = environ['PATH_INFO'].removeprefix(PREFIX) or '/'
        return site.app(environ, start_response)

    class QuietHandler(WSGIRequestHandler):
        def log_message(self, *args):
            pass

    server = make_server('127.0.0.1', 0, mounted, handler_class=QuietHandler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


@pytest.mark.parametrize('width', [1280, 390, 320])
def test_file_navigation_special_names_and_reader_round_trip(site, browse_folder, browser, live_origin, width):
    child = browse_folder / '中文 & <资料>'
    child.mkdir()
    (child / 'empty').mkdir()
    title = '未索引 <img src=x onerror=alert(1)> & 阅读.txt'
    body = '这是从文件浏览直接打开的未索引正文。'
    (child / title).write_text(body, encoding='utf-8')
    (child / 'unsupported.bin').touch()
    client = client_for(site, prefix=PREFIX)
    page = browser.new_page(viewport={'width': width, 'height': 900}, is_mobile=width < 700, has_touch=width < 700)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.context.add_cookies([dict(name=cookie.name, value=cookie.value, url=live_origin + PREFIX + '/')
                              for cookie in client.cookiejar])
    page.goto(live_origin + PREFIX + '/files')
    wait_loaded(page)
    assert page.locator('.account-nav a').all_text_contents() == ['发现文档', '文件浏览', '我的书架', '历史记录', '我的分享']
    assert page.locator('.account-nav [aria-current=page]').inner_text() == '文件浏览'
    for box in page.locator('.account-nav a').evaluate_all('nodes => nodes.map(node => { const r=node.getBoundingClientRect(); return {left:r.left,right:r.right}; })'):
        assert 0 <= box['left'] and box['right'] <= width
    page.locator('.files-list').get_by_role('link', name=site.books.name, exact=True).click()
    page.locator('.files-list').get_by_role('link', name=browse_folder.name, exact=True).click()
    page.locator('.files-list').get_by_role('link', name=child.name, exact=True).click()
    playwright_api.expect(page.locator('#files-heading')).to_have_text(child.name)
    assert page.locator('.files-name *').count() == 0
    assert page.get_by_text('暂不支持在线阅读', exact=True).is_visible()
    page.locator('.files-list').get_by_role('link', name='empty', exact=True).click()
    playwright_api.expect(page.locator('.files-status')).to_have_text('此目录没有可显示的文件或文件夹。')
    page.get_by_role('link', name='返回上级', exact=True).click()
    page.locator('.files-list').get_by_role('link', name=title, exact=True).focus()
    page.keyboard.press('Enter')
    page.wait_for_url('**/library/reader?**')
    page.frame_locator('#page-area iframe').get_by_text(body, exact=True).wait_for()
    page.get_by_role('link', name='返回文件浏览', exact=True).click()
    page.wait_for_url('**/library/files?**')
    playwright_api.expect(page.locator('#files-heading')).to_have_text(child.name)
    assert page.locator('.files-list').get_by_role('link', name=title, exact=True).is_visible()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path=str(site.root / f'files-{width}.png'), full_page=True)
    assert not errors, errors


def test_mixed_byte_names_show_unavailable_without_blocking_reader(site, mixed_byte_names, browser, live_origin):
    client = client_for(site, prefix=PREFIX)
    page = browser.new_page(viewport={'width': 390, 'height': 844})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.context.add_cookies([dict(name=cookie.name, value=cookie.value, url=live_origin + PREFIX + '/')
                              for cookie in client.cookiejar])
    page.goto(live_origin + PREFIX + '/files?' + urlencode({'path': str(mixed_byte_names['root'])}))
    wait_loaded(page)
    reason = '名称或目标路径不是有效 UTF-8，无法打开'
    disabled = page.locator('.files-row').filter(has_text=reason)
    assert disabled.count() == 5 and disabled.locator('a').count() == 0
    assert set(disabled.locator('.files-name').all_text_contents()) == mixed_byte_names['unavailable']
    assert page.locator('.files-name *').count() == 0
    assert page.locator('.files-row').count() == 6
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path=str(site.root / 'mixed-names-390.png'), full_page=True)
    page.get_by_role('link', name='可读.txt', exact=True).click()
    page.wait_for_url('**/library/reader?**')
    page.frame_locator('#page-area iframe').get_by_text('混合名称目录中的正常正文。', exact=True).wait_for()
    page.get_by_role('link', name='返回文件浏览', exact=True).click()
    playwright_api.expect(page.locator('.files-row')).to_have_count(6)
    assert page.locator('.files-row').filter(has_text=reason).locator('a').count() == 0
    assert not errors, errors


def test_five_pages_remain_bounded_and_failure_can_reload(site, browse_folder, browser):
    for number in range(600):
        (browse_folder / f'book-{number:04d}.txt').touch()
    client = client_for(site, prefix=PREFIX)
    page = browser.new_page(viewport={'width': 390, 'height': 844})
    requests = []
    page.on('request', lambda request: requests.append(request.url) if '/api/files?' in request.url else None)
    route_site(page, client)
    page.goto('http://recoll.test' + PREFIX + '/files?' + urlencode({'path': str(browse_folder)}))
    wait_loaded(page)
    assert len(requests) == 1 and page.locator('.files-row').count() == 100
    names = set(page.locator('.files-name').all_text_contents())
    for number in range(2, 7):
        page.get_by_role('button', name='下一页', exact=True).click()
        playwright_api.expect(page.locator('[data-files-count]')).to_have_text(f'第 {number} 批 · 本页 100 项')
        assert len(requests) == number and page.locator('.files-row').count() == 100
        batch = set(page.locator('.files-name').all_text_contents())
        assert not names.intersection(batch)
        names.update(batch)
    page.wait_for_timeout(150)
    assert len(requests) == 6 and len(names) == 600
    page.get_by_role('button', name='下一页', exact=True).click()
    playwright_api.expect(page.locator('.files-status')).to_have_text('已到目录末尾，没有更多可显示的条目。')
    assert page.locator('.files-row').count() == 0
    page.get_by_role('button', name='重新加载目录', exact=True).click()
    wait_loaded(page)

    def fail_once(route):
        page.unroute('**/api/files?**', fail_once)
        route.fulfill(status=503, content_type='application/json', body=json.dumps({'message': '测试：目录暂时不可用'}))

    page.route('**/api/files?**', fail_once)
    page.get_by_role('button', name='下一页', exact=True).click()
    playwright_api.expect(page.locator('.files-status')).to_have_text('测试：目录暂时不可用')
    assert page.locator('.files-row').count() == 0
    page.get_by_role('button', name='重试', exact=True).click()
    playwright_api.expect(page.locator('[data-files-count]')).to_have_text('第 1 批 · 本页 100 项')
    assert page.locator('.files-row').count() == 100


def test_late_directory_response_cannot_overwrite_new_navigation(site, browse_folder, browser):
    slow, fast = browse_folder / 'slow', browse_folder / 'fast'
    slow.mkdir()
    fast.mkdir()
    (slow / 'old.txt').touch()
    (fast / 'current.txt').touch()
    client = client_for(site, prefix=PREFIX)
    page = browser.new_page()
    # Keep the old transport alive to exercise the response generation check as
    # well as AbortController, even when a server has already accepted a request.
    page.add_init_script('''const originalFetch = window.fetch;
        window.fetch = (url, options = {}) => { const {signal, ...rest} = options; return originalFetch(url, rest); };''')
    route_site(page, client)
    pending = []

    def hold_slow(route):
        query = parse_qs(urlsplit(route.request.url).query)
        if query.get('path') == [str(slow)]:
            pending.append(route)
        else:
            route.fallback()

    page.route('**/api/files?**', hold_slow)
    page.goto('http://recoll.test' + PREFIX + '/files?' + urlencode({'path': str(browse_folder)}))
    wait_loaded(page)
    page.locator('.files-list').get_by_role('link', name='slow', exact=True).click()
    assert len(pending) == 1
    page.locator('.files-list').get_by_role('link', name='fast', exact=True).click()
    playwright_api.expect(page.locator('#files-heading')).to_have_text('fast')
    pending[0].fulfill(content_type='application/json', body=json.dumps(listing(client, slow)))
    page.wait_for_timeout(100)
    assert page.locator('#files-heading').inner_text() == 'fast'
    assert page.locator('.files-name').all_text_contents() == ['current.txt']
    assert parse_qs(urlsplit(page.url).query)['path'] == [str(fast)]
