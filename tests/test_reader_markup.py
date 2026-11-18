import json
from zipfile import ZipFile

import pytest
from lxml import html

from reader_markup import cached_book


def test_long_inline_text_ordered_list_and_code_split_without_losing_content(tmp_path):
    path = tmp_path / 'novel.html'
    spans = [f'书中第{number}段。' for number in range(6000)]
    lines = ''.join(f'line {number:05d}\n' for number in range(25000))
    path.write_text('<main><p>' + ''.join(f'<b>{text}</b>' for text in spans) + '</p><ol start="7" reversed>'
                    + ''.join(f'<li>{text}</li>' for text in spans) + '</ol><pre><code>' + lines + '</code></pre></main>')
    with ZipFile(cached_book(path, 'html', tmp_path / 'cache.zip')) as cache:
        manifest = json.loads(cache.read('manifest.json'))
        sections = [html.document_fromstring(cache.read(item['href']), parser=html.HTMLParser(encoding='utf-8'))
                    for item in manifest['chapters']]
    assert sum(bool(tree.xpath('//main/p/b')) for tree in sections) > 1
    assert [text for tree in sections for text in tree.xpath('//p/b/text()')] == spans
    assert sum(bool(tree.xpath('//main/ol/li')) for tree in sections) > 1
    assert [(int(item.get('value')), item.text) for tree in sections for item in tree.xpath('//ol/li')] == list(zip(range(7, 7 - len(spans), -1), spans))
    assert sum(bool(tree.xpath('//main/pre/code')) for tree in sections) > 1
    assert ''.join(text for tree in sections for text in tree.xpath('//pre/code/text()')) == lines


def test_empty_markup_does_not_publish_a_section(tmp_path):
    path = tmp_path / 'empty.html'
    path.write_text('<style>body { color: grey }</style>')
    cache = tmp_path / 'cache.zip'
    with pytest.raises(ValueError, match='没有可读正文'):
        cached_book(path, 'html', cache)
    assert not cache.exists()
