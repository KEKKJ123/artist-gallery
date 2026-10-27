# 模块边界与依赖方向

本文是当前代码的地图，不增改功能需求。需求以 `design.md`、交互以 `frontend-style.md` 为准。

## 后端

```text
server/app.py       组装路由、中间件、应用配置；不放处理器或业务逻辑
  ├─ api.py         列表 API：解析请求参数 → 调用 core → JSON
  ├─ media.py       原图的访问边界、缩略图响应与缓存头
  ├─ pages.py       前端页面兜底
  └─ context.py     请求级连接与共用参数解析；不反向 import app

core/browse.py ─┬─ images.py    共用图片投影、分页边界、按哈希查询
core/inbox.py  ─┘      └─ media.py     媒体格式能力表，无 Pillow 依赖
core/browse.py ─── layout.py    图库相对目录约定，无导入逻辑
core/platforms.py              内置平台定义及平台列表查询
core/importer.py               导入与确认后的源文件删除（写操作）
core/thumbnail.py              缩略图生成（Pillow），共用 media.py 的格式表
```

- `browse` 可调用 `inbox.count_inbox_hinted` 取得导航统计，但不得为了常量或共用投影引入导入流程。
- 只读查询不依赖 `importer`、`thumbnail` 或 Pillow；新增共用能力放在真正所属模块，不能随手挂到收件箱上。
- `core` 不依赖 `server` / Web 框架。处理器保持普通 `def`，每次请求在 `context.connection` 内开关连接。
- `db.open_library` 负责启动时的校验、迁移和平台同步；请求里的 `db.connect` 只连接已经校验过的图库。
- HTTP 路径、JSON 结构、分页规则不因模块移动而改变；数据库结构、迁移与文件操作语义也不变。

## 前端

```text
App / components
  ├─ stores/inbox.js       当前视图的协调器；显式列出界面能用的状态与动作
  │    ├─ useImageCollection   分页、加载错误、请求代次、去重
  │    ├─ useImageSelection    选择、焦点、当前预览；只接收图片集合
  │    └─ stores/library.js    全库导航统计与平台资料，共享但不依赖当前视图
  ├─ useGalleryNavigation     地址栏同步、窄屏抽屉；通过回调读写视图
  ├─ useGalleryKeys           网格层快捷键；通过回调执行动作
  └─ PreviewOverlay
       └─ usePreviewViewport  尺寸、缩放状态、鼠标和双指手势
            └─ lib/zoom.js    纯数学计算
```

`use…` 函数放在 `frontend/src/composables/`。它们是可单独使用的 Vue 状态模块：

- 不 import Pinia、store、组件或 API；输入通过 ref / getter / 回调传入。
- 分页模块只调用传入的 `fetchPage(offset)`，不知道取的是收件箱还是文件夹。
- 选择模块不知道网络与分页；协调器在接纳新列表后调用 `prune`，换视图时调用 `reset`。
- 预览舞台不知道图片来源、帮助弹层和图库；组件只负责显示信息、切图及键盘优先级。
- 需要监听浏览器事件的模块自行在卸载时清理，不留全局监听器。

`library` store 独立刷新全库资料：导航用自己的请求代次丢弃旧结果；平台请求合并并发、缓存成功结果（包括空列表），失败可重试。两种请求失败都保留已有资料，不阻断图片显示。

`lib/` 保持不依赖 Vue / Pinia 的基础模块；网络只从 `lib/api.js` 发出。不要为了减少几行接线代码，把共享资料再次塞回当前图片的 store。

## 守护测试

- `tests/test_layering.py`：core 不依赖 Web；只读查询不依赖写流程或图片解码器；Python 本地模块无静态 import 环。
- `frontend/tests/module-boundaries.test.js`：lib / composables / stores 的依赖方向、本地模块无静态 import 环、路径大小写匹配（Windows 同样检查）。
- 新增模块有独立测试；原 store 和 App 的集成测试仍保留，覆盖快速切换、分页、选择、预览及帮助弹层之间的事件传递。

这些检查不替代审查和真实浏览器验证，但能阻止常见的依赖倒流。
