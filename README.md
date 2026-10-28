# artist-gallery

本地画师作品图库：目标是**一图一卡、直接角色 tag／画师属性、多平台来源与文件版本管理**，图库可整体复制到手机使用。平台是可叠加的来源信息，不是图片的互斥归属。

纯本地运行，不需要联网，不依赖任何平台 API。图片数据只存在你自己的磁盘上。

## 功能现状

**T1 新模型基础与 T2 来源核查／归档／撤销已实现。** 设计与边界见 [design.md](docs/design.md)、[ADR 0010](docs/decisions/0010-图片直接属性与原名增量导入.md)。

- 当前格式版本 6，由基线 5 保留数据升级；改路线前旧开发库已弃用，不迁移、不保留专门筛查和旧 fixture。保留当前格式标识、版本升级和未知／过新库保护，程序不会自动清空或覆盖已有文件。
- 复制导入全部先进收件箱，尽量保留原文件名，文件名识别只提供来源建议，不自动归档或填未知 p0。
- 再次选择同一外部目录即可增量导入：hash 相同且副本完好时复用，保留已有标签／画师／来源／归档状态，保存新名称线索；外部文件减少不会删除图库。不是镜像同步。
- 网页支持收件箱／已归档两区、来源建议筛选、多选、固定标题、大图缩放／触摸和主题；同图多来源不会重复卡片。逐图检查可追加链接、人工确认／驳回／解除来源；保存不自动归档。
- 已建立直接内容 tag（含 `character:红豆`）、画师账号、多来源／可空页码／时间及文件版本关系，并提供只读投影；支持正常／强制归档与倒序撤销，文件失败／中断后展示恢复清单，不自动覆盖或重试。**打 tag、编辑画师与组合检索仍待 T3**。
- 检查界面电脑左图右资料、手机上下排列；上一张／跳过只切图。草稿按图库／图片独立保留，刷新和关闭浏览器后可恢复；当前展示文件大小在单选详情和检查页按需读取。
- 多选追加来源必须确认“全部有效链接 × 每张所选图”；混合缺项批次整批不执行，另选范围后再决定正常或强制归档。

下一步：T3 图片直接属性编辑／检索；T4 最小平台规则包。原文件追溯、下载器、Android APK 和双端合并后置，见 [实施计划](docs/transition.md)。暂停分支 `feat/image-details-captions` 保留，未整批合并，文件大小已按新文件版本关系适配。

旧平台文件夹 API 已移除；旧 `?folder=` 书签明确提示失效后回收件箱，不再代表平台来源。

## 快速开始（电脑）

需要 Python 3.12 或更高版本。以 Windows 为例：

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"

# 新建图库
.venv\Scripts\artist-gallery init D:\MyGallery

# 导入图片（只复制，不删源文件）
.venv\Scripts\artist-gallery import D:\MyGallery D:\下载\图片 -n   # 只读预演：查看导入计划，不做任何改动
.venv\Scripts\artist-gallery import D:\MyGallery D:\下载\图片      # 正式导入，完成后会询问是否删除源文件

# 统计
.venv\Scripts\artist-gallery status D:\MyGallery

# 启动网页服务，浏览器打开 http://localhost:8765
.venv\Scripts\artist-gallery serve D:\MyGallery
```

Linux / macOS 把 `.venv\Scripts\` 换成 `.venv/bin/` 即可。

## 快速开始（Android 手机，Termux）

在有 APK 之前（M4），可以用 [Termux](https://termux.dev/) 在手机上运行。这条路径面向愿意折腾的用户。

```bash
pkg install python python-pillow git
git clone https://github.com/KEKKJ123/artist-gallery.git ~/artist-gallery        # 放在 Termux 自己的目录，不要放 /sdcard
cd ~/artist-gallery
python -m venv .venv --system-site-packages     # 复用系统装好的 Pillow
. .venv/bin/activate
pip install -e .                                # 不要加 [dev]：其中的 ruff 需要在手机上编译 Rust

artist-gallery init ~/gallery
artist-gallery serve ~/gallery                  # 然后用手机浏览器打开 http://localhost:8765
```

要在手机上跑测试，额外执行 `pip install pytest httpx2`。

## 用手机访问电脑上的图库（局域网）

不想拷贝文件，只想在手机上看电脑里的图库：

1. 手机和电脑连**同一个 Wi-Fi**。
2. 电脑上启动服务时加 `--host 0.0.0.0`：
   ```bash
   .venv\Scripts\artist-gallery serve D:\MyGallery --host 0.0.0.0
   ```
3. 看终端里"手机访问"下面列出的地址，比如 `http://192.168.1.2:8765`，在**手机浏览器**里输入它。
4. 首次可能弹出 Windows 防火墙提示，选"允许专用网络"。

注意：
- **不要在浏览器里输入 `0.0.0.0`**，那不是一个能访问的地址；要用上面列出的那个 IP。
- 如果列出了好几个地址，选长得像家里 Wi-Fi 的（通常以 `192.168.` 开头）。开了代理软件或 VPN 时，会多出一些手机连不上的地址，终端会标注出来。
- 这个模式**没有登录保护**，同一个 Wi-Fi 里的人都能看到图库。用完请 Ctrl+C 停止；不要在咖啡店、学校等公共 Wi-Fi 上用。
- 手机访问的是电脑上的图库，手机本身不保存图片；要离线看，用下一节的拷贝方式。

## 把图库带到手机上

图库就是一个普通文件夹（`library.db` + `images/`），**整个复制过去**即可，数据库里只存相对路径。

- **复制／备份前先停止写操作，稳妥做法是停服务后复制整个图库。** 数据库不使用 WAL（见 [ADR 0006](docs/decisions/0006-wal-不开启.md)），但这不保证导入、数据库升级或文件搬迁期间复制得到一致快照。Git 不备份图库文件。
- 缩略图缓存目录 `.cache/` 不需要复制，用到时会自动重新生成。
- 同一时间只在一端修改图库：两端都改会各自产生记录，目前还没有合并功能（计划在 M5）。

## 技术栈

- Python 3.12 + SQLite + Pillow
- Starlette + uvicorn（纯 Python，无原生扩展，兼容 Android）
- 前端 Vue 3 + Pinia + Vite（源码在 `frontend/`；构建产物提交进仓库，所以只是使用的话不需要 Node）

## 许可证

[GPL-2.0-or-later](LICENSE)。自己使用、修改不受限制；如果要把本项目或基于它修改的版本分发给别人，需要同样以 GPL 开源。

## 贡献

见 [CONTRIBUTING.md](CONTRIBUTING.md)。`main` 只通过 Pull Request 合入，CI 必须通过（Windows / Ubuntu × Python 3.12 / 3.14）。开发约定见 [AGENTS.md](AGENTS.md)。

> 本仓库只存代码和文档。图片、数据库、cookies 均被 `.gitignore` 排除，不会进仓库。
