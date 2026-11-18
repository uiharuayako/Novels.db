"""Bounded, single-process directory cursors for the file browser."""
from collections import OrderedDict
from os import scandir
import secrets
import threading
import time


class CursorExpired(ValueError):
    pass


class DirectoryPager:
    page_size = 100
    max_cursors = 32
    ttl = 300

    def __init__(self):
        self._cursors = OrderedDict()
        self._lock = threading.Lock()
        self._timer = None

    def _prune(self):
        now = time.monotonic()
        for token, state in list(self._cursors.items()):
            if state['expires'] <= now:
                self._cursors.pop(token)['iterator'].close()

    def _schedule(self):
        if self._cursors and self._timer is None:
            delay = max(.01, min(state['expires'] for state in self._cursors.values()) - time.monotonic())
            self._timer = threading.Timer(delay, self._expire)
            self._timer.daemon = True
            self._timer.start()

    def _expire(self):
        with self._lock:
            self._timer = None
            self._prune()
            self._schedule()

    def read(self, path, owner, scope, cursor=''):
        """Consume at most one budget, including entries later hidden by the UI.

        Tokens are single-use. A retry after an interrupted response must restart
        the directory; replaying a token never silently skips another page.
        """
        with self._lock:
            self._prune()
            if cursor:
                state = self._cursors.get(cursor)
                if not state or (state['path'], state['owner'], state['scope']) != (path, owner, scope):
                    raise CursorExpired('此分页已失效，请重新加载目录。')
                del self._cursors[cursor]
            else:
                state = None
        # A cursor is removed before consuming it, so independent directories
        # can read concurrently without holding the cache lock across I/O.
        if state is None:
            state = dict(iterator=scandir(path), path=path, owner=owner, scope=scope)
        entries = []
        more = True
        try:
            for _ in range(self.page_size):
                try:
                    entries.append(next(state['iterator']))
                except StopIteration:
                    more = False
                    break
        except OSError:
            state['iterator'].close()
            raise
        with self._lock:
            token = None
            if more:
                while len(self._cursors) >= self.max_cursors:
                    self._cursors.popitem(last=False)[1]['iterator'].close()
                token = secrets.token_urlsafe(24)
                state['expires'] = time.monotonic() + self.ttl
                self._cursors[token] = state
            else:
                state['iterator'].close()
            self._schedule()
            return entries, token

    def close(self):
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None
            for state in self._cursors.values():
                state['iterator'].close()
            self._cursors.clear()
