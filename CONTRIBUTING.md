# 参与 Novels.db / Contributing

欢迎 PR！修复一个问题、完善一段文档、补充翻译、改善阅读体验，都是有用的贡献。Issue 和 PR 可使用中文或 English。请尊重彼此，围绕可复现的问题和具体方案讨论。

## 开始之前

- **报告问题**：说明预期和实际行为、复现步骤、文件格式、浏览器及部署方式。必要时附截图和脱敏日志；请勿上传密码、Cookie、真实账号库或未获授权的小说文件。
- **提出功能**：描述使用场景和希望改善的结果。涉及账号、数据结构、索引范围或阅读流程的大改动，建议先开 Issue 对齐范围。
- **认领工作**：在现有 Issue 留言，或直接提交一个范围清晰的小 PR。欢迎文档、翻译和可访问性方面的首次贡献。

## 本地开发

先按[快速开始](README.md#快速开始)准备系统 Recoll 扩展与自己的测试文库。使用能导入系统扩展的 Python 创建环境：

```bash
python3 -m venv --system-site-packages .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -c "from recoll import recoll, rclextract, rclconfig"
```

使用独立的开发数据库，不要复用正在运行的个人文库账号库：

```bash
export RECOLL_WEBUI_DB_PATH="$HOME/.local/share/novels-db-dev/app.sqlite3"
python manage.py init --username admin
python webui-standalone.py -c /path/to/test-recoll-config
```

初始化会交互式要求输入密码，首次登录需要改密。Node.js 用于 JavaScript 测试和重新构建前端依赖；正常运行应用不需要 Node.js。Bottle 与阅读器运行时已随仓库提供。

## 代码在哪里

| 位置 | 职责 |
| --- | --- |
| `webui.py` | Recoll 搜索、预览下载、阅读内容及缓存 |
| `accounts.py` / `account_web.py` | SQLite、认证、账号管理与个人设置 |
| `webui_data.py` / `shares.py` | 书架、历史、进度、推荐与公开分享 |
| `views/` / `static/` | Bottle 模板与界面资源 |
| `static/reader/` | 阅读器、格式适配与账号同步 |
| `tests/` | Python 集成与浏览器测试、Node.js 单元测试 |
| `manage.py` / `examples/` | 初始化、备份恢复、清理与服务示例 |
| `vendor-build/` | 随附前端依赖的构建入口 |

保持改动与问题相称，优先复用已有实现。不要修改第三方压缩产物来代替源代码修改；若更新 PDF.js，按其[构建说明](vendor-build/pdfjs/README.md)操作并保留许可信息。产品名称为 **Novels.db（ND）**；`RECOLL_WEBUI_*`、脚本名称和存储标识是已有部署接口，修改时需考虑兼容性。

## 验证改动

按影响范围选择检查，并在 PR 中写明实际执行的命令和结果。例如：

```bash
# 账号与数据层
python -m pytest -q tests/test_accounts.py tests/test_account_web.py

# 使用真实临时 Recoll 索引的集成测试
python -m pytest -q tests/test_webui_integration.py

# JavaScript 逻辑
node --test tests/*.test.mjs

# 全部 Python 测试（含可选的浏览器检查）
python -m pytest -q tests
```

浏览器测试需要 Playwright 和 Chromium，可以指定现有浏览器：

```bash
export RECOLL_TEST_CHROMIUM=/absolute/path/to/chromium
python -m pytest -q tests/test_app_experience_browser.py
```

浏览器不可用时相关测试会跳过；请如实写明跳过原因。真实 CHM 样本检查需要 `RECOLL_TEST_CHM_MANIFEST` 指向已有解包缓存的 `manifest.json`，完整 CHM 检查还需 `7z`。集成测试会创建临时索引和 SQLite 数据库，不连接正在运行的服务。

界面改动请检查桌面和手机宽度、键盘操作及子路径挂载，并附实际截图。文档改动检查本地链接与命令；低风险的文案或样式调整无需搭建额外测试框架。

## 提交 PR

1. Fork 仓库并为具体问题创建分支。
2. 提交范围清晰的修改，必要时同步文档和行为测试。
3. 说明解决了什么问题、用户能看到的变化、验证结果，并关联对应 Issue。
4. 若有未验证的环境或迁移要求，写明实际限制；根据评审意见继续完善。

请保留上游署名和随附依赖的许可信息。来源与许可现状见[说明](docs/third-party.md)。

## English participation guide

**Pull requests are welcome.** Issues and reviews can be in English or Chinese. For a bug, include expected/actual behavior, reproduction steps, document format, browser and deployment details. Use a small original or legally shareable sample and redact credentials and personal data.

Fork the repository and work on a focused branch. Use the setup commands above with a system Python that provides Recoll, a virtual environment created with `--system-site-packages`, and a separate development database and library. Install `requirements-dev.txt`; initialize an account before starting the server. Your first login requires a password change.

Run the relevant Python and/or Node.js commands above. Integration tests build disposable Recoll indexes and account databases. Browser checks need Playwright and Chromium; set `RECOLL_TEST_CHROMIUM` to its absolute path. Report missing prerequisites and skipped checks. For UI changes, include real desktop/mobile screenshots and check keyboard access and a mounted URL prefix.

Describe the problem, the resulting behavior and the commands/results in your PR. Open an issue before a large architectural or data migration change. Keep patches focused, update affected documentation, and preserve upstream attribution and dependency notices. Documentation, translation and accessibility improvements are good first contributions.
