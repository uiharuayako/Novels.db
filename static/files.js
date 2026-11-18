(() => {
  'use strict';
  const browser = document.querySelector('[data-file-browser]');
  if (!browser) return;
  const list = browser.querySelector('.files-list');
  const crumbs = browser.querySelector('.files-breadcrumbs');
  const status = browser.querySelector('.files-status');
  const next = browser.querySelector('[data-files-next]');
  const refresh = browser.querySelector('[data-files-refresh]');
  const retry = browser.querySelector('[data-files-retry]');
  const parent = browser.querySelector('[data-files-parent]');
  let currentPath = browser.dataset.initialPath;
  let nextCursor = null;
  let controller;
  let requestNumber = 0;
  let pageNumber = 0;

  const pageURL = path => browser.dataset.pageUrl + (path ? '?' + new URLSearchParams({path}) : '');
  const navigate = path => {
    history.pushState(null, '', pageURL(path));
    load(path);
  };
  const directoryLink = (name, path, url) => {
    const link = document.createElement('a');
    link.textContent = name;
    link.href = url;
    link.addEventListener('click', event => {
      if (event.button || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      navigate(path);
    });
    return link;
  };
  const load = async (path, cursor = '') => {
    controller?.abort();
    controller = new AbortController();
    const request = ++requestNumber;
    currentPath = path;
    if (!cursor) pageNumber = 0;
    next.disabled = true;
    refresh.disabled = true;
    retry.hidden = true;
    list.setAttribute('aria-busy', 'true');
    status.textContent = '正在加载…';
    status.dataset.error = 'false';
    const parameters = new URLSearchParams({path});
    if (cursor) parameters.set('cursor', cursor);
    try {
      const response = await fetch(browser.dataset.api + '?' + parameters, {signal: controller.signal, credentials: 'same-origin'});
      const data = await response.json();
      if (request !== requestNumber) return;
      if (!response.ok) throw new Error(data.message || '目录加载失败，请重试。');
      currentPath = data.path;
      nextCursor = data.next_cursor;
      pageNumber += 1;
      browser.querySelector('#files-heading').textContent = data.title;
      crumbs.replaceChildren(...data.breadcrumbs.map(item => directoryLink(item.name, item.path, item.url)));
      parent.hidden = !data.parent;
      if (data.parent) parent.href = data.parent;
      const rows = data.items.map(item => {
        const row = document.createElement('li');
        row.className = 'files-row';
        row.dataset.kind = item.kind;
        const icon = document.createElement('span');
        icon.className = 'files-icon';
        icon.setAttribute('aria-hidden', 'true');
        icon.textContent = item.kind === 'directory' ? '▱' : '▤';
        const name = item.url && item.kind === 'directory' ? directoryLink(item.name, item.path, item.url) : document.createElement(item.url ? 'a' : 'span');
        name.className = 'files-name';
        name.textContent = item.name;
        name.title = item.name;
        if (item.kind === 'file' && item.url) name.href = item.url;
        const detail = document.createElement('span');
        detail.className = 'files-detail';
        detail.textContent = item.unavailable_reason || (item.kind === 'directory' ? '文件夹 →' : item.supported ? item.format.toUpperCase() + ' · 阅读 →' : '暂不支持在线阅读');
        row.append(icon, name, detail);
        return row;
      });
      list.replaceChildren(...rows);
      next.hidden = !nextCursor;
      status.textContent = rows.length ? '' : nextCursor ? '本批没有可显示的条目，可继续下一页。' : pageNumber > 1 ? '已到目录末尾，没有更多可显示的条目。' : '此目录没有可显示的文件或文件夹。';
      browser.querySelector('[data-files-count]').textContent = data.path ? `第 ${pageNumber} 批 · 本页 ${rows.length} 项` : `${rows.length} 个文库目录`;
    } catch (error) {
      if (request !== requestNumber || error.name === 'AbortError') return;
      list.replaceChildren();
      nextCursor = null;
      next.hidden = true;
      status.textContent = error.message || '目录加载失败，请重试。';
      status.dataset.error = 'true';
      retry.hidden = false;
      browser.querySelector('[data-files-count]').textContent = '';
    } finally {
      if (request === requestNumber) {
        list.removeAttribute('aria-busy');
        next.disabled = false;
        refresh.disabled = false;
      }
    }
  };
  parent.addEventListener('click', event => {
    if (event.button || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    navigate(new URL(parent.href).searchParams.get('path') || '');
  });
  next.addEventListener('click', () => { if (!next.disabled && nextCursor) load(currentPath, nextCursor); });
  refresh.addEventListener('click', () => load(currentPath));
  retry.addEventListener('click', () => load(currentPath));
  window.addEventListener('popstate', () => load(new URL(location.href).searchParams.get('path') || ''));
  load(currentPath);
})();
