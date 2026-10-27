# artist-gallery

本地画师作品图库：目标是**一图一卡、作品组共享 tag、画师多平台账号、多来源关联与文件版本管理**，图库可整体复制到手机使用。平台是可叠加的来源信息，不是图片的互斥归属。

纯本地运行，不需要联网，不依赖任何平台 API。图片数据只存在你自己的磁盘上。

## 功能现状

**2026-10-28 起正在转向新整理模型，当前程序尚未切换。** [设计文档](docs/design.md) 描述目标，[过渡计划](docs/transition.md) 区分代码现状、迁移评审点与验收条件。本次 T0 只改文档，不升级图库。

已实现（旧模型下的能力）：

- [x] **M0** 命令行建库、导入（sha256 去重、文件名识别来源、收件箱）、统计
- [x] **M1a／M1b** 本地网页服务、缩略图、网格、多选、键盘操作、大图缩放／触摸、主题与只读文件夹浏览
- [x] 前后端模块化与依赖边界检查

新路线按以下顺序分批交付（**均未实现**，T0 是本次设计 PR）：

- [ ] **T1** 新关系模型与旧库兼容迁移：图片／文件版本、组成员、发布位置、明确整理状态
- [ ] **T2** 收件箱 → 自动建议 → 逐图检查／多行链接 → 正常或强制归档及撤销
- [ ] **T3** 多组共享 tag、画师关联、关系浏览与搜索
- [ ] **T4** 最小平台规则包、中性两区存储与旧文件搬迁（分别评审交付）
- [ ] 后续：完整浏览搜索（M2）、下载器（M3）、Android APK（M4）、原文件追溯／相似候选／双端合并（M5）

原 M1c～M1e 的实施安排由 T1～T4 替代。暂停中的 `feat/image-details-captions` 不包含在已实现清单里，也不会为转向而整批合并。

完整设计见 [docs/design.md](docs/design.md)，技术决策见 [docs/decisions/](docs/decisions/)。

> 当前网页仍按旧模型浏览收件箱和平台文件夹，不能核查、归档或打 tag；CLI 仍可能按平台自动归档。这是待替换行为，不是新路线承诺。新路线将所有新图先收入收件箱，平台规则只提建议；保留有无建议筛选，并提供正常／强制归档。**不要把下面的当前使用说明误认为新流程已交付。**

## 快速开始（电脑）

需要 Python 3.12 或更高版本。以 Windows 为例：

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"

# 新建图库
.venv\Scripts\artist-gallery init D:\MyGallery

# 导入图片（只复制，不删源文件）
.venv\Scripts\artist-gallery import D:\MyGallery D:\下载\图片 -n   # 预演：看看会怎么归档，不做任何改动
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
git clone <本仓库地址> ~/artist-gallery        # 放在 Termux 自己的目录，不要放 /sdcard
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
