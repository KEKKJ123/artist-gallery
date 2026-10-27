# 画师图库 设计文档 v0.7（2026-10-27）

> v0.7 变更：撤销最近一次归档提前到 M1c（归档不弹确认、靠撤销兜底；不可撤销的操作仍须确认）；界面风格见 `docs/frontend-style.md`。同日整理：第 3 节标注为概念模型并列出与实际结构的差异；第 4 节 CLI 补全 `init` / `serve`；2.1 节确认档位明确为三档。
> v0.6 变更：按 188 个真实样本校准识别规则（Pixiv 单页 `标题_ID`、Zerochan、X media key、排除哈希/时间戳）；视频跳过并报告；新增第 10 节未来构想（画质优选）。视频与图片同样分类导入，不做缩略图和画质处理。
> v0.5 变更：归档文件名改为 `{platform}_{post_id}_p{page}`；第 4 节识别规则按实际实现更新（M0 导入已完成）。
> v0.4 变更：Android 默认图库改放 App 私有目录、零存储权限，Photo Picker/SAF 导入；共享文件夹为可选高级项。见 ADR 0004。
> v0.3 变更：Web 框架由 FastAPI 改为 Starlette；Android 端改为 APK 发布（Briefcase + Chaquopy，CI 编译），Termux 保留为开发者路径。见 ADR 0003。
> v0.2 变更：新增 2.1 文件管理策略（默认移动+重命名、程序内移动、批量操作、撤销）；数据模型新增 op_log 表。

## 1. 目标与范围
- 本地管理画师作品图片；核心维度：**画师 / 来源（平台+作品ID）/ tag**。
- 起点：明日方舟·红豆；扩展到任意角色、事物 → 全部靠 tag 命名空间实现，不为"角色"单独建模。
- 规模：现有 ~200 张，设计目标 1 万张以内无压力（SQLite 足够）。
- 平台：Pixiv、X 一等支持；小众平台通过"平台配置表"自定义，不改代码。
- 设备：Windows 主力；Android 完整可用（APK 安装即用，Termux 作为开发者路径）+ 局域网访问。

## 2. 总体架构
```
图库根目录/                 ← 整个文件夹可直接复制/同步到手机
├─ library.db              ← SQLite，所有路径存"相对于根目录"
├─ images/
│   ├─ pixiv/pixiv_123456789_p0.png
│   ├─ x/x_1849000000000000000_p1.jpg
│   ├─ <自定义平台>/...
│   └─ _inbox/原始文件名.jpg   ← 来源未知，待整理
└─ .cache/thumbs/          ← 缩略图，可随时重建，不必同步
```
- 程序：Python 3.12 + Starlette/uvicorn + SQLite + Pillow；下载器内置 gallery-dl（作为 Python 库调用）。
  - 依赖约束：运行时依赖必须是纯 Python，或在 Chaquopy 包仓库中有现成包（ADR 0003）。
- 代码分层：`core/`（纯逻辑）→ `server/`（Starlette API + 静态文件）→ `frontend/`（Vue 3 + Vite 构建的静态页面）。
- 运行方式：
  - PC：`artist-gallery serve <图库目录>`（等价于 `python -m artist_gallery serve <图库目录>`），浏览器打开 localhost。
  - Android（普通用户）：安装 APK。App 启动时在后台线程运行同一个 server，全屏 WebView 加载 localhost。APK 由 Briefcase 打包、GitHub Actions 编译。
  - Android（开发者）：Termux 里 `pip install` 同一个包，浏览器打开 localhost。
  - 手机在线：访问 PC 的局域网地址。
- Android 存储（ADR 0004）：
  - 默认图库放 App 私有目录 `Android/data/<包名>/files/`，**不申请任何存储权限**。
  - 导入图片用系统 Photo Picker（无 Play 服务时回退 SAF），只拿到用户选中的文件；导入/导出整个图库用 SAF 选文件夹。
  - 高级选项（默认关闭）：图库放共享文件夹，此时才申请存储权限（≤10：WRITE_EXTERNAL_STORAGE；≥11：所有文件访问）。
  - 只做侧载分发，不上 Google Play。
- 文件名自描述：来源确定后文件被重命名为 `{platform}_{post_id}_p{page}.{ext}`（平台名写进文件名本身，不依赖所在目录；重名时追加 `_2`、`_3`）。图片被移到任何目录都能从文件名重建来源。

### 2.1 文件管理策略（v0.2 新增）
- **导入**：复制进图库 + 按模板重命名，校验通过后入库。**源文件不自动删除**：导入完成后由用户确认是否删除（CLI 提示 / 界面复选框，默认不删），删除前再校验一次副本和源文件。见 ADR 0005。
- **存放模板可配置**：默认 `images/{platform}/{platform}_{post_id}_p{page}.{ext}`；可改成例如 `images/{character}/{artist}/{platform}_{post_id}_p{page}.{ext}`（文件名部分固定，只有目录可配置）。模板只决定"新文件放哪"，不强制已有文件。
- **程序内移动**：任意图片/作品可以被移到图库内的任意子文件夹（如 `images/精选/`），db 同步更新 `rel_path`。文件名中的来源部分保持不变，只换目录。
- **批量操作**（所有页面的多选都支持）：
  - 批量移动到文件夹 / 新建文件夹
  - 批量按模板重新整理（例：把模板改了以后，一键把全库重排）
  - 批量改 tag（加 / 删 / 替换）、批量改画师、批量合并 / 拆分作品
  - 每次批量操作都写操作日志（op_log），支持**撤销最近一次**，可连续撤销（倒序逐条，不跳着撤）。不可逆记录（如 `delete_source`）不进撤销栈；撤销前校验当前状态，不一致则保留现状并报错。
  - **撤销没实现的操作不得免确认**：按里程碑（M1c 归档、M1d 打 tag、M1e 其余）逐项交付撤销，交付前一律按"大范围"处理，先清单后确认。
  - 预览与确认分三档（ADR 0007，v0.7 起；"小范围免确认"只对撤销已交付的操作生效，见上一条）：
    - **小范围、可撤销**（收件箱归档、打 tag、合并作品等，作用于当前选中的少量图）：操作面板里**实时显示预览**（如"将重命名为 `pixiv_123_p0.png`"），`Enter` 即执行，**不弹确认框**，完成后提示条带"撤销"按钮。
    - **大范围、可撤销**（改模板后重排全库、批量移动整个文件夹等，一次动成百上千个文件）：**先显示完整"A → B"清单，确认后才执行**；同样可撤销。
    - **不可撤销**（删除源文件、永久删除）：任何情况下都必须显式确认（ADR 0005）。
- **外部改动**：如果在资源管理器里手动挪了文件，下次启动或手动"重新扫描"时按 sha256 找回，更新路径；找不到的标为"丢失"，不自动删除记录。
- **安全**：移动采用"先复制 → 校验 hash → 再删原文件"，中途出错不丢图。

## 3. 数据模型
> 下面是**概念模型**，用来讲清楚各表的关系，省略了约束和索引。**实际结构以 `src/artist_gallery/core/schema.sql` 加 `db.py` 的 `MIGRATIONS` 为准**（当前 v4）。
> 与概念模型相比，实际多出：`platform.builtin`（内置平台标记）、`image.missing`（重新扫描时找不到文件）、`image.orig_name`（导入时的原文件名）、`image.source_hint`（中置信的来源建议，JSON）。
> 内置平台（pixiv / x / zerochan）的识别规则写在 `core/platforms.py`，每次打开图库时同步进表，其 `file_regex` 列为空；只有自定义平台使用这一列。
```sql
CREATE TABLE platform (            -- 平台配置，小众平台在这里加
  id TEXT PRIMARY KEY,             -- 'pixiv' / 'x' / 'lofter' ...
  name TEXT,
  post_url  TEXT,                  -- 'https://www.pixiv.net/artworks/{post_id}'
  user_url  TEXT,                  -- 'https://www.pixiv.net/users/{uid}'
  url_regex TEXT,                  -- 从粘贴的链接里解析 post_id / handle
  file_regex TEXT                  -- 从文件名里解析 post_id / page（仅自定义平台使用）
);
CREATE TABLE artist  (id INTEGER PRIMARY KEY, name TEXT NOT NULL, note TEXT);
CREATE TABLE account (
  id INTEGER PRIMARY KEY, artist_id INT REFERENCES artist,
  platform TEXT REFERENCES platform, uid TEXT, handle TEXT,
  UNIQUE(platform, uid)            -- X 用数字 uid 做主键，handle 会变
);
CREATE TABLE work (id INTEGER PRIMARY KEY, artist_id INT REFERENCES artist,
                   title TEXT, posted_at TEXT, added_at TEXT);
CREATE TABLE source (
  id INTEGER PRIMARY KEY, work_id INT REFERENCES work,
  platform TEXT REFERENCES platform, post_id TEXT,
  UNIQUE(platform, post_id)        -- 同一作品可有多个来源（Pixiv+X 双发）
);
CREATE TABLE image (
  id INTEGER PRIMARY KEY, work_id INT REFERENCES work,  -- NULL = 收件箱
  rel_path TEXT UNIQUE, sha256 TEXT UNIQUE, page INT,
  width INT, height INT, phash TEXT, added_at TEXT
);
CREATE TABLE tag (id INTEGER PRIMARY KEY, ns TEXT DEFAULT '', name TEXT,
                  UNIQUE(ns, name));
CREATE TABLE tag_alias (alias TEXT PRIMARY KEY, tag_id INT REFERENCES tag);
CREATE TABLE work_tag  (work_id INT, tag_id INT, PRIMARY KEY(work_id, tag_id));
CREATE TABLE op_log (              -- 批量操作日志，用于撤销
  id INTEGER PRIMARY KEY, batch_id TEXT, at TEXT,
  kind TEXT,                       -- 'move' / 'tag_add' / 'tag_del' / 'merge' ...
  payload TEXT                     -- JSON：{image_id, from, to} 等
);
```
tag 命名空间约定：`character:红豆`、`series:明日方舟`、`meta:R-18` 等，不带前缀的就是普通 tag。
别名：`Vigna`、`ヴィグナ` 等写法统一归到 `character:红豆`（具体别名录入时再定）。

## 4. 导入与识别
文件名规则按顺序匹配，命中即停（实现：`core/recognize.py`）：
| # | 规则 | 示例 | 结果 |
|---|---|---|---|
| 1 | 本程序格式 `{platform}_{post_id}_p{page}`，platform 须已登记 | `pixiv_123456789_p0` | 高 → 自动归档 |
| 2 | platform 表的 `file_regex`：Pixiv `ID_pN`；Zerochan `名字.full.ID` / `名字.600.ID` | `标题_107517372_p1`、`Vigna.full.3017022` | 高 → 自动归档 |
| 3 | 内置：Pixiv 单页 `标题_ID`（ID 在末尾）；gallery-dl 的 X 格式 `{tweet_id}_{num}`（num 从 1 起，转为 p0 起） | `红豆_80742555`、`1849…_1` | 高 → 自动归档 |
| 4 | 孤立数字：17–20 位 → X；8 位或 1 开头的 9 位 → Pixiv（排除 20YYMMDD 日期） | `红豆 12345678` | 中 → 收件箱，附来源建议 |
| 4b | 15 位大小写混合的 media key（X 网页右键另存）→ 只提示"可能来自 X"，ID 待补 | `EO2cBcJWoAAJJWf` | 中 → 收件箱 |
| 5 | 其他：截图、相机、QQ/微信导出、哈希文件名、时间戳 | `Screenshot_…`、`Image_107017529707664`、`mmexport…` | 无 → 收件箱 |
- 单页规则 `标题_ID` 的防护：8–9 位数字可能是 QQ 号。标题含 `QQ`、`头像`、`微信`、`群`、`账号`、`avatar`、`uid` 等字样时降为中置信（收件箱+建议）。带 `_pN` 的原图格式不受影响。
- "孤立"= 两侧不是字母或数字，避免把十六进制哈希、`mmexport1738…` 里的片段误认成 ID。
- Pixiv ID 范围：8 位，或 1 开头的 9 位（截至 2026 年约 1.4 亿）。7 位及以下、10 位（多为时间戳）不认。Pixiv 进入 2 开头的 9 位后需放宽。
- X 推文 ID：17–20 位（2011 年后的 snowflake）。QQ 导出的 `Image_` + 13–15 位不是推文 ID。
- 依据：2026-10-26 用 188 个真实文件名样本校准（高置信 62、media key 1、其余为截图/相机/App 导出等确实无来源信息的文件、视频 2）。
- 视频（`.mp4` 等）与图片走同一套识别和归档，只是不读宽高；GIF 视作图片。不生成视频/GIF 专用缩略图，也不参与画质判断（第 10.1 节只针对静态图）。
- 隐藏文件夹（任何一级以 `.` 开头，如 `.thumbnails`）在扫描文件夹时跳过；直接指定的文件不受此限。
- 用 sha256 去重：库里已有或同批次重复的文件跳过，**源文件不动**。
- 目标重名时追加 `_2`、`_3`。损坏/非图片文件报错并保留源文件。
- 自定义平台：在 platform 表里写 `file_regex`（命名组 `post_id`、可选 `page`），就能参与识别。
- CLI（`artist-gallery --help` 查看全部）：
  - `init <图库>`：新建图库（已存在则报错，不覆盖）。
  - `import <图库> <文件或文件夹...> [--delete-source ask|yes|no] [-n/--dry-run] [--no-recursive] [-v]`：导入。
  - `status <图库>`：统计。
  - `serve <图库> [--host 127.0.0.1] [--port 8765]`：启动网页界面。默认只允许本机访问；`--host` 设为非本机地址即开放局域网（无登录保护，会提示）。

## 5. 手动整理（重点：批量、少点鼠标）
"收件箱"页面：
- 缩略图网格，Ctrl/Shift 多选 + 框选；按导入时间或相似度排序，同一作品的几页会挨在一起。
- 右侧面板对**所有选中的图**一次性操作：
  - **粘贴链接**：贴 `https://x.com/xxx/status/123`，自动识别平台、作品ID、账号 handle；账号没见过就弹出"绑定到哪个画师"（可模糊搜索，或新建）。
  - **tag 输入框**：自动补全 + 别名；"最近使用"快捷按钮；可设"默认 tag"（如 `character:红豆`），之后新导入的图自动带上。
  - 选中的多张图 = 同一作品的多页 → 一个按钮"合并为一个作品"，页码按选择顺序排。
- 全键盘操作：`Ctrl+V` 贴链接、`T` 聚焦 tag 框、`Enter` 确认并跳到下一组。
- 手机：同一界面做成响应式，长按进入多选。

## 6. 下载器
- 入口：界面里贴链接 / 批量贴一堆链接 → 后台调用 gallery-dl → 按 `{platform}/{post_id}_p{n}` 存入 → 元数据（画师 uid、handle、原始 tag、发布时间）直接写库。
- 登录态：
  - X：需要浏览器 cookies（`auth_token`、`ct0`），导出为 cookies.txt。建议用小号，频繁抓取有被限流/封号的风险。
  - Pixiv：gallery-dl 的 Pixiv 提取器需要 refresh token（`gallery-dl oauth:pixiv` 获取一次）。
- 原则：下载器只是录入的捷径。X/Pixiv 改接口导致失效时，手动录入流程必须仍然完整可用。
- 后期：Tampermonkey 用户脚本，在 Pixiv/X 页面加"存入图库"按钮，把当前链接 POST 给本地服务。

## 7. 浏览与检索
- 搜索语法：`character:红豆 -meta:R-18 artist:xxx platform:pixiv`（与 / 非 / 按画师 / 按平台）。
- 画师页：所有平台账号（链接由模板拼出）、作品墙、该画师下 tag 的统计。
- 作品详情：所有来源链接、所有页、tag。

## 8. 同步与备份
- 手机和 PC 之间同步整个图库目录，`.cache/` 排除。APK 默认（私有目录）下用 App 内"导入/导出图库"；开启共享文件夹高级选项后可用 Syncthing / 手动复制。
- **限制**：SQLite 不能两边同时改。约定一端为主（PC），手机以浏览为主；或两边改完后用"合并导入"（以 sha256 + source 为键合并）——放在后期做。
- `export` 命令：把 db 导出为 JSON，可以放进 git 做版本备份。

## 9. 里程碑
| 阶段 | 内容 | 完成标准 |
|---|---|---|
| M0 ✅ | 建库、CLI 导入（hash、文件名识别、收件箱） | 现有 200 张入库，Pixiv 的大部分自动识别（2026-10-27 完成：188 个样本全部入库，带 ID 的 62 个全部自动归档） |
| M1 | 后端 API（Starlette）+ 收件箱批量整理界面 | 能在 10 分钟内整理完 50 张 X 图 |
| ↳ M1a ✅ | `serve` 命令、收件箱列表接口、缩略图 | 浏览器能访问，接口能返回收件箱和缩略图 |
| ↳ M1b | 前端骨架（Vue 3 + Vite）、缩略图网格、多选 | 能看到收件箱并多选 |
| ↳ M1c | 粘贴链接识别、归档为作品、画师创建与绑定、**撤销最近一次归档** | 一张图贴链接后归档成功，且能撤销（归档不弹确认，靠撤销兜底） |
| ↳ M1d | tag：补全、别名、默认 tag；撤销扩展到打 tag | 能给作品打 tag，打错能撤销 |
| ↳ M1e | `scan` 找回文件；撤销扩展到其余批量操作 | 手动挪图后能找回 |
| M2 | 浏览、搜索、画师页、作品页 | 日常可用 |
| M3 | 内置下载器（gallery-dl） | 贴链接即入库，带元数据 |
| M4 | Briefcase 打 APK + GitHub Actions 自动发布；手机端界面适配；Termux 开发者文档 | 普通用户装 APK 即可离线使用 |
| M5 | pHash 相似图、用户脚本、双端合并、画质优选（第 10.1 节） | 锦上添花 |

## 10. 未来构想（尚未排期）

### 10.1 画质优选："保留更优画质"
**问题**：同一张图常有多个画质版本——X 网页另存的是压缩图，gallery-dl 可取原图；Pixiv 有原图 `ID_pN.png` 和预览 `ID_pN_master1200.webp`；画师可能私下给出原文件。用户希望图库里最终留下最好的那份。

**画质判定**（按优先级）：
1. 来源等级：`original`（Pixiv `_pN` 原图、X `name=orig`、画师原文件、手动标记）> `preview`（Pixiv `_master1200`、`_square1200`，X 网页另存）> `unknown`。
2. 像素数（宽 × 高）。
3. 无损格式（PNG）优先于有损（JPEG/WebP），仅在像素数相同时比较。
4. 文件大小。

**"同一张图"的判定**：
- 有来源 ID 时：同一 `(work, page)` 即同一张图。
- 无来源 ID 时（如 X 网页另存的图后来又下载了原图）：靠 pHash 相似度 + 人工确认，所以依赖 M5 的 pHash。

**行为**（设置项"保留更优画质"，默认开）：
- 新文件比旧文件好：新文件接替该 `(work, page)`，旧文件**移到 `.trash/`**（不直接删，遵守 AGENTS.md 规则 2），可在回收站恢复或清空。
- 新文件更差：不导入，报告里显示"已有更高画质版本"。
- 关闭该项时：保留所有版本，作为同一页的多个变体。
- 作品详情页提供"替换为原图"（手动指定文件，用于画师私下给的原文件）。

**与下载器（M3）的关系**：下载时默认请求最高画质（gallery-dl 对 Pixiv、X 默认就取原图）；对收件箱里"可能来自 X、ID 待补"的图，补上链接后可一键"下载原图并替换"。

**需要的结构变更（实施时再加迁移）**：`image.quality_tier`（original / preview / unknown）；`.trash/` 目录和对应的 op_log 记录。

**现状**：Pixiv 的 `_master1200` 预览文件已能识别出作品 ID 和页码，但还不会标记为预览；原图和预览图会作为同一页的两个文件并存。

**范围**：只针对静态图片。视频和 GIF 不判断画质、不做替换。
