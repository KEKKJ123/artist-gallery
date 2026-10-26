# CHANGELOG

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [Unreleased]
### 协作
- 新增 `CONTRIBUTING.md`：分支 + Pull Request + Squash and merge，`main` 不直接推送。
- 新增 GitHub Actions CI：Windows / Ubuntu × Python 3.12 / 3.14，跑 ruff 和 pytest。
- 新增 PR 模板；AGENTS.md 的 Git 约定改为走 PR。

### 修复（代码审查 2026-10-26）
- 内置平台规则移到 `core/platforms.py`，打开图库时同步进数据库：旧图库自动用上新规则，此前已建的库不会再卡在旧正则上。迁移 v3 → v4 加 `platform.builtin` 列。
- 新增 `db.open_library()` 统一"连接 → 迁移 → 同步内置平台"。
- 迁移改为显式事务：失败整体回滚（之前 `executescript` 会先提交，可能留下改了一半的库）。
- 重名判断不区分大小写（Windows / Android 共享存储不区分）。
- 收件箱文件名清理：去掉 Windows 非法字符、保留名，截断到 150 字节以内（Android 上限 255 字节）。
- 从图库的上级目录导入时，不会把图库自己的文件再扫一遍。
- 内置正则改用 ASCII 模式，全角数字不会被当成 ID。
- 自定义平台的无效正则只记日志、不让导入崩溃。
- Ctrl+C 中断时清理已复制的副本。
- 迁移测试改为用真实的 v1 schema 建库。
- Pixiv 单页规则 `标题_ID`：标题含 QQ / 头像 / 微信 / 群 / 账号 / avatar / uid 等字样时降为中置信，防止把 QQ 号当成作品 ID。

### 变更（按真实样本校准识别）
- 用 188 个真实文件名样本校准：自动归档从 22 个提高到 62 个；中置信误报从 68 个（含大量哈希/QQ 导出名被误认）降到 1 个真实有效的。
- 新增 Pixiv 单页 `标题_ID` 高置信规则；数字须"孤立"（两侧非字母数字）；Pixiv ID 收紧为 8 位或 1 开头的 9 位，X ID 为 17–20 位。
- 内置 Zerochan 平台（迁移 v2 → v3）。
- X 网页另存的 15 位 media key 识别为"可能来自 X、ID 待补"。
- 视频与图片同样按文件名分类导入（不读宽高、不做缩略图和画质处理）。
- 扫描文件夹时跳过隐藏文件夹（如 `.thumbnails`）。
- 设计文档 v0.6：新增第 10 节未来构想（画质优选）。

### 新增（M0 导入）
- `artist-gallery import`：扫描文件/文件夹 → sha256 去重 → 文件名识别来源 → 复制校验后移入图库（`--copy` 保留源文件，`-n` 预演）。
- 识别规则（`core/recognize.py`）：本程序格式、Pixiv `_p` 格式、gallery-dl X 格式自动归档；孤立数字作为中置信建议进收件箱。
- `artist-gallery status`：图库统计。
- 安全文件复制 `core/fileops.py`：写入 `.part` 临时文件，校验 hash 后再落位。
- 数据库迁移 v1 → v2：`image` 新增 `orig_name`、`source_hint`；内置文件名正则加数字边界。
- 测试增至 37 个（识别规则、导入、去重、重名、损坏文件、迁移）。

### 新增（基础架构）
- 仓库基础架构：`AGENTS.md`、`pyproject.toml`、`CHANGELOG.md`、`docs/decisions/`。
- Python 包骨架 `artist_gallery`：数据库结构 v1（`schema.sql`）、迁移机制（`PRAGMA user_version`）、CLI `init` 命令。
- 内置平台 Pixiv、X 的链接 / 文件名解析正则。
- pytest 测试：建库、版本号、内置平台正则。
- ADR 0003：Android 改为 APK 发布（Briefcase + Chaquopy，CI 编译），Web 框架改用 Starlette；设计文档升到 v0.3。
- 测试 `test_layering.py`：检查 `core/` 不 import Web 框架。

- ADR 0004：Android 默认图库放 App 私有目录、零存储权限，Photo Picker/SAF 导入，共享文件夹为可选高级项；设计文档升到 v0.4。

### 变更
- 数据库代码移到 `artist_gallery.core`（`core/db.py`、`core/schema.sql`）。
- AGENTS.md 规则 6 改为"运行时依赖须为纯 Python 或 Chaquopy 有现成包"；新增规则 7（分层）；补充 Termux 安装注意事项。

## 2026-10-26
### 新增
- 设计文档 v0.2。
