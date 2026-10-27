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
| `frontend/` | Vue 3 + Vite 前端源码 | 可改；**改完必须 `npm run build` 并把 `src/artist_gallery/server/static/` 的变化一起提交**（见下文"前端开发"） |
| `src/artist_gallery/server/static/` | 前端构建产物 | **只由 `npm run build` 生成，不手改**；提交进仓库，CI 会检查它和源码是否一致 |
| `docs/design.md` | 设计文档，唯一的需求来源 | 改需求前先和红豆确认 |
| `docs/frontend-style.md` | 前端风格与交互约定 | 做 `frontend/` 前先读；改风格先和红豆确认 |
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
10. **确认与撤销**（ADR 0007）：碰到图库之外、无法撤回的操作（删除源文件、永久删除）必须用户显式确认；图库内可撤销的操作不弹确认，但必须写 op_log 并能撤销。新增"不弹确认"的操作前，对应的撤销必须已经实现并有测试；撤销没落地的操作按大范围档处理（清单确认）。撤销失败时保留现状并报错，不覆盖、不删文件；`delete_source` 等不可逆记录不进撤销栈。

## 文件编码
- 所有文本文件用 **UTF-8、不带 BOM、换行用 LF**（`.gitattributes` 已统一换行）。
- **在 Windows PowerShell 5.1 里不要用 `Set-Content -Encoding utf8` / `Add-Content -Encoding utf8` / `Out-File` 写源码**：它们会悄悄在文件开头加 BOM。带 BOM 的 `.py` 在 Linux/Termux 上会直接 `SyntaxError: invalid non-printable character U+FEFF`，而 Windows 上完全看不出来。要写文件时用编辑工具，或 `[IO.File]::WriteAllText(path, text, (New-Object Text.UTF8Encoding($false)))`。
- CI 有 `hygiene` 任务检查这一条。

## 开发环境
- Python 3.12；红豆的 Windows 机器上默认 shell 是 **PowerShell 5.1**：不支持 `&&`，用 `;` 或分多条命令。
- 安装（可编辑模式 + 开发依赖）：
  ```
  python -m venv .venv
  .venv\Scripts\python -m pip install -e ".[dev]"
  ```
- 运行测试：`.venv\Scripts\python -m pytest`
- CLI：`.venv\Scripts\artist-gallery --help`
- 启动网页服务：`.venv\Scripts\artist-gallery serve <图库目录>`，浏览器打开 http://localhost:8765
- 测试依赖 `httpx2`（Starlette 的 TestClient 需要），装 `.[dev]` 时已包含。
- 数据库**不开 WAL**（ADR 0006）：图库靠复制文件夹同步，不要自行加 `PRAGMA journal_mode=WAL`。
- server 的请求处理器写成普通 `def`（在线程池里跑），每个请求用 `db.connect()` 自己开关连接，不要跨线程共用连接。

### 前端开发（`frontend/`）
需要 Node ≥ 22.12（或 20.19+），只有改前端的人才需要装；只用程序的人不需要（构建产物已提交）。
```
cd frontend
npm ci                 # 按 package-lock.json 装依赖
npm test               # 单元测试（vitest）
npm run build          # 构建，产物直接写进 ../src/artist_gallery/server/static/
npm run dev            # 开发服务器 http://localhost:5173，接口代理到本机已启动的 artist-gallery serve（8765）
```
- **改了 `frontend/` 就要重新 `npm run build`，并提交 `static/` 的变化。** 忘了的话 CI 的 `frontend` 任务会报错。
- 前端运行时依赖要尽量少（现在只有 vue、pinia、@lucide/vue）；加新依赖前先想"手写能不能解决"（见 `docs/frontend-style.md` 第 8 节）。**没有用 vue-router**：只有"收件箱 / 文件夹"两种视图，用 `lib/location.js` + `lib/history.js`（几十行、有测试）把视图同步到地址栏就够了；到 M2 页面变多再重新评估。
- 前端的"在途请求"要防竞态：用户快速切换视图时，先发出、后返回的旧请求不能覆盖新结果（见 `stores/inbox.js` 的 `epoch`）。新增会异步取数据的 store 时照此处理。
- 组件文件名用大驼峰（`ThumbCell.vue`）。CI 跑在区分大小写的 Linux 上，`import` 路径的大小写必须和文件名逐字一致，否则 Windows 上正常、CI 里报错。
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
