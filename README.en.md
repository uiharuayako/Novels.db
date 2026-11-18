<div align="center">
  <img src="static/novels-db.svg" width="76" height="76" alt="Novels.db logo">
  <h1>Novels.db <sup>ND</sup></h1>
  <p><strong>A full-text search reader for very large novel libraries</strong></p>
  <p><a href="README.md">简体中文</a> · <strong>English</strong></p>
  <p><a href="#quick-start">Quick start</a> · <a href="docs/README.md">Documentation</a> · <a href="CONTRIBUTING.md">Contributing</a> · <a href="https://github.com/uiharuayako/Novels.db/issues">Issues</a></p>
</div>

**Novels.db (ND)** is based primarily on **[recoll-webui](https://framagit.org/medoc92/recollwebui)**, with [Recoll](https://www.recoll.org/) providing indexing and search. Remember a line of dialogue but not the title? Search the text, open the matching novel, save it to your bookshelf and resume where you left off.

The project targets search and reading across very large novel libraries. Capacity and query performance depend on the collection, Recoll index and deployment resources. ND connects to an existing index; the operator manages document collection, index creation and updates.

![Novels.db discovery page with full-text search, recent reading and novel recommendations](docs/images/discovery.png)

## From search to reading

| Feature | What it provides |
| --- | --- |
| Full-text search | Recoll query syntax, phrases, directory/date filters, match snippets and CSV / JSON export. |
| Discovery | Continue recent books, revisit search recommendations and explore daily picks. |
| Personal bookshelf | Save books or folders, switch grid/list views and resume reading. |
| Browser reader | Continuous reading, contents, in-book search, typography controls and focus mode. |
| Accounts and sync | Per-account history, progress and preferences, with explicit choices for conflicting positions. |
| Sharing | Expiring links to books or folders, revocable by the owner. |

### Actual application screenshots

These are real application pages using a disposable Recoll index, isolated accounts and original demo stories. They contain no personal library data. The interface is currently primarily Simplified Chinese, with desktop and mobile layouts.

**Find a line inside a story.** Search results keep snippets, filters and reading actions together.

![Full-text results showing novel titles, highlighted matches and reading actions](docs/images/search.png)

**Keep your next read close.** The bookshelf stores favorites and synced progress.

![Personal bookshelf list with novels, synced progress and resume actions](docs/images/bookshelf.png)

**Open a book and keep reading.** Contents and continuous text share a warm paper reading canvas.

![Novel reader with a chapter outline and continuous text in the sepia theme](docs/images/reader.png)

## How it works

```text
Novel files → Recoll index → Novels.db → Search and reading in the browser
                              └─ SQLite: accounts, bookshelf, history and progress
```

The backend uses Python, Bottle, Waitress and SQLite. Reader assets ship with the repository and require no runtime CDN downloads. All accounts share the operator's configured library while keeping separate personal records. Anyone holding a public share link can read its contents without signing in; configure sharing to match the library's access policy.

Readable formats include TXT, Markdown, HTML, XML, MHTML, EPUB, MOBI, AZW / AZW3, FB2, CHM, DOCX, PDF, CBZ, CBR, CBT and CB7. Layout and positioning support vary by format. CHM requires `7z`; text search in scanned PDFs requires an OCR text layer. Folder reading scans up to 1,000 readable files. Recoll container `ipath` entries support preview/download rather than direct reading. Moved files need to be found again.

## Quick start

**Docker Compose is recommended for production; NAS deployments can use Dockge.** The host needs Docker Engine, Compose and existing Recoll configuration, index and source documents. Host Python is not required. Native Python instructions are in [Developer setup](#developer-setup-native-python) below.

The container reads an **existing index: do not rebuild it to deploy the WebUI**. It never runs `recollindex`. The image uses Debian's Recoll and system Python, with the existing `requirements.txt` installed in a `--system-site-packages` virtual environment. It includes `7z` for CHM and LibreOffice Writer for Word previews. The default numeric identity is `1000:1000`; choose a nonzero UID/GID with read access to mounted files.

### 1. Prepare Docker / Dockge directories and configuration

On the NAS, place `compose.yaml` and `.env` in **`/mnt/user/appdata/dockge/stacks/recoll-webui/`**. Save the repository's `compose.yaml` there and run subsequent Docker commands from that directory. Directory preparation and destination restore examples use the NAS root administration terminal; on another Linux host, run `sudo -i` first.

```bash
STACK=/mnt/user/appdata/dockge/stacks/recoll-webui
install -d -m 755 "$STACK" "$STACK/recoll-config"
cd "$STACK"
```

Copy only **`recoll.conf`** from the source to `$STACK/recoll-config/`. If the deployment actually uses custom `fields`, `mimemap`, `mimeconf` or other configuration files, copy those files too. **Do not copy the whole Recoll configuration directory**: its index, `aspdict`, logs and backups are unnecessary. Mount the existing index directly. Other custom files referenced by the configuration must also be readable inside the container.

Configuration, source documents and the index are read-only mounts. SQLite, its `.secret`, `.registration.json` and lock files live together in a separate persistent **local filesystem directory, outside SMB/NFS storage**. The root filesystem is read-only; conversion caches use `/tmp`.

The following defaults use the existing smaller library. Keep the original VM absolute paths inside the container and adjust only NAS mount sources. Library identity includes the Recoll configuration directory, and document identities and progress depend on original paths:

| Content | Fixed container target | Default VM source | NAS source for the smaller library |
| --- | --- | --- | --- |
| Recoll configuration | `/home/uiharu/.recoll-novel` | Same as target | `/mnt/user/appdata/dockge/stacks/recoll-webui/recoll-config` |
| Original novels | `/mnt/share/migusuper/fastFolder/Novel` | Same as target | `/mnt/migusuper/fastFolder/Novel` |
| Recoll index | `/mnt/share/migusuper/fastFolder/re_index` | Same as target | `/mnt/migusuper/fastFolder/re_index` |
| Application state | `/var/lib/recoll-webui` | Same as target | `/mnt/cache/appdata/recoll-webui/state` (local disk) |

Preserve `topdirs = /mnt/share/migusuper/fastFolder/Novel` and `dbdir = /mnt/share/migusuper/fastFolder/re_index` in `recoll.conf`. Create `.env` in the stack directory:

```dotenv
RECOLL_WEBUI_IMAGE=ghcr.io/uiharuayako/novels.db:latest
RECOLL_WEBUI_UID=1000
RECOLL_WEBUI_GID=1000
RECOLL_WEBUI_BIND=127.0.0.1
RECOLL_WEBUI_PORT=8080
RECOLL_CONFIG_SOURCE=/mnt/user/appdata/dockge/stacks/recoll-webui/recoll-config
RECOLL_LIBRARY_SOURCE=/mnt/migusuper/fastFolder/Novel
RECOLL_INDEX_SOURCE=/mnt/migusuper/fastFolder/re_index
RECOLL_STATE_SOURCE=/mnt/cache/appdata/recoll-webui/state
```

For other installations, adapt the source paths to actual storage; `state` must be on a local filesystem. Create all source directories first: Compose refuses missing paths instead of creating empty mounts. Ensure the selected UID/GID can traverse the configuration, index and library directories and read configuration files. Add `group_add` if supplementary group access is needed; do not recursively change library ownership.

```bash
# In the deployment host's administration terminal; match UID/GID to .env.
install -d -o 1000 -g 1000 -m 700 /mnt/cache/appdata/recoll-webui/state
chmod 755 "$STACK/recoll-config"
chmod 644 "$STACK/recoll-config/recoll.conf"
docker compose config --quiet
```

Custom configuration files must also be readable by the selected UID. Resolved symlink paths must be visible inside the container. Other deployments must adapt the fixed targets while preserving their original library identity.

### 2. Select an image and start

`compose.yaml` defaults to `ghcr.io/uiharuayako/novels.db:latest`. **Select an image version that has been successfully published and that you can pull.** For a first publication, complete the GHCR publishing workflow first, or [build locally](#local-builds-and-ghcr-ci). Private packages require `docker login ghcr.io`; anonymous pulls require a public package. When using a GHCR version, run:

```bash
docker compose pull
```

Initialize accounts only for a new deployment. For existing account data, use the migration and restore section below and skip `init`:

```bash
docker compose run --rm webui python manage.py init --username admin
docker compose up -d
```

Initialization prompts for a 15–128 character password. On first login, change it and sign in again. Open [http://127.0.0.1:8080/](http://127.0.0.1:8080/). Use a host reverse proxy or SSH tunnel for remote access, or set `RECOLL_WEBUI_BIND` to the host's LAN address for direct LAN access. For an HTTPS reverse proxy, set `RECOLL_WEBUI_TRUSTED_PROXIES` to the actual proxy addresses and `RECOLL_WEBUI_PROXY_SCHEME=https`. To upgrade, back up first, then run `docker compose stop webui`, `docker compose pull` and `docker compose up -d`. Recreating a container preserves the host's `state` directory.

### Migration, backup and restore

Rehearse with a disposable destination directory and a separate port while keeping the original service running. At final cutover, stop all source workers and export a fresh snapshot so later bookshelf and progress changes are included. Run the following on the source host as the service's OS account, using its actual database path and Python environment:

```bash
set -eu
SOURCE_DB=/actual/service/path/app.sqlite3
BACKUP_DIR=$(mktemp -d)
.venv/bin/python manage.py --db "$SOURCE_DB" backup "$BACKUP_DIR/app.sqlite3"
install -m 600 "$SOURCE_DB.secret" "$BACKUP_DIR/app.sqlite3.secret"
if [ -f "$SOURCE_DB.registration.json" ]; then
  install -m 600 "$SOURCE_DB.registration.json" "$BACKUP_DIR/app.sqlite3.registration.json"
else
  printf '%s\n' 'The source has no registration settings file; restore with registration closed by default.'
fi
```

Securely transfer the snapshot directory to `state/restore/` on the destination, retaining these filenames. Use `manage.py backup` for the database; do not copy a live SQLite file. Signing keys and registration settings are not included in the database backup.

Run the following in the **destination host's root administration terminal**, using `sudo -i` first on another Linux host. `state/restore` may be a `0700` directory owned by another numeric UID; an ordinary operator's `if [ -f ... ]` cannot reliably detect its files. The example explicitly copies registration settings and fails if they cannot be read. **Only if the source is confirmed to have no such file, omit the second `install` and move any existing target `.registration.json` outside the mount as a backup**, leaving registration closed by default. Before replacing an existing target, back up its database and both companion files, and stop every target worker:

```bash
set -eu
cd /mnt/user/appdata/dockge/stacks/recoll-webui
STATE=/mnt/cache/appdata/recoll-webui/state
docker compose stop webui
install -o 1000 -g 1000 -m 600 "$STATE/restore/app.sqlite3.secret" "$STATE/app.sqlite3.secret"
install -o 1000 -g 1000 -m 600 "$STATE/restore/app.sqlite3.registration.json" "$STATE/app.sqlite3.registration.json"
chown -R 1000:1000 "$STATE"
chmod 700 "$STATE" "$STATE/restore"
docker compose run --rm webui python manage.py restore /var/lib/recoll-webui/restore/app.sqlite3 --workers-stopped
docker compose up -d
```

Match UID/GID in the commands to `.env`. Restoration preserves accounts, bookshelf, history and progress, and revokes old sessions, so users must sign in again. Do not run `init` before restoring and generate a replacement key. Mount the existing index unchanged; maintenance stays with the existing external indexing jobs.

To make a container-side backup, write to a new filename in persistent state:

```bash
docker compose exec webui python manage.py backup /var/lib/recoll-webui/backup-before-upgrade.sqlite3
```

Separately save `app.sqlite3.secret` and `app.sqlite3.registration.json` (if present), plus the Recoll configuration, index and original documents.

### Local builds and GHCR CI

Published GHCR images are recommended for production. To build locally, run the build in the source directory and keep the same image selection for subsequent Compose commands:

```bash
docker build -t recoll-webui:local .
export RECOLL_WEBUI_IMAGE=recoll-webui:local
cd /mnt/user/appdata/dockge/stacks/recoll-webui
docker compose run --rm webui python -c 'from recoll import recoll, rclextract, rclconfig'
# Initialize or restore data following the quick start before starting.
docker compose up -d
```

For Dockge, also change `RECOLL_WEBUI_IMAGE` in the stack's `.env` to `recoll-webui:local` and skip GHCR pulls. `.github/workflows/container.yml` builds and checks PR images without publishing. Pushes to the default branch (`master`) and Git tags publish to GHCR after runtime checks; other branches do not publish. The default branch produces `latest`, tag builds retain the Git tag name, and each published build also has a `sha-…` tag. Pin a tag or digest using `RECOLL_WEBUI_IMAGE` for production. Allow the workflow to write Packages. The build context includes only application code, runtime requirements and bundled assets.

## Developer setup (native Python)

Use this section for development and debugging; production deployments should follow the Docker workflow above. Requirements are Linux, Python 3 and system-installed Recoll Python bindings. Recoll is a system dependency, not a pip package; the interpreter must be able to import its system extensions. Reuse existing configuration and indexes: **do not rebuild an existing index**. If no index exists, create one for a separate test library using the [operations guide](docs/operations.rst). Operators still manage index updates separately.

```bash
git clone https://github.com/uiharuayako/Novels.db.git
cd Novels.db
python3 -m venv --system-site-packages .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -c "from recoll import recoll, rclextract, rclconfig"

export RECOLL_WEBUI_DB_PATH="$HOME/.local/share/recoll-webui/app.sqlite3"
# Only for a new development account database; restore existing accounts instead.
python manage.py init --username admin
python webui-standalone.py -c /path/to/recoll-config
```

Keep the database in a private persistent directory outside source, static assets and the library. Open [http://127.0.0.1:8080/](http://127.0.0.1:8080/). Use `-a` for the bind address, `-p` for the port and `-t` for worker threads; run `python webui-standalone.py --help` for all options. Native WSGI, HTTPS proxy and `SCRIPT_NAME` subpath configuration are covered in the [operations guide](docs/operations.rst) and [systemd guide](README-systemd.rst).

## Maintenance and documentation

| Guide | Contents |
| --- | --- |
| [Documentation index](docs/README.md) | Deployment, reader development and maintainer references |
| [Operations guide](docs/operations.rst) | Full setup, configuration, format constraints, proxies and maintenance (中文) |
| [Account and reading data](docs/accounts-and-history.md) | Registration, permissions, retention and recovery (中文) |
| [systemd deployment](README-systemd.rst) | Service account, persistent storage and scheduled cleanup (English) |
| [Contributing](CONTRIBUTING.md) | Development setup, tests, issues and pull requests (中文 / English) |
| [Origins and licensing](docs/third-party.md) | Upstream projects and bundled dependency notices (中文 / English) |

Run maintenance as the service's OS account with the same database path:

```bash
python manage.py create-user reader --display-name Reader
python manage.py reset-password admin --enable --admin
python manage.py cleanup
python manage.py backup /private/backups/recoll-backup.sqlite3
```

The backup destination must not already exist. Back up the signing key `.secret` and registration settings `.registration.json` separately, together with your Recoll configuration, index and original documents. Before restoration, stop **all** standalone / WSGI workers:

```bash
python manage.py restore /private/backups/recoll-backup.sqlite3 --workers-stopped
```

Back up and stop workers before an upgrade. Registration is closed by default and can be managed by an administrator; no email address is required. Search history, recent reading and progress sync can be controlled separately. Bookshelf records protect their associated progress from normal retention cleanup. See the linked guides for retention periods and access rules.

## Contributions welcome

PRs, bug reports, documentation fixes, translations and reader improvements are welcome. You can participate in English or Chinese, including for your first contribution. Read [CONTRIBUTING.md](CONTRIBUTING.md), and discuss larger changes in an issue first.

## Acknowledgments

This project is based primarily on **[medoc92/recollwebui](https://framagit.org/medoc92/recollwebui)**, which originated from [koniu/recoll-webui](https://github.com/koniu/recoll-webui). Thanks to [Recoll](https://www.recoll.org/) for the search engine, [Koodo Reader / Kookit](https://github.com/koodo-reader/koodo-reader) and [Mozilla PDF.js](https://github.com/mozilla/pdf.js) for reader runtimes, and the reader projects referenced in our design notes. See [origins and licensing](docs/third-party.md).
