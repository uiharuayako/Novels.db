"""Reader continuity with native Chromium touch input, not DOM TouchEvents."""
from pathlib import Path
from urllib.parse import urlsplit
import copy
import json
import os
import shutil
import time

import pytest

pw = pytest.importorskip('playwright.sync_api')
ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / 'views/reader.tpl').read_text()
TEMPLATE = TEMPLATE[TEMPLATE.index('<div id="reader-app"'):TEMPLATE.index('<script>')]


@pytest.fixture
def reader():
    chromium = os.environ.get('RECOLL_TEST_CHROMIUM') or shutil.which('chromium') or shutil.which('google-chrome')
    if not chromium:
        pytest.skip('Set RECOLL_TEST_CHROMIUM to run native touch checks')
    settings = {'progress_epoch': 3, 'reading_epoch': 4, 'progress_sync_enabled': True, 'preferences': {}}
    chunks = {
        'A': ['第一章 起点\n' + '\n'.join(f'A first paragraph {i:03d}' for i in range(90)),
              '第二章 中途\n' + '\n'.join(f'A middle paragraph {i:03d}' for i in range(50)) + '\n第三章 终点\n'
              + '\n'.join(f'A final paragraph {i:03d}' for i in range(80))],
        'B': ['\n'.join(f'B saved paragraph {i:03d}' for i in range(100))],
        'C': ['C short book final line'],
    }
    items = [{'documentId': name, 'contentVersion': 'v1', 'openHandle': f'handle-{name}', 'format': 'txt',
              'path': f'/{name}.txt', 'name': name, 'title': name, 'manifestUrl': f'/txt/{name}/manifest'} for name in chunks]
    positions = {name: {'position': None, 'revision': 0, 'content_version': 'v1'} for name in chunks}
    positions['B'].update(position={'chunkIndex': 0, 'chunkProgressRatio': .35}, revision=4)
    calls, errors, control = [], [], {'fail_B': False, 'unsupported_A': False, 'progress_reads': []}
    with pw.sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=chromium, args=['--no-sandbox'])
        context = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)

        def route_request(route):
            request = route.request
            path = urlsplit(request.url).path

            def send(value, mime='application/json', status=200):
                route.fulfill(status=status, content_type=mime, body=value if isinstance(value, (str, bytes)) else json.dumps(value))

            if path.startswith('/static/'):
                source = ROOT / path.lstrip('/')
                return send(source.read_bytes(), 'text/javascript' if source.suffix in ('.js', '.mjs') else 'text/css') if source.is_file() else send({}, status=404)
            if path == '/reader':
                config = {'mode': 'folder', 'apiBase': '/api/reader', 'account': {'userId': 'a', 'sessionId': 's', 'csrf': 'c', 'settings': settings}}
                return send('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
                            '<link rel="stylesheet" href="/static/style.css"><link rel="stylesheet" href="/static/reader/reader-ui.css">'
                            '</head><body>' + TEMPLATE + '<script>window.RECOLL_READER=' + json.dumps(config) + '</script>'
                            '<script type="module" src="/static/reader/app.js"></script></body></html>', 'text/html')
            if path == '/api/reader/folder':
                visible_items = copy.deepcopy(items)
                if control['unsupported_A']:
                    visible_items[0].update(progressSupported=False, readOnlyPreview=True, format='html', url='/member-preview')
                return send({'items': visible_items, 'currentIndex': 0, 'count': 3, 'truncated': False, 'root': '/books'})
            if path == '/member-preview':
                return send('Correct member <literal> preview', 'text/plain; charset=utf-8')
            if path == '/api/account':
                return send({'user': {'id': 'a'}, 'sessionId': 's', 'settings': settings})
            if request.method == 'POST':
                body = request.post_data_json
                calls.append((path, copy.deepcopy(body)))
                if path.endswith('/open'):
                    name = body['handle'].removeprefix('handle-')
                    return send({'progress': positions[name], 'settings': settings})
                if '/progress/' in path:
                    name = path.rsplit('/', 1)[1]
                    assert body['revision'] == positions[name]['revision']
                    positions[name].update(position=copy.deepcopy(body['position']), revision=positions[name]['revision'] + 1)
                    return send(positions[name])
                return send({'settings': settings})
            if '/api/reader/progress/' in path:
                control['progress_reads'].append(path)
                return send({**positions[path.rsplit('/', 1)[1]], 'settings': settings})
            if path.startswith('/txt/'):
                _, _, name, kind, *tail = path.split('/')
                if control['fail_B'] and name == 'B':
                    return send({'error': 'Fixture B unavailable'}, status=503)
                if kind == 'manifest':
                    values = chunks[name]
                    toc = []
                    if name == 'A':
                        for index, text in enumerate(values):
                            for heading in ['第一章 起点', '第二章 中途', '第三章 终点']:
                                if heading in text:
                                    toc.append({'index': index, 'label': heading, 'textOffset': text.index(heading), 'query': heading, 'depth': 0})
                    return send({'format': 'txt', 'charset': 'utf-8', 'chunkCount': len(values), 'contentUrl': f'/txt/{name}/chunk', 'toc': toc,
                                 'chunks': [{'index': i, 'byteLength': len(text.encode())} for i, text in enumerate(values)]})
                index = int(tail[0])
                return send({'index': index, 'text': chunks[name][index]})
            return send({}, status=404)

        context.route('**/*', route_request)
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto('http://recoll.test/reader')
        page.wait_for_function("() => window.rendition?.format === 'TXT' && document.querySelector('#reader-progress-label').textContent.includes('/3 章')")
        if not page.locator('#reader-sidebar').evaluate("node => node.classList.contains('is-hidden')"):
            page.locator('#reader-toggle-toc').click()
        page.wait_for_timeout(300)
        cdp = context.new_cdp_session(page)
        yield page, cdp, positions, calls, errors, control
        browser.close()


def tail(page, distance=0):
    page.evaluate("async () => {await window.rendition.goToPosition({chunkIndex:1,chunkProgressRatio:1});}")
    page.wait_for_function("() => document.querySelector('[data-chunk-index=\"1\"] iframe')?.dataset.readerContentLoaded === 'yes'")
    page.wait_for_timeout(250)
    page.locator('#page-area').evaluate('''(stage,distance) => {
      const frame=stage.querySelector('[data-chunk-index="1"] iframe'),range=frame.contentDocument.createRange();
      range.selectNodeContents(frame.contentDocument.body);
      const bottom=frame.getBoundingClientRect().top+range.getBoundingClientRect().bottom-stage.getBoundingClientRect().top+stage.scrollTop;
      stage.scrollTop=bottom-stage.clientHeight-distance;
    }''', distance)
    page.wait_for_timeout(250)


def touch(cdp, kind, x=190, y=500, extra=None, timestamp=None):
    points = [] if kind == 'touchEnd' else [{'x': x, 'y': y, 'id': 1}, *(extra or [])]
    cdp.send('Input.dispatchTouchEvent', {'type': kind, 'touchPoints': points, **({'timestamp': timestamp} if timestamp is not None else {})})


def swipe(page, cdp, start, end, steps=8, pause=35, release=True):
    touch(cdp, 'touchStart', y=start)
    for index in range(1, steps + 1):
        touch(cdp, 'touchMove', y=start + (end - start) * index / steps)
        page.wait_for_timeout(pause)
    if release:
        touch(cdp, 'touchEnd')


def test_continuous_touch_crosses_real_book_end_once_and_restores_next_book(reader):
    page, cdp, positions, calls, errors, _ = reader
    # A middle source chunk cannot be mistaken for the end of the book.
    page.evaluate('() => {const s=document.querySelector("#page-area"),slot=document.querySelector("[data-chunk-index]");s.scrollTop=slot.offsetHeight-s.clientHeight;}')
    page.wait_for_timeout(200)
    assert not page.locator('#reader-book-end').is_visible()
    tail(page, 180)
    assert not page.locator('#reader-book-end').is_visible()
    bounds = page.locator('#page-area').bounding_box()
    swipe(page, cdp, bounds['y'] + bounds['height'] - 50, bounds['y'] + 65, steps=14, release=False)
    page.wait_for_function("() => document.querySelector('#reader-title').textContent === 'B'")
    # Remaining input from this same finger must not reach C.
    touch(cdp, 'touchMove', y=bounds['y'] + 35)
    touch(cdp, 'touchEnd')
    page.wait_for_timeout(400)
    assert page.locator('#reader-title').inner_text() == 'B'
    assert .30 < page.evaluate('window.rendition.getPosition().chunkProgressRatio') < .4
    assert positions['A']['position']['chunkIndex'] == 1
    assert float(positions['A']['position']['percentage']) == 1
    assert not any(body.get('handle') == 'handle-C' for path, body in calls)
    page.locator('#reader-progress-prev-book').click()
    page.wait_for_function("() => document.querySelector('#reader-title').textContent === 'A' && document.querySelector('#reader-book-end')?.hidden === false")
    page.wait_for_timeout(300)
    assert page.locator('#reader-title').inner_text() == 'A'
    assert errors == []


def test_tail_second_gesture_cancels_reverse_multitouch_and_keyboard_failure_recovery(reader):
    page, cdp, positions, calls, errors, control = reader
    tail(page)
    page.wait_for_function("() => document.querySelector('#reader-book-end')?.hidden === false")
    bounds = page.locator('#page-area').bounding_box()
    y = bounds['y'] + bounds['height'] - 210
    swipe(page, cdp, y, y - 35, steps=3)
    assert page.locator('#reader-title').inner_text() == 'A'
    touch(cdp, 'touchStart', y=y)
    touch(cdp, 'touchMove', y=y - 25)
    page.wait_for_timeout(50)
    touch(cdp, 'touchMove', y=y - 10)  # Reversal cancels this intention.
    page.wait_for_timeout(50)
    touch(cdp, 'touchMove', y=y - 130)
    page.wait_for_timeout(50)
    touch(cdp, 'touchEnd')
    assert page.locator('#reader-title').inner_text() == 'A'
    touch(cdp, 'touchStart', y=y, extra=[{'x': 240, 'y': y, 'id': 2}])
    page.wait_for_timeout(50)
    touch(cdp, 'touchMove', y=y - 120, extra=[{'x': 240, 'y': y - 120, 'id': 2}])
    page.wait_for_timeout(50)
    touch(cdp, 'touchEnd')
    assert page.locator('#reader-title').inner_text() == 'A'
    # A new deliberate gesture while stopped at the end opens B.
    swipe(page, cdp, y, y - 160)
    page.wait_for_function("() => document.querySelector('#reader-title').textContent === 'B'")
    page.locator('#reader-progress-prev-book').click()
    page.wait_for_function("() => document.querySelector('#reader-title').textContent === 'A' && document.querySelector('#reader-book-end')?.hidden === false")
    control['fail_B'] = True
    page.locator('#reader-toggle-toolbar').click()
    page.wait_for_timeout(300)
    button = page.locator('#reader-book-end-next')
    assert button.is_enabled()
    button.focus()
    assert page.evaluate('document.activeElement.id') == 'reader-book-end-next'
    page.keyboard.press('Enter')
    page.get_by_role('button', name='重试下一本').wait_for(timeout=5000)
    assert page.locator('#reader-title').inner_text() == 'B'
    assert not any(body.get('handle') == 'handle-C' for path, body in calls)
    page.get_by_role('button', name='返回上一本').click()
    page.wait_for_function("() => document.querySelector('#reader-title').textContent === 'A' && document.querySelector('#reader-book-end')?.hidden === false")
    page.locator('#reader-book-end-next').click()
    page.get_by_role('button', name='重试下一本').wait_for()
    control['fail_B'] = False
    page.get_by_role('button', name='重试下一本').click()
    page.wait_for_function("() => document.querySelector('#reader-title').textContent === 'B' && window.rendition?.getPosition()?.chunkProgressRatio > .3 && window.rendition.getPosition().chunkProgressRatio < .4")
    assert .30 < page.evaluate('window.rendition.getPosition().chunkProgressRatio') < .4
    assert float(positions['A']['position']['percentage']) == 1
    assert errors == []


def test_release_inertia_restore_slider_and_reflow_do_not_switch(reader):
    page, cdp, positions, calls, errors, _ = reader
    tail(page, 300)
    bounds = page.locator('#page-area').bounding_box()
    y = bounds['y'] + bounds['height'] - 70
    # A short fast native swipe ends before content reaches the tail. Chromium's
    # compositor momentum continues after touchEnd and must never open B.
    page.evaluate('''() => {
      window.readerRelease = null;
      for(const frame of document.querySelectorAll('#page-area iframe')) frame.contentDocument.addEventListener('touchend', () => {
        const stage=document.querySelector('#page-area'),last=stage.querySelector('[data-chunk-index="1"] iframe');
        const range=last.contentDocument.createRange();range.selectNodeContents(last.contentDocument.body);
        window.readerRelease={top:stage.scrollTop,remaining:last.getBoundingClientRect().top+range.getBoundingClientRect().bottom-stage.getBoundingClientRect().bottom};
      }, {once:true,passive:true});
    }''')
    started = time.time() - .1
    touch(cdp, 'touchStart', y=y, timestamp=started)
    for index in range(1, 4):
        touch(cdp, 'touchMove', y=y - index * 60, timestamp=started + index * .005)
    touch(cdp, 'touchEnd', timestamp=started + .020)
    page.wait_for_function('window.readerRelease !== null')
    released = page.evaluate('window.readerRelease')
    assert released['remaining'] > 2, released
    page.wait_for_timeout(1400)
    assert page.locator('#page-area').evaluate('node=>node.scrollTop') > released['top']
    assert page.locator('#reader-book-end').is_visible()
    assert page.locator('#reader-title').inner_text() == 'A'
    tail(page)
    page.wait_for_timeout(300)
    assert page.locator('#reader-title').inner_text() == 'A'
    page.locator('#reader-progress-range').evaluate("node=>{node.value='1000';node.dispatchEvent(new Event('change',{bubbles:true}))}")
    page.wait_for_timeout(300)
    page.locator('#reader-toggle-settings').click()
    page.locator('#reader-font-increase').click()
    page.locator('#reader-close-settings').click()
    page.set_viewport_size({'width': 844, 'height': 390})
    page.wait_for_timeout(600)
    assert page.locator('#reader-title').inner_text() == 'A'
    assert not any(body.get('handle') == 'handle-B' for path, body in calls)
    assert errors == []


def test_numeric_chapters_follow_actual_heading_and_short_last_book_is_visible(reader):
    page, _, _, _, errors, _ = reader
    page.evaluate('async () => {await window.rendition.goToPosition({chunkIndex:1,chunkProgressRatio:.08})}')
    page.wait_for_function("() => document.querySelector('#reader-progress-label').textContent.includes('第 2/3 章')")
    page.evaluate('async () => {await window.rendition.goToPosition({chunkIndex:1,chunkProgressRatio:.65})}')
    page.wait_for_function("() => document.querySelector('#reader-progress-label').textContent.includes('第 3/3 章')")
    label = page.locator('#reader-progress-label').inner_text()
    assert page.locator('#reader-progress-range').get_attribute('aria-valuetext') == label
    assert page.locator('#reader-progress-label').evaluate('node=>node.scrollWidth<=node.clientWidth')
    page.locator('#reader-progress-next-book').click()
    page.wait_for_function("() => document.querySelector('#reader-title').textContent === 'B' && document.querySelector('#reader-progress-label').textContent.includes('第 1/1 区段')")
    page.locator('#reader-progress-next-book').click()
    page.wait_for_function("() => document.querySelector('#reader-title').textContent === 'C' && document.querySelector('#reader-book-end')?.hidden === false")
    assert page.get_by_text('已到书单末尾', exact=True).is_visible()
    assert not page.locator('#reader-book-end-next').is_visible()
    assert page.locator('#reader-progress-next-book').is_disabled()
    assert errors == []


@pytest.mark.parametrize('width', [390, 1280])
def test_unsupported_preview_can_be_dismissed_and_never_requests_member_progress(reader, width):
    page, _, _, calls, errors, control = reader
    control['unsupported_A'] = True
    control['progress_reads'].clear()
    member_opens = sum(path.endswith('/open') and body.get('handle') == 'handle-A' for path, body in calls)
    page.set_viewport_size({'width': width, 'height': 844})
    page.reload()
    page.get_by_text('此来源暂不支持保存进度', exact=True).wait_for()
    page.frame_locator('#page-area iframe').get_by_text('Correct member <literal> preview', exact=True).wait_for()
    page.get_by_role('button', name='收起', exact=True).click()
    capability = page.locator('#reader-meta .reader-sync-capability')
    assert capability.inner_text() == '进度保存不可用'
    geometry = capability.evaluate('''node => {
      const style=getComputedStyle(node),rect=node.getBoundingClientRect(),meta=node.parentElement.getBoundingClientRect();
      return {width:rect.width,height:rect.height,clip:style.clip,clipPath:style.clipPath,
        position:style.position,visibility:style.visibility,left:rect.left,right:rect.right,bottom:rect.bottom,
        metaLeft:meta.left,metaRight:meta.right,stageTop:document.querySelector('#page-area').getBoundingClientRect().top};
    }''')
    assert geometry['width'] >= 80 and geometry['height'] >= 14, geometry
    assert geometry['clip'] == 'auto' and geometry['clipPath'] == 'none', geometry
    assert geometry['position'] == 'static' and geometry['visibility'] == 'visible', geometry
    assert geometry['left'] >= geometry['metaLeft'] and geometry['right'] <= geometry['metaRight'] + 1, geometry
    assert geometry['left'] >= 0 and geometry['right'] <= width, geometry
    assert geometry['bottom'] <= geometry['stageTop'], geometry
    assert not page.get_by_role('button', name='收起', exact=True).is_visible()
    page.wait_for_timeout(400)
    assert control['progress_reads'] == []
    assert sum(path.endswith('/open') and body.get('handle') == 'handle-A' for path, body in calls) == member_opens
    assert not page.locator('#reader-book-end').is_visible()
    page.locator('#reader-progress-next-book').click()
    page.wait_for_function("() => document.querySelector('#reader-title').textContent === 'B' && window.rendition?.getPosition()?.chunkProgressRatio > .3")
    assert page.locator('.reader-sync-capability').count() == 0
    assert not any(path.endswith('/A') for path in control['progress_reads'])
    assert errors == []


def test_wheel_requires_a_new_burst_after_reaching_end(reader):
    page, _, _, _, errors, _ = reader
    tail(page, 180)
    bounds = page.locator('#page-area').bounding_box()
    page.mouse.move(bounds['x'] + bounds['width'] / 2, bounds['y'] + bounds['height'] - 100)
    page.mouse.wheel(0, 450)
    page.wait_for_timeout(60)
    assert page.locator('#reader-book-end').is_visible()
    page.mouse.wheel(0, 90)
    page.wait_for_timeout(80)
    assert page.locator('#reader-title').inner_text() == 'A'
    page.wait_for_timeout(250)
    page.mouse.wheel(0, 90)
    page.wait_for_function("() => document.querySelector('#reader-title').textContent === 'B'")
    assert errors == []
