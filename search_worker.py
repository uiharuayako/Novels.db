"""Execute Recoll searches in a disposable process, outside the server's GIL.

The pickle streams are private pipes to the parent web process, never HTTP input.
"""
import pickle
import sys

import bottle
import webui


def main():
    query, config, path, cached = pickle.load(sys.stdin.buffer)
    webui._g_snippet_cache.update(cached)
    try:
        result = webui.run_recoll_search(query, config, path)
    except bottle.HTTPError as exc:
        response = {'error': exc.body, 'status': exc.status_code}
    else:
        response = {
            'result': result, 'query': query, 'config': config,
            'snippets': list(webui._g_snippet_cache.items()),
        }
    pickle.dump(response, sys.stdout.buffer)


if __name__ == '__main__':
    main()
