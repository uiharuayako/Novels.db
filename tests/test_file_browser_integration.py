"""Read real temporary folders without querying or changing the Recoll index."""
import json
import os
import shlex
import shutil
import sqlite3
import threading
import time
import uuid
from urllib.parse import parse_qs, urlsplit

import pytest
from webtest import TestApp

import file_browser
from test_webui_integration import recoll_index, site, client_for, local_url


@pytest.fixture
def browse_folder(site):
    root = site.books / ('browse-' + uuid.uuid4().hex)
    root.mkdir()
    try:
        yield root
    finally:
        site.module.file_pager.close()
        shutil.rmtree(root, ignore_errors=True)


def listing(client, path='', cursor=''):
    return client.get('/api/files', dict(path=str(path), cursor=cursor)).json


@pytest.fixture
def mixed_byte_names(browse_folder):
    regular = browse_folder / '可读.txt'
    regular.write_text('混合名称目录中的正常正文。', encoding='utf-8')
    raw_root = os.fsencode(browse_folder)
    raw_file = raw_root + b'/\xce\xc4\xbc\xfe.txt'
    raw_directory = raw_root + b'/\xff-<folder>'
    with open(raw_file, 'wb') as output:
        output.write(b'legacy name')
    os.mkdir(raw_directory)
    os.symlink(raw_file, raw_root + b'/alias-file.txt')
    os.symlink(raw_directory, raw_root + b'/alias-directory')
    os.symlink(os.fsencode(regular), raw_root + b'/alias-\xfe.txt')
    return dict(root=browse_folder, regular=regular, raw_directory=raw_directory,
                unavailable={'\\xce\\xc4\\xbc\\xfe.txt', '\\xff-<folder>', 'alias-file.txt',
                             'alias-directory', 'alias-\\xfe.txt'})


def test_non_utf8_names_and_symlink_targets_do_not_block_siblings(site, mixed_byte_names):
    root = mixed_byte_names['root']
    expected = mixed_byte_names['unavailable'] | {'可读.txt'}
    for number in range(125):
        name = f'page-{number:03d}.txt'
        (root / name).touch()
        expected.add(name)
    client = client_for(site, prefix='/library')
    items, cursor = [], ''
    while True:
        response = client.get('/api/files', dict(path=str(root), cursor=cursor))
        response.body.decode('utf-8')
        data = response.json
        assert data['scanned'] <= 100 and len(data['items']) <= 100
        items.extend(data['items'])
        cursor = data['next_cursor']
        if not cursor:
            break
    assert {item['name'] for item in items} == expected and len(items) == len(expected)
    unavailable = [item for item in items if item.get('unavailable_reason')]
    assert {item['name'] for item in unavailable} == mixed_byte_names['unavailable']
    assert {item['kind'] for item in unavailable} == {'file', 'directory'}
    for item in unavailable:
        assert item['url'] is None and item['path'] is None and not item['supported']
        assert 'UTF-8' in item['unavailable_reason']
    normal = next(item for item in items if item['name'] == '可读.txt')
    opened = client.get(local_url(normal['url']).removeprefix('/library'), status=303)
    document_id = parse_qs(urlsplit(opened.location).query)['document_id'][0]
    book = client.get('/api/reader/book', {'document_id': document_id}).json['book']
    assert client.get(local_url(book['url']).removeprefix('/library')).text == mixed_byte_names['regular'].read_text(encoding='utf-8')
    for alias in ('alias-file.txt', 'alias-directory'):
        client.get('/api/files', {'path': str(root / alias)}, status=400)
        client.get('/files/open', {'path': str(root / alias)}, status=400)

    # A configured root can itself be a normal-name symlink to such a folder.
    root_alias = site.root / 'root-alias'
    root_alias.symlink_to(os.fsdecode(mixed_byte_names['raw_directory']), target_is_directory=True)
    (site.config / 'recoll.conf').write_text(site.base_config + f'topdirs = {site.books} {root_alias}\n', encoding='utf-8')
    roots = listing(client)['items']
    assert len(roots) == 2
    disabled = next(item for item in roots if item.get('unavailable_reason'))
    assert disabled['name'] == '\\xff-<folder>' and disabled['url'] is None and disabled['path'] is None


def test_roots_nested_names_and_direct_reader_open(site, browse_folder, monkeypatch):
    extra = site.root / '另一 文库 & <资料>'
    extra.mkdir()
    conf = site.root / 'extra-conf'
    conf.mkdir()
    (conf / 'recoll.conf').write_text('topdirs = ' + shlex.quote(str(extra)) + '\n', encoding='utf-8')
    monkeypatch.setenv('RECOLL_EXTRACONFDIRS', str(conf))
    child = browse_folder / '中文 空格 & <img src=x onerror=alert(1)>'
    child.mkdir()
    book = child / '尚未索引 & <小说>.txt'
    book.write_text('freshunindexedtoken 正确的文件正文', encoding='utf-8')
    (child / 'unknown.bin').write_bytes(b'unsupported')
    (child / '.secret.txt').write_text('hidden', encoding='utf-8')
    (child / 'empty').mkdir()
    client = client_for(site, prefix='/library')
    navigation = client.get('/files').html.select('.account-nav a')
    assert [item.get_text() for item in navigation][:3] == ['发现文档', '文件浏览', '我的书架']
    assert navigation[1]['aria-current'] == 'page'
    assert {item['path'] for item in listing(client)['items']} == {str(site.books), str(extra)}
    parent = listing(client, browse_folder)
    assert [item['name'] for item in parent['items']] == [child.name]
    data = listing(client, child)
    assert {item['name'] for item in data['items']} == {book.name, 'unknown.bin', 'empty'}
    assert data['breadcrumbs'][-1]['name'] == child.name
    assert data['parent'].startswith('/library/files?')
    assert listing(client, child / 'empty')['items'] == []
    unsupported = next(item for item in data['items'] if item['name'] == 'unknown.bin')
    assert not unsupported['supported'] and unsupported['url'] is None
    with sqlite3.connect(site.store.path) as connection:
        assert connection.execute('SELECT count(*) FROM document_refs').fetchone()[0] == 0
    item = next(item for item in data['items'] if item['name'] == book.name)
    opened = client.get(local_url(item['url']).removeprefix('/library'), status=303)
    assert opened.location.startswith('http://localhost:80/library/reader?')
    query = parse_qs(urlsplit(opened.location).query)
    reader = client.get(local_url(opened.location).removeprefix('/library'))
    assert reader.html.select_one('a[aria-label="返回文件浏览"]')['href'] == query['return_to'][0]
    metadata = client.get('/api/reader/book', {'document_id': query['document_id'][0]}).json['book']
    body = client.get(local_url(metadata['url']).removeprefix('/library'))
    assert body.text == book.read_text(encoding='utf-8')
    book.unlink()
    client.get('/files/open', {'path': str(book)}, status=404)


def test_boundaries_cursors_and_open_revalidation(site, browse_folder):
    outside = site.root / 'outside'
    outside.mkdir()
    secret = outside / 'secret.txt'
    secret.write_text('must not leak', encoding='utf-8')
    (browse_folder / 'escape').symlink_to(outside, target_is_directory=True)
    (browse_folder / 'escape.txt').symlink_to(secret)
    (browse_folder / '.hidden').mkdir()
    (browse_folder / '.hidden' / 'secret.txt').write_text('hidden', encoding='utf-8')
    (browse_folder / 'hidden-alias').symlink_to(browse_folder / '.hidden', target_is_directory=True)
    os.mkfifo(browse_folder / 'pipe.txt')
    for number in range(220):
        (browse_folder / f'book-{number}.txt').touch()
    alice, bob = client_for(site), client_for(site, 'bob')
    TestApp(site.app).get('/api/files', status=401)
    TestApp(site.app).get('/files', status=302)
    for path in (outside, browse_folder / 'escape', browse_folder / '.hidden'):
        alice.get('/api/files', {'path': str(path)}, status=403)
    alice.get('/api/files', {'path': str(browse_folder / '..')}, status=400)
    alice.get('/api/files', {'path': '/etc'}, status=403)
    alice.get('/files/open', {'path': str(browse_folder / 'escape.txt')}, status=403)
    alice.get('/files/open', {'path': str(browse_folder / 'pipe.txt')}, status=404)
    data = listing(alice, browse_folder)
    assert all(item['name'].startswith('book-') for item in data['items'])
    cursor = data['next_cursor']
    for client, token in ((bob, cursor), (alice, 'forged')):
        client.get('/api/files', {'path': str(browse_folder), 'cursor': token}, status=409)
    next_page = listing(alice, browse_folder, cursor)
    assert next_page['items']
    alice.get('/api/files', {'path': str(browse_folder), 'cursor': cursor}, status=409)
    target = browse_folder / 'book-0.txt'
    target.unlink()
    target.symlink_to(secret)
    alice.get('/files/open', {'path': str(target)}, status=403)
    unreadable = browse_folder / 'book-1.txt'
    unreadable.chmod(0)
    try:
        alice.get('/files/open', {'path': str(unreadable)}, status=403)
    finally:
        unreadable.chmod(0o600)
    private = browse_folder / 'unreadable'
    private.mkdir()
    private.chmod(0)
    try:
        alice.get('/api/files', {'path': str(private)}, status=403)
    finally:
        private.chmod(0o700)


def test_large_directory_scans_once_with_bounded_pages(site, browse_folder, monkeypatch):
    total = 3207
    for number in range(total):
        (browse_folder / f'item-{number:05d}.txt').touch()
    for number in range(125):
        (browse_folder / f'.hidden-{number}').touch()
    actual_scandir = file_browser.scandir
    calls = dict(opened=0, yielded=0, closed=0)

    class CountedIterator:
        def __init__(self, path):
            calls['opened'] += 1
            self.iterator = actual_scandir(path)

        def __next__(self):
            item = next(self.iterator)
            calls['yielded'] += 1
            return item

        def close(self):
            calls['closed'] += 1
            self.iterator.close()

    monkeypatch.setattr(file_browser, 'scandir', CountedIterator)
    client = client_for(site)
    seen, cursor, pages, timings, sizes = [], '', 0, [], []
    while True:
        start = time.monotonic()
        data = listing(client, browse_folder, cursor)
        timings.append(time.monotonic() - start)
        pages += 1
        assert data['scanned'] <= 100 and len(data['items']) <= 100
        assert calls['yielded'] <= pages * 100
        sizes.append(len(json.dumps(data, ensure_ascii=False).encode()))
        seen.extend(item['name'] for item in data['items'])
        cursor = data['next_cursor']
        if not cursor:
            break
    assert len(seen) == total and len(set(seen)) == total
    assert calls == dict(opened=1, yielded=total + 125, closed=1)
    assert not site.module.file_pager._cursors
    with sqlite3.connect(site.store.path) as connection:
        assert connection.execute('SELECT count(*) FROM document_refs').fetchone()[0] == 0
    print(dict(entries=total, pages=pages, first_ms=round(timings[0] * 1000, 2),
               deep_ms=round(timings[-2] * 1000, 2), largest_response_bytes=max(sizes), **calls))


def test_cursor_capacity_eviction_and_expiry_close_resources(tmp_path, monkeypatch):
    for number in range(5):
        (tmp_path / str(number)).touch()
    pager = file_browser.DirectoryPager()
    pager.page_size, pager.max_cursors, pager.ttl = 2, 2, .08
    actual_scandir = file_browser.scandir
    opened = []

    class Tracked:
        def __init__(self, path):
            self.iterator, self.closed = actual_scandir(path), False
            opened.append(self)

        def __next__(self):
            return next(self.iterator)

        def close(self):
            self.closed = True
            self.iterator.close()

    monkeypatch.setattr(file_browser, 'scandir', Tracked)
    try:
        _, first = pager.read(str(tmp_path), 'alice', 'scope')
        pager.read(str(tmp_path), 'alice', 'scope')
        _, latest = pager.read(str(tmp_path), 'alice', 'scope')
        assert len(pager._cursors) == 2 and opened[0].closed
        with pytest.raises(file_browser.CursorExpired):
            pager.read(str(tmp_path), 'alice', 'scope', first)
        deadline = time.monotonic() + 2
        while not all(item.closed for item in opened) and time.monotonic() < deadline:
            time.sleep(.01)
        assert all(item.closed for item in opened) and not pager._cursors
        with pytest.raises(file_browser.CursorExpired):
            pager.read(str(tmp_path), 'alice', 'scope', latest)
        assert pager.read(str(tmp_path), 'alice', 'scope')[0]
    finally:
        pager.close()


def test_slow_directory_does_not_block_other_directory_reads(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    slow, fast = tmp_path / 'slow', tmp_path / 'fast'
    slow.mkdir()
    fast.mkdir()
    (slow / 'slow.txt').touch()
    (fast / 'fast.txt').touch()
    entered, release = threading.Event(), threading.Event()
    actual_scandir = file_browser.scandir

    class SlowIterator:
        def __init__(self):
            self.iterator = actual_scandir(slow)

        def __next__(self):
            entered.set()
            assert release.wait(3), 'test did not release the slow directory'
            return next(self.iterator)

        def close(self):
            self.iterator.close()

    monkeypatch.setattr(file_browser, 'scandir', lambda path: SlowIterator() if path == str(slow) else actual_scandir(path))
    pager = file_browser.DirectoryPager()
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending = pool.submit(pager.read, str(slow), 'alice', 'scope')
            try:
                assert entered.wait(2)
                other = pool.submit(pager.read, str(fast), 'alice', 'scope')
                assert other.result(timeout=1)[0][0].name == 'fast.txt'
            finally:
                release.set()
            assert pending.result(timeout=2)[0][0].name == 'slow.txt'
    finally:
        pager.close()
