# 0003 Android 以 APK 发布；Web 框架改用 Starlette
- 日期：2026-10-26
- 状态：采纳；部分取代 0001；存储权限部分被 [0004](0004-Android存储与权限.md) 取代

## 背景
- 普通用户大多不会用 Termux，最省事的分发方式是 APK。
- 把 Python 打包进 APK 的主流方案是 Chaquopy（Briefcase 的 Android 后端也基于它）。它的原生包仓库里有 Pillow，但没有 pydantic-core。
- FastAPI 依赖 pydantic v2 → pydantic-core（Rust 扩展），在 Termux 和 Chaquopy 上都要自行编译，是打包的最大障碍。

## 决定
1. Web 框架用 **Starlette + uvicorn**（纯 Python 依赖链），不用 FastAPI。请求校验手写或用 dataclass。
2. 代码分三层，Android 外壳以后再套：
   - `core/`：纯逻辑（导入、识别、移动、tag），不感知运行环境。
   - `server/`：Starlette，提供 API 和前端静态文件。
   - `frontend/`：Vue 构建出的静态页面。
3. 发布形态：
   - PC / Termux：`python -m artist_gallery serve`，浏览器访问。
   - APK：Briefcase 打包；App 启动时在后台线程起 server，全屏 WebView 加载 localhost。
4. APK 由 GitHub Actions 编译：推送 `v*` tag 时构建并附加到 Release。本机不强制安装 Android Studio。
5. Termux 方案保留，作为开发者 / 进阶用户路径。

## 理由与代价
- 一套 Python 代码覆盖 PC、Termux、APK，三端行为一致。
- 代价：
  - APK 内含 Python 运行时，体积较大（实际大小待打包后确认）。
  - 图库放在共享存储时需要 MANAGE_EXTERNAL_STORAGE（"所有文件访问权限"），只适合侧载分发，上不了 Google Play。不走 SAF，因为它会让 Python 无法按路径操作文件。
  - 失去 FastAPI 的自动校验和 OpenAPI 文档。
- 待验证：gallery-dl 在 Chaquopy 下能否正常运行（M3/M4 时测试）。

## 对依赖的约束（补充 AGENTS.md 规则 6）
新增运行时依赖必须满足其一：纯 Python；或在 Chaquopy 包仓库（https://chaquo.com/pypi-13.1/）中有对应包。
