# CHANGELOG

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [Unreleased]
### 新增
- 仓库基础架构：`AGENTS.md`、`pyproject.toml`、`CHANGELOG.md`、`docs/decisions/`。
- Python 包骨架 `artist_gallery`：数据库结构 v1（`schema.sql`）、迁移机制（`PRAGMA user_version`）、CLI `init` 命令。
- 内置平台 Pixiv、X 的链接 / 文件名解析正则。
- pytest 测试：建库、版本号、内置平台正则。
- ADR 0003：Android 改为 APK 发布（Briefcase + Chaquopy，CI 编译），Web 框架改用 Starlette；设计文档升到 v0.3。
- 测试 `test_layering.py`：检查 `core/` 不 import Web 框架。

### 变更
- 数据库代码移到 `artist_gallery.core`（`core/db.py`、`core/schema.sql`）。
- AGENTS.md 规则 6 改为"运行时依赖须为纯 Python 或 Chaquopy 有现成包"；新增规则 7（分层）；补充 Termux 安装注意事项。

## 2026-10-26
### 新增
- 设计文档 v0.2。
