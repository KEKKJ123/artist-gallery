# 前端本地调试方案

> **状态：方案文档。** 命令按 [AGENTS.md](../AGENTS.md)、`frontend/package.json`、`frontend/vite.config.js` 整理；第 3 节的 403 结论已用 `WriteGuard` 模拟验证，**其余步骤（`npm ci`、Vite 实际运行、DevTools 扩展、VS Code 断点）尚未在本机端到端跑通**，首次使用时请对照第 9 节“常见问题”核对。
> 配套文档：[frontend-visual-design.md](frontend-visual-design.md)、[frontend-state-transitions.md](frontend-state-transitions.md)。

## 1. 三种调试方式怎么选

| 方式 | 地址 | 适合 | 局限 |
|---|---|---|---|
| **A. Vite 开发服务器** | `http://localhost:5173` | 改样式、布局、组件；热更新；看源码断点 | **写操作会被后端拒绝（见第 3 节）**，需要先解决 |
| **B. 构建产物 + 后端** | `http://localhost:9000` | 验证最终效果；归档、保存等写操作的真实流程 | 代码已压缩，没有热更新，**不能用 Vue DevTools 看组件**（生产构建默认关闭） |
| **C. 单元测试（Vitest）** | 终端 | 状态转移、store 逻辑、竞态；不需要后端和图库 | 不是真实浏览器环境（jsdom），看不到真实布局 |

建议组合：**状态逻辑用 C**，**界面外观用 A（只读操作）**，**写操作流程用 B 做最终确认**。

## 2. 前置条件

| 项目 | 要求 | 本机现状（2026-10-29 检查） |
|---|---|---|
| Node | ≥ 22.12，或 20.19+ | v24.18.0，符合 |
| 前端依赖 | 首次或锁文件变化时 `npm ci` | 2026-10-29 本轮依赖已存在，交互测试与 `npm run build` 通过，无需重复安装 |
| Python 环境 | 3.12+，依赖与解释器版本一致 | 早先出现过 Python／Pillow 版本不一致；2026-10-29 本轮已通过 `python -m artist_gallery serve --help` 及归档后端测试，不应再默认要求重建环境 |
| 端口 | 后端用 9000 | 8765 位于 Windows 保留范围 `8741–8840`，无法监听 |

## 3. 已知问题：Vite 代理会让写操作返回 403

**现象**：用方式 A 打开 5173 页面，浏览、缩略图、大图都正常，但草稿保存、保存资料、归档、撤销等写操作失败，提示“写操作只接受本图库页面的同源请求”。

**原因**：

1. `server/write_guard.py` 要求写请求的 `Origin` 必须等于 `scheme://Host`。
2. 浏览器在 5173 页面发出的请求带 `Origin: http://localhost:5173`。
3. `vite.config.js` 的代理设置了 `changeOrigin: true`，它只把 `Host` 改成后端地址（如 `127.0.0.1:9000`），**不会改写 `Origin`**。
4. 两者不一致，被判定为非同源，返回 403。

**验证**（把 `WriteGuard` 单独放进最小 ASGI 应用，构造三种请求）：

| 请求 | 结果 |
|---|---|
| 直接访问 9000：`Origin=http://localhost:9000`，`Host=localhost:9000` | 200 |
| 模拟 Vite 代理：`Origin=http://localhost:5173`，`Host=127.0.0.1:9000` | **403** |
| 无 `Origin` 头（如 curl） | 200 |

这是对中间件的隔离验证，没有启动真实的 Vite；Vite 实际转发的头以首次运行时 Network 面板为准。

**这是后端有意设计的安全边界**（防止别的网站借浏览器写入本地图库），**不应该为了方便调试放宽后端校验**。

可选的解决办法，均需要改仓库文件，**本文档所在 PR 不包含**，待确认后另开 PR：

| 办法 | 做法 | 评价 |
|---|---|---|
| ① 代理里改写 Origin（推荐） | 在 `vite.config.js` 的代理项加 `configure`，`proxyReq.setHeader('origin', 后端地址)`，仅在 `npm run dev` 时生效 | 只影响开发服务器，不动后端，不进构建产物 |
| ② 后端地址可配置 | `const backend = process.env.AG_BACKEND ?? 'http://127.0.0.1:8765'` | 解决端口被保留的问题，和 ① 一起做 |
| ③ 只读调试 | 暂不改动，用 A 看界面，用 B 或 C 验证写操作 | 无需改代码，但无法在热更新下调试归档流程 |

在 ①② 落地前，**写操作流程请用方式 B 或 C**。

## 4. 方式 A：Vite 开发服务器

### 4.1 准备测试图库

归档会移动图库内的文件，请使用专门的测试图库，不要用正式图库。导入只复制，不删源：

```powershell
.\.venv\Scripts\artist-gallery.exe init "D:\GalleryDev"
.\.venv\Scripts\artist-gallery.exe import "D:\GalleryDev" "D:\测试图片" --delete-source no
```

### 4.2 启动

终端 1，后端（使用未被保留的端口）：

```powershell
.\.venv\Scripts\artist-gallery.exe serve "D:\GalleryDev" --port 9000
```

终端 2，前端：

```powershell
Set-Location frontend
npm ci
npm run dev
```

浏览器打开 **`http://localhost:5173`**（不是 9000）。

**注意**：当前 `vite.config.js` 代理目标写死为 `127.0.0.1:8765`。要连到 9000 的后端，需要完成第 3 节的 ②；否则接口请求会失败。在此之前，请改用方式 B 或 C。

### 4.3 能做什么

- 保存 `.vue`／`.css` 后页面热更新，无需刷新。
- 浏览器 F12 → Sources 中可看到源码文件并打断点。
- 写操作受第 3 节限制。

## 5. 方式 B：构建产物 + 后端

`serve` 直接托管 `src/artist_gallery/server/static/`，页面与接口同源，写操作正常。

```powershell
Set-Location frontend
npm ci
npm run build        # 产物写入 ../src/artist_gallery/server/static/
Set-Location ..
.\.venv\Scripts\artist-gallery.exe serve "D:\GalleryDev" --port 9000
```

访问 `http://localhost:9000`。

**注意**：

- `npm run build` 会**清空并重写已提交的 `static/` 目录**（`vite.config.js` 里 `emptyOutDir: true`）。仅为本地试验而构建时，提交前请确认 `git status` 里的 `static/` 变化是你有意提交的；改了 `frontend/` 就必须一起提交，否则 CI 的 `frontend` 任务报错。
- 构建产物是压缩代码，F12 看到的不是源码；需要定位问题请回到方式 A 或 C。

## 6. 工具

### 6.1 Vue DevTools 浏览器扩展（推荐）

在 Edge／Chrome 应用商店搜索 “Vue.js devtools” 安装。**只对开发服务器（方式 A）生效**，方式 B 的生产构建默认不启用。

- Components：组件树，查看和修改 props、状态。
- Pinia：查看 `review`、`inbox`、`prefs`、`library` 的实时状态，支持时间线和直接编辑。调试归档流程时重点看 `review.archivePlan`、`review.busy`、`review.notice`。
- Timeline：事件和组件更新记录。

不需要改项目。

### 6.2 浏览器开发者工具（F12）

| 面板 | 用途 |
|---|---|
| Elements | 查看 DOM、样式；验证右上角提示框（`.toast-region`、`.toast`）的 `pointer-events`、`z-index`、`top` 位置 |
| Network | 查看 `/api/...` 请求、状态码、响应体；定位 403、409 等 |
| Sources | 给源码打断点、单步执行（方式 A） |
| Console | 查看前端抛出的错误 |
| Application → Local Storage | 检查草稿的本地兜底副本（`review-drafts.js` 管理） |

### 6.3 VS Code 断点调试

**Python 服务端和 Vue 前端是两个进程，需要两个调试器。** Python 断点由 Python Debugger 扩展处理；Vue／JavaScript 断点由 VS Code 内置浏览器调试器处理。只在普通终端执行 Python 命令，不会自动连接 VS Code 调试器。

安装 Microsoft 的 Python、Python Debugger，以及 Vue - Official 扩展。执行“Python: Select Interpreter”，选择项目 `.venv`。在本机 `.vscode/launch.json` 中添加以下配置（`.vscode/` 已被忽略，不提交图库路径）：

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python：图库服务端",
      "type": "debugpy",
      "request": "launch",
      "module": "artist_gallery",
      "args": ["serve", "${input:galleryRoot}", "--port", "9000"],
      "cwd": "${workspaceFolder}",
      "console": "integratedTerminal",
      "justMyCode": true
    },
    {
      "name": "Vue：Vite 源码（当前只读联调）",
      "type": "msedge",
      "request": "launch",
      "url": "http://localhost:5173",
      "webRoot": "${workspaceFolder}/frontend"
    },
    {
      "name": "浏览器：后端页面（完整写入流程）",
      "type": "msedge",
      "request": "launch",
      "url": "http://localhost:9000",
      "webRoot": "${workspaceFolder}/src/artist_gallery/server/static"
    }
  ],
  "inputs": [
    {
      "id": "galleryRoot",
      "type": "promptString",
      "description": "专用测试图库的绝对路径（不要填正式图库）"
    }
  ]
}
```

使用 Chrome 时把 `msedge` 改成 `chrome`。

**调试 Python 和真实归档流程：**

1. 准备专用测试图库，参照第 4.1 节；启动前停止占用同端口的旧服务。
2. 选择“Python：图库服务端”，按 F5，输入测试图库路径。等价命令是 `.\.venv\Scripts\python.exe -m artist_gallery serve "D:\GalleryDev" --port 9000`，但由调试器启动。
3. 在 `server/editing.py` 的 `archive` 或 `core/archiving.py` 的 `archive` 中打断点；选择“浏览器：后端页面”启动另一个调试会话（也可普通浏览器打开 9000）。
4. 点击归档，Python 断点会在请求处理时命中；F10 单步、F11 进入函数、F5 继续。同步请求在线程池中执行也能断点，不需要改为 `async def`。
5. 当前 CLI 没有热重载参数。修改 Python 后停止并重新 F5；停在写入／文件操作中间时不要强行结束进程，尽量继续到请求完成。此页面使用构建产物，修改 Vue 后需重新构建，不能期待 `.vue` 源码断点直接绑定生产包。

**调试 Vue 源码：**

1. 前端终端进入 `frontend`，执行 `npm run dev`，等 Vite 打印就绪地址；若实际端口不是 5173，同步修改浏览器配置。
2. 选择“Vue：Vite 源码”并启动。在 `frontend/src/stores/review.js` 或 `.vue` 的 `<script setup>` 可执行语句处打断点；点击界面触发，查看变量和调用栈。模板、CSS 布局使用浏览器 Elements 与 Vue DevTools 查看。
3. 浏览器必须是调试器启动的窗口；只启动 Vite 的 Node 调试器不会调试浏览器中的 Vue 代码。空心断点先确认访问的是 5173、不是生产包 9000，且 `webRoot` 指向 `frontend`。
4. **现有代理固定连接后端 8765，而以上 Python 示例使用 9000，两者不能直接联调。** 若 8765 可用，可将 Python 配置端口改成 8765 来做只读联调；端口不可用则需要另行调整 Vite 代理目标。即便端口一致，写操作仍有第 3 节的 403 限制。本次不修改代理或后端安全校验。
5. 在未解决代理问题前，Vue 归档逻辑可用第 7 节的 JavaScript 调试终端运行 `npm test -- tests\review-ui.test.js tests\review-store.test.js`，对模拟 API 的测试打断点；真实写入则使用 9000 页面配合 Python 断点。

以上启动配置已按 CLI 入口核对，但 VS Code／真实浏览器的断点命中仍需本机手动验证。

### 6.4 需要新增依赖的工具（暂不采用）

| 工具 | 用途 | 说明 |
|---|---|---|
| `vite-plugin-vue-devtools` | 页面内嵌 DevTools，免装扩展 | 新增开发依赖 |
| `@vitest/ui` | 网页界面查看测试 | 新增开发依赖 |

前端依赖要尽量少（见 frontend-style 第 8 节），扩展和浏览器自带工具已够用；如确需，请先与红豆确认。

## 7. 方式 C：用单元测试调试状态逻辑

```powershell
Set-Location frontend
npm test              # 跑一遍
npm run test:watch    # 保存即重跑
```

适用于状态转移类问题（如归档流程中 `archivePlan` 的变化），不需要后端和图库：在测试里模拟 `lib/api.js` 的函数，断言 store 的状态序列。现有测试位于 `frontend/tests/`，如 `inbox-store.test.js`、`prefs-store.test.js`，可参考其写法。VS Code 里也可以给测试代码打断点，用“JavaScript 调试终端”运行 `npm run test:watch`。

状态逻辑改动应先写这类测试，再对照 [frontend-state-transitions.md](frontend-state-transitions.md) 第 9 节的覆盖表。已有的归档流程测试可直接参考 `review-store.test.js` 里“单图正常归档全程不写入清单，弹窗不会闪现；成功后发出提示”一条：它在 `executeArchive` 的 mock 里读取 `review.archivePlan`，从而断言请求进行中清单为空；提示框的计时测试见 `toast-notice.test.js`（用假计时器）。

## 8. 用“单张正常归档”走一遍

单张正常归档改动前会先弹清单再自动执行，现在已改为直接执行（[frontend-state-transitions.md](frontend-state-transitions.md) 第 3、4 节）。可以用下面的步骤在真实浏览器里确认，**这一步目前没有人工执行过**：

1. 在 `review.js` 的 `prepareArchive` 中，`plan = {...}` 赋值行和 `archivePlan.value = plan` 行各打一个断点。
2. 在 Pinia 面板观察 `review.archivePlan`、`review.busy`、`review.noticeSeq`。
3. 点击单张图“正常归档”：应停在第一个断点，**不会**停在第二个；`archivePlan` 全程为 null，页面不出现清单弹窗；请求返回后 `noticeSeq` 加一，右上角出现提示，约 3 秒后消失。
4. 再试强制归档或选中多张归档：应停在第二个断点，`archivePlan` 有值。单图强制归档没有复选框，须点击弹窗中的“强制归档”才执行；多张归档仍要求勾选范围确认。
5. 在 Elements 面板确认提示框外层 `.toast-region` 的 `pointer-events` 为 `none`，并在提示显示期间点击顶栏按钮，确认能响应。
6. 写操作需要方式 B，或完成第 3 节办法 ①② 后使用方式 A。

## 9. 常见问题

| 现象 | 可能原因 |
|---|---|
| 5173 页面数据为空，Network 里接口失败 | 后端没启动，或代理目标端口与后端不一致（第 4.2 节） |
| 5173 页面浏览正常，保存／归档 403 | 第 3 节：Origin 与 Host 不一致 |
| 9000 页面打开是旧界面 | 没有重新 `npm run build`，或浏览器缓存，Ctrl+F5 |
| 找不到 Vue DevTools 面板 | 在生产构建（9000）页面使用；换到 5173 |
| `serve` 报 socket 权限错误 | 端口被 Windows 保留，换端口，见 README |
| 命令行报 `cannot import name '_imaging'` | `.venv` 的 Python 与 Pillow 二进制版本不一致，需重建 `.venv` |
| 弹窗打开时快捷键、预览被屏蔽 | 预期行为：`OperationDialogs` 隔离全局键盘，避免操作背后的选择变化 |
