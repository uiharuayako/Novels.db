# Novels.db 文档 / Documentation

[简体中文首页](../README.md) · [English overview](../README.en.md) · [贡献指南 / Contributing](../CONTRIBUTING.md)

## 安装与使用 / Setup and use

| 文档 | 适合什么时候阅读 |
| --- | --- |
| [完整运维与功能指南](operations.rst)（中文） | 安装、环境变量、索引、反向代理、格式能力与运行限制 |
| [systemd 部署](../README-systemd.rst)（English） | 以服务账号长期运行，以及自动清理 |
| [账号与阅读数据](accounts-and-history.md)（中文） | 注册、权限、个人记录、备份和恢复 |
| [来源与许可 / Origins and licensing](third-party.md) | 了解 recoll-webui 上游及随附资源 |

English setup and maintenance commands are available in [README.en.md](../README.en.md). The detailed operations and account guides are currently in Chinese.

## 开发 / Development

从[贡献指南](../CONTRIBUTING.md)了解本地环境、代码目录和测试方式。[PDF.js 构建说明](../vendor-build/pdfjs/README.md)用于更新仓库自带的 PDF 运行时。

以下资料记录实现思路，阅读时请与当前代码核对；通用部署以运维指南为准。

- [阅读器 UI/UX 调研](reader-ui-research.md)：交互参考与验证范围。
- [多账号与历史功能设计](multi-account-and-history-plan.md)：原始设计记录。
