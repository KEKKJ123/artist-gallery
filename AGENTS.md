# AGENTS.md

给在本仓库工作的 AI 代理（以及未来的自己）看的说明。动手前先读完本文件和 `docs/design.md`。

## 项目是什么
本地画师作品图库：按 **画师 / 来源（平台+作品ID）/ tag** 管理图片。
完整设计见 [docs/design.md](docs/design.md)；本文件只写"怎么在这个仓库里干活"。

## 目录结构
| 路径 | 内容 | 规则 |
|---|---|---|
| `src/artist_gallery/` | Python 包入口（CLI） | 可改 |
| `src/artist_gallery/core/` | 纯业务逻辑：数据库、导入、识别、文件操作、tag | 可改；不得依赖 Web 框架 |
| `src/artist_gallery/core/schema.sql` | 数据库结构 | 改动必须同时加迁移，见下文 |
| `src/artist_gallery/server/` | Starlette API + 静态文件托管（M1 起才有） | 可改；只做参数解析和调用 core |
| `android/` 或 Briefcase 配置 | APK 打包（M4 起才有） | 可改 |
| `tests/` | pytest 测试 | 可改；新功能要带测试 |
| `frontend/` | Vue 前端（M1 起才有） | 可改 |
| `docs/design.md` | 设计文档，唯一的需求来源 | 改需求前先和红豆确认 |
| `docs/decisions/` | 设计决策记录（ADR） | 只追加，不改历史条目 |
| `CHANGELOG.md` | 变更记录 | 每个功能性 commit 都要更新 |
| `AGENTS.md` | 本文件 | 改之前先说明理由 |

## 硬性规则
1. **绝不把用户数据提交进仓库**：图片、`*.db`、cookies、token、`gallery-dl.conf`。`.gitignore` 已排除，不要用 `git add -f` 绕过。测试用图在测试里用 Pillow 现场生成。
2. **绝不擅自删除用户的图片文件**。导入只复制；删除源文件只能在用户明确确认后通过 `delete_sources()` 进行（ADR 0005）。图库内部移动一律"复制 → 校验 sha256 → 删除旧位置"，任何一步失败就保留原文件并报错。
3. **数据库里的路径一律相对于图库根目录**，用 `/` 作分隔符（Windows 和 Android 通用）。不出现盘符和绝对路径。
4. **打开图库一律用 `db.open_library()`**（负责迁移和同步内置平台），不要自己 `connect` + `migrate`。内置平台的识别规则在 `core/platforms.py` 里改，**不需要**写迁移。
5. **改表结构 = 加迁移**：在 `core/db.py` 的 `MIGRATIONS` 末尾追加一条，`PRAGMA user_version` 递增。不改已有的迁移。
6. **手动录入是完整功能，下载器是可选功能**。任何功能都不能依赖 Pixiv/X 的接口可用。
7. **路径要能跨平台**：文件名重名判断一律不区分大小写；新生成的文件名不得含 Windows 非法字符、不超过 255 字节（见 `importer._safe_stem`）。
8. **Android 兼容（APK + Termux）**：新增**运行时**依赖必须是纯 Python，或在 Chaquopy 包仓库（https://chaquo.com/pypi-13.1/）中有现成包。不满足的依赖不准加，先和红豆讨论。因此 Web 层用 Starlette，**不用 FastAPI / pydantic v2**（见 ADR 0003）。开发依赖（pytest、ruff）不受此限。
9. **分层**：`core/` 不得 import `server/` 或任何 Web 框架；所有业务逻辑放 `core/`，`server/` 只做参数解析和调用。

## 开发环境
- Python 3.12；红豆的 Windows 机器上默认 shell 是 **PowerShell 5.1**：不支持 `&&`，用 `;` 或分多条命令。
- 安装（可编辑模式 + 开发依赖）：
  ```
  python -m venv .venv
  .venv\Scripts\python -m pip install -e ".[dev]"
  ```
- 运行测试：`.venv\Scripts\python -m pytest`
- CLI：`.venv\Scripts\artist-gallery --help`
- Termux 上安装：Pillow 用 `pkg install python-pillow`，venv 加 `--system-site-packages`；只装 `pip install -e . pytest`，**不要装 `.[dev]`**（ruff 是 Rust 写的，会在手机上现场编译）。

## 代码风格
- 格式化与检查：`ruff format` + `ruff check`（配置在 `pyproject.toml`）。
- 类型标注：公共函数必须有。
- 注释、文档、commit 说明用中文；标识符用英文。
- SQL 用参数化查询，不拼字符串。

## Git 约定
完整流程见 [CONTRIBUTING.md](CONTRIBUTING.md)。要点：
- **不直接 push `main`**。从最新 main 开分支（`feat/…`、`fix/…` 等），推分支后开 Pull Request，CI 绿了再由别人合并（Squash and merge）。
- commit 前缀：`feat:` 新功能 / `fix:` 修复 / `docs:` 文档 / `refactor:` 重构 / `test:` 测试 / `chore:` 杂项。
- 一个 commit 只做一件事；提交前跑一遍测试和 ruff。
- 动 `MIGRATIONS` 前确认没有别的开着的 PR 也在加迁移。
- **AI 代理**：开工前 `git switch main; git pull --ff-only`，再开分支。完成后推分支，在回复里给出分支名、commit 哈希、改动摘要和开 PR 的链接 `https://github.com/KEKKJ123/artist-gallery/compare/main...<分支名>?expand=1`。不自行合并，由红豆合并。

## 不确定时
需求不清楚、设计文档没写到、或要做破坏性操作（批量移动、删记录、改 schema）时，先问红豆，不要自行补全。
