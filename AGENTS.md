# AGENTS.md

给在本仓库工作的 AI 代理（以及未来的自己）看的说明。动手前先读完本文件和 `docs/design.md`。

## 项目是什么
本地画师作品图库：按 **画师 / 来源（平台+作品ID）/ tag** 管理图片。
完整设计见 [docs/design.md](docs/design.md)；本文件只写"怎么在这个仓库里干活"。

## 目录结构
| 路径 | 内容 | 规则 |
|---|---|---|
| `src/artist_gallery/` | Python 包（后端 + CLI） | 可改 |
| `src/artist_gallery/schema.sql` | 数据库结构 | 改动必须同时加迁移，见下文 |
| `tests/` | pytest 测试 | 可改；新功能要带测试 |
| `frontend/` | Vue 前端（M1 起才有） | 可改 |
| `docs/design.md` | 设计文档，唯一的需求来源 | 改需求前先和红豆确认 |
| `docs/decisions/` | 设计决策记录（ADR） | 只追加，不改历史条目 |
| `CHANGELOG.md` | 变更记录 | 每个功能性 commit 都要更新 |
| `AGENTS.md` | 本文件 | 改之前先说明理由 |

## 硬性规则
1. **绝不把用户数据提交进仓库**：图片、`*.db`、cookies、token、`gallery-dl.conf`。`.gitignore` 已排除，不要用 `git add -f` 绕过。测试用图在测试里用 Pillow 现场生成。
2. **绝不删除用户的图片文件**。移动文件一律"复制 → 校验 sha256 → 删除源文件"，任何一步失败就保留源文件并报错。
3. **数据库里的路径一律相对于图库根目录**，用 `/` 作分隔符（Windows 和 Android 通用）。不出现盘符和绝对路径。
4. **改表结构 = 加迁移**：在 `db.py` 的 `MIGRATIONS` 末尾追加一条，`PRAGMA user_version` 递增。不改已有的迁移。
5. **手动录入是完整功能，下载器是可选功能**。任何功能都不能依赖 Pixiv/X 的接口可用。
6. **Termux 兼容**：新增依赖前确认它在 Android（Termux, aarch64）上能装。需要编译 C/Rust 扩展的依赖要在 PR/commit 说明里注明。

## 开发环境
- Python 3.12；红豆的 Windows 机器上默认 shell 是 **PowerShell 5.1**：不支持 `&&`，用 `;` 或分多条命令。
- 安装（可编辑模式 + 开发依赖）：
  ```
  python -m venv .venv
  .venv\Scripts\python -m pip install -e ".[dev]"
  ```
- 运行测试：`.venv\Scripts\python -m pytest`
- CLI：`.venv\Scripts\artist-gallery --help`

## 代码风格
- 格式化与检查：`ruff format` + `ruff check`（配置在 `pyproject.toml`）。
- 类型标注：公共函数必须有。
- 注释、文档、commit 说明用中文；标识符用英文。
- SQL 用参数化查询，不拼字符串。

## Git 约定
- 分支：直接在 `main` 上提交（单人项目）；大改动可开 `feat/xxx` 分支。
- commit 前缀：`feat:` 新功能 / `fix:` 修复 / `docs:` 文档 / `refactor:` 重构 / `test:` 测试 / `chore:` 杂项。
- 一个 commit 只做一件事；提交前跑一遍测试。
- AI 代理完成改动后：commit 并 push，然后在回复里列出 commit 哈希和改动摘要。

## 不确定时
需求不清楚、设计文档没写到、或要做破坏性操作（批量移动、删记录、改 schema）时，先问红豆，不要自行补全。
