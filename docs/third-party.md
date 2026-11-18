# 来源与许可 / Origins and licensing

## 项目来源

**Novels.db（ND）主要基于 [medoc92/recollwebui](https://framagit.org/medoc92/recollwebui)**，该上游更早源自 [koniu/recoll-webui](https://github.com/koniu/recoll-webui)。[Novels.db](https://github.com/uiharuayako/Novels.db) 在上游搜索界面的基础上增加了账号、书架、阅读与分享功能。

[Recoll](https://www.recoll.org/) 提供全文索引、查询和文档提取。应用的产品名称不改变 Recoll 引擎、配置及现有部署接口的名称。

## 随附资源

| 资源 | 来源及许可信息 |
| --- | --- |
| Bottle | 仓库内的 [`bottle.py`](../bottle.py) 保留其 MIT 许可声明。 |
| Koodo Reader / Kookit | [上游仓库](https://github.com/koodo-reader/koodo-reader)；构建入口位于 [`vendor-build/reader-bundle/`](../vendor-build/reader-bundle/)，应用使用 [`kookit.bundle.js`](../static/reader/kookit.bundle.js) 运行时。 |
| Mozilla PDF.js | 随附版本与构建方法见 [PDF.js 说明](../vendor-build/pdfjs/README.md)；[Apache-2.0 许可](../static/reader/vendor/pdfjs/6.5.438/LICENSE)以及字体、CMap、WASM 等目录内的独立许可一并保留。 |
| 其他界面资源 | 原有 JavaScript、CSS 和图片中的作者及许可声明继续适用。 |

阅读体验参考 Readest、Koodo Reader 等开源阅读器，详见 [UI/UX 调研记录](reader-ui-research.md)。Novels.db 标志为本项目绘制的 SVG；展示截图使用原创演示小说，由实际应用生成。

## 项目许可现状

当前仓库未包含可确认覆盖整个项目的根目录 `LICENSE`。各上游和随附依赖遵循各自许可；在以完整项目进行再分发前，需要核实上游授权与新增代码的许可安排。

## English

Novels.db is based primarily on **medoc92/recollwebui**, itself originating from **koniu/recoll-webui**. Recoll supplies indexing, search and extraction. The linked table identifies bundled runtimes and retained notices; PDF.js also includes separate notices for fonts, CMaps and WASM components. The current repository has no verified root license covering the complete project. Upstream and bundled components retain their respective terms; project-wide redistribution requires resolving upstream and added-code licensing. The ND SVG is drawn for this project, and the screenshots show the actual application with original demo stories.
