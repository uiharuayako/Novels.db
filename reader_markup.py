"""Build cached, independently renderable HTML sections for the scrolling reader."""
import codecs
import json
import re
import tempfile
from html import escape
from pathlib import Path
from urllib.parse import quote, unquote
from zipfile import ZIP_DEFLATED, ZipFile

from cmarkgfm import github_flavored_markdown_to_html
from cmarkgfm.cmark import Options
from lxml import etree, html


SECTION_BYTES = 64 * 1024
CONTAINERS = {'body', 'main', 'article', 'section', 'div', 'aside', 'nav', 'header', 'footer', 'blockquote'}
HEADINGS = {f'h{level}' for level in range(1, 7)}
SPLITTABLE = {'p', 'span', 'a', 'b', 'i', 'strong', 'em', 'ul', 'ol', 'li', 'dl', 'dd', 'pre', 'code'}


def document_tree(path, format_):
    raw = Path(path).read_bytes()
    if format_ == 'md':
        text = github_flavored_markdown_to_html(raw.decode('utf-8-sig', 'replace'),
                                                options=Options.CMARK_OPT_UNSAFE | Options.CMARK_OPT_FOOTNOTES)
        raw = text.encode('utf-8')
    else:
        charset = re.search(rb'''(?:<meta\b[^>]*?\bcharset|<\?xml\b[^>]*?\bencoding)\s*=\s*["']?\s*([\w.-]+)''', raw[:4096], re.I)
        if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
            raw = raw.decode('utf-16', 'replace').encode('utf-8')
        elif charset:
            raw = raw.decode(charset[1].decode('ascii'), 'replace').encode('utf-8')
    parser = html.HTMLParser(encoding='utf-8', remove_comments=True, no_network=True, huge_tree=True)
    try:
        root = html.document_fromstring(raw, parser=parser)
    except etree.ParserError as error:
        raise ValueError('文档没有可读正文') from error
    if parser.error_log.filter_from_fatals():
        raise ValueError(str(parser.error_log.last_error.message))
    for node in root.xpath('//script|//iframe|//object|//embed|//form|//base|//meta[@http-equiv]'):
        node.drop_tree()
    for node in root.iter(etree.Element):
        for key in list(node.attrib):
            if (key.startswith('on') or key in ('srcdoc', 'autofocus', 'formaction') or
                    (key in ('href', 'src', 'xlink:href') and node.get(key).lstrip().lower().startswith('javascript:'))):
                del node.attrib[key]
    return root


def opening(node):
    attrs = ''.join(f' {key}="{escape(value)}"' for key, value in node.attrib.items() if re.fullmatch(r'[\w:.-]+', key))
    return f'<{node.tag}{attrs}>'.encode('utf-8')


def text_parts(text):
    for start in range(0, len(text or ''), SECTION_BYTES // 2):
        yield escape(text[start:start + SECTION_BYTES // 2], quote=False).encode('utf-8'), start > 0


def number_list_items(node):
    def integer(value, default):
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    items = node.findall('li')
    step = -1 if 'reversed' in node.attrib else 1
    current = integer(node.get('start'), len(items) if step == -1 else 1)
    for item in items:
        current = integer(item.get('value'), current)
        item.set('value', str(current))
        current += step


def flow_parts(node):
    yield from text_parts(node.text)
    for child in node:
        data = None if child.tag in CONTAINERS else html.tostring(child, encoding='utf-8', with_tail=False)
        if data is None or (len(data) > SECTION_BYTES and child.tag in SPLITTABLE):
            if child.tag == 'ol':
                number_list_items(child)
            for section in section_bodies(child):
                yield section, True
        else:
            yield data, True
        yield from text_parts(child.tail)


def section_bodies(node):
    start, end = opening(node), f'</{node.tag}>'.encode()
    parts, size = [], 0
    for data, boundary in flow_parts(node):
        if boundary and size >= SECTION_BYTES:
            yield start + b''.join(parts) + end
            parts, size = [], 0
        parts.append(data)
        size += len(data)
    if parts or not len(node):
        yield start + b''.join(parts) + end


def write_sections(archive, path, format_):
    root = document_tree(path, format_)
    body = root.body
    styles = []
    for node in root.xpath('//style|//link[@rel]'):
        if node.tag == 'style' or 'stylesheet' in node.get('rel', '').lower().split():
            styles.append(html.tostring(node, encoding='utf-8', with_tail=False))
        node.drop_tree()
    if body is None or not (any(text.strip() for text in body.itertext()) or body.xpath('.//img|.//svg|.//video')):
        raise ValueError('文档没有可读正文')
    archive.writestr('head', b'<!doctype html>' + opening(root) + b'<head><meta charset="utf-8"><base href="">'
                     + b''.join(styles) + b'</head>')
    ids = set(body.xpath('.//*[@id]/@id'))
    suffixes = {}
    for number, heading in enumerate(body.iter(*sorted(HEADINGS))):
        if heading.get('id'):
            continue
        slug = re.sub(r'[^\w -]', '', heading.text_content().strip().lower()).replace(' ', '-') if format_ == 'md' else ''
        stem = slug or f'reader-heading-{number}'
        fragment, suffix = stem, suffixes.get(stem, 0)
        while fragment in ids:
            suffix += 1
            fragment = f'{stem}-{suffix}'
        suffixes[stem] = suffix
        heading.set('id', fragment)
        ids.add(fragment)
    linked = {unquote(href[1:]) for href in body.xpath('.//a[starts-with(@href,"#")]/@href')}
    chapters, toc, fragments = [], [], {}
    for index, section in enumerate(section_bodies(body)):
        href = f'section-{index}.html'
        archive.writestr(href, section)
        parsed = html.document_fromstring(section, parser=html.HTMLParser(encoding='utf-8', huge_tree=True))
        label = ''
        for node in parsed.xpath('//*[@id or @name]'):
            for key in (node.get('id'), node.get('name')):
                if key in linked:
                    fragments.setdefault(key, index)
            if node.tag in HEADINGS and node.text_content().strip():
                title = node.text_content().strip()
                label = label or title
                toc.append({'label': title, 'href': href + '#' + quote(node.get('id'), safe=''), 'depth': int(node.tag[1]) - 1})
        chapters.append({'href': href, 'size': len(section), 'label': label or f'正文区段 {index + 1}'})
    title = root.xpath('string(/html/head/title)').strip() or Path(path).stem
    archive.writestr('manifest.json', json.dumps({'title': title, 'chapters': chapters, 'toc': toc, 'fragments': fragments,
                                                  'start_path': chapters[0]['href']}, ensure_ascii=False))


def cached_book(path, format_, destination):
    if not destination.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=destination.parent) as work:
            temporary = Path(work, 'book.zip')
            with ZipFile(temporary, 'w', ZIP_DEFLATED, compresslevel=1) as archive:
                write_sections(archive, path, format_)
            temporary.replace(destination)
    return destination
