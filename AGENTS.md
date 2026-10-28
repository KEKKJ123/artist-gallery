# AGENTS.md

给在本仓库工作的 AI 代理（以及未来的自己）看的说明。动手前先读完本文件和 `docs/design.md`。

## 项目是什么
本地画师作品图库：**图片直接关联内容 tag、画师与多平台来源；文件版本与图片身份分开，不要求分组**。
完整需求见 [docs/design.md](docs/design.md)，模型决定见 [ADR 0008](docs/decisions/0008-以图片为中心的整理与来源模型.md)，开发期旧库例外见 [ADR 0009](docs/decisions/0009-开发期旧库不迁移.md)，旧模型专用筛查的移除见 [ADR 0011](docs/decisions/0011-移除旧模型专用筛查.md)，最新简化决定见 [ADR 0010](docs/decisions/0010-图片直接属性与原名增量导入.md)，代码转向与验收见 [docs/transition.md](docs/transition.md)。本文件只写"怎么在这个仓库里干活"。

## 当前路线切换（2026-10-28）

- 当前设计 v0.10：T1 新模型基础与 T2 来源核查／归档／撤销已实现；当前格式版本 6（基线 5 追加升级），草稿独立持久化、文件中断显式恢复。T3 直接 tag／画师编辑与检索尚未实现，不能写成已交付。
- T0 已合入；红豆确认旧开发库有异地备份，由红豆手动处理。T1 面向新建库，**不做旧数据迁移、映射、旧目录搬迁或旧格式兼容**；AI 不清空或重建用户库。
- `open_library` 先只读识别格式，再按新版本迁移／同步；只维护当前格式标识与版本校验，不维护改路线前旧库专门识别或 fixture。预演 readonly，不升级／同步。
- `feat/image-details-captions` 暂停，不合并、不改写、不删除；固定标题和文件大小可在新模型中按模块复用，不整批引入旧来源与资料包方案。
- 本次 schema 已与红豆评审，红豆确认 sky 不并行修改；后续改 schema／格式标识／版本代码仍先协调。首要原则是减少用户无用／繁琐操作，即使增加代码工作量。

## 目录结构
| 路径 | 内容 | 规则 |
|---|---|---|
| `src/artist_gallery/` | Python 包入口（CLI） | 可改 |
| `src/artist_gallery/core/` | 纯业务逻辑：数据库、导入、识别、文件操作、tag | 可改；不得依赖 Web 框架 |
| `src/artist_gallery/core/schema.sql` | 数据库结构 | T1 可按 ADR 0009 建立新格式基线；之后改结构追加迁移，见下文 |
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
4. **打开已有图库用 `db.open_library()`**，不要自己 `connect` + `migrate`。当前它负责迁移和同步 `core/platforms.py` 的内置规则，改规则无需迁移；服务启动校验后，各请求用轻量 `db.connect()` 自行开关连接。平台规则包的格式与更新方式按 T4 另审，不能提前绕过此入口。
5. **格式与版本边界**：不实现改路线前旧库升级或专门筛查，旧 fixture 已移除（ADR 0011）；当前格式未知／过新／损坏库不清空重建。新格式结构变化追加 MIGRATIONS 与对应 REQUIRED_SCHEMAS，不改写已发布版本要求；先检查输入版本，再迁移并在提交前检查目标版本。改 schema／格式标识／版本代码前先与 sky 协调。
6. **手动录入是完整功能，下载器是可选功能**。任何功能都不能依赖 Pixiv/X 的接口可用。
7. **路径要能跨平台**：文件名重名判断一律不区分大小写；新生成的文件名不得含 Windows 非法字符、不超过 255 字节（见 `importer._safe_stem`）。
8. **Android 兼容（APK + Termux）**：新增**运行时**依赖必须是纯 Python，或在 Chaquopy 包仓库（https://chaquo.com/pypi-13.1/）中有现成包。不满足的依赖不准加，先和红豆讨论。因此 Web 层用 Starlette，**不用 FastAPI / pydantic v2**（见 ADR 0003）。开发依赖（pytest、ruff）不受此限。
9. **分层**：`core/` 不得 import `server/` 或任何 Web 框架；所有业务逻辑放 `core/`，`server/` 只做参数解析和调用。
10. **确认与撤销**（ADR 0007、0008）：小范围、可撤销且撤销已实现有测试的操作可免额外弹框；大范围操作先清单确认；不可逆操作必须显式确认。均须按范围写 op_log；撤销未交付前按大范围档处理。多选追加来源必须明确确认“全部链接 × 每张所选图”，不能用可撤销作理由取消范围确认。撤销失败保留现状，不覆盖、不删文件；不可逆记录不进撤销栈且不能被跨过。
11. **直接属性与身份分开**：图片直接关联 tag、画师和来源，不创建作品组或隐式单图组。pn 是对应来源的可空位置，不是总页数／图片 ID。收件箱／已归档明确记录，不从路径或来源猜；批量属性只影响所选图片。
12. **识别不等于确认或归档**：文件名／链接预填待核查信息，不猜作者。正常归档至少一条人工确认的具体发布，页码／时间可未知；无来源可显式强制归档，不伪造确认或越过安全。hash 增量保持旧分类、原名和状态，源目录减少不删图库；副本缺失／损坏报错不覆盖，重复输入不进删源清单。
13. **不迁移不等于自动清空**：开发期旧库由红豆手动处理；AI 不删用户文件，不写旧库转换、映射或搬迁工具。旧库专门识别已移除，保留通用格式校验；`init` 不覆盖已有库或冲突文件。新格式之后的升级及正常文件操作仍须保护数据、备份和恢复；代码回滚不等于库降级，暂停 PR 不得擅自丢弃。

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
- 前端运行时依赖要尽量少（现在只有 vue、pinia、@lucide/vue）；加新依赖前先想"手写能不能解决"（见 `docs/frontend-style.md`）。当前未用 vue-router，`lib/location.js` + `lib/history.js` 负责旧视图地址栏同步；新检查页／关系浏览变复杂时先评估，不默认新增路由依赖。
- 前端的"在途请求"要防竞态：先发出、后返回的旧请求不能覆盖当前图片／视图（见 `composables/use-image-collection.js` 与 `stores/library.js`）。composables 不反向依赖 store／组件／API，取数由回调传入；新增异步模块须有独立及集成竞态测试。
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
- 复杂大改必须在同一个 PR 内拆成多个职责清晰的 commit，各带测试；main 继续 Squash，重点是 PR 内有拆分记录。一个 commit 只做一件事，提交前跑测试和 ruff，不以“整批配套”代替拆分。
- 动 `MIGRATIONS` 前确认没有别的开着的 PR 也在加迁移。
- **AI 代理**：开工前 `git switch main; git pull --ff-only`，再开分支。完成后推分支，在回复里给出分支名、commit 哈希、改动摘要和开 PR 的链接 `https://github.com/KEKKJ123/artist-gallery/compare/main...<分支名>?expand=1`。不自行合并，由红豆合并。

## 不确定时
需求不清楚、设计文档没写到、或要做破坏性操作（批量移动、删记录、改 schema）时，先问红豆，不要自行补全。
