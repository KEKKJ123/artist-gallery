# artist-gallery

本地画师作品图库：按 **画师 / 来源（平台+作品ID）/ tag** 管理图片，支持 Pixiv、X 及自定义平台，图库可整体复制到手机使用。

纯本地运行，不需要联网，不依赖任何平台 API。图片数据只存在你自己的磁盘上。

## 功能现状

进度与设计文档 [第 9 节里程碑](docs/design.md) 保持一致：

- [x] **M0** 命令行建库、导入（sha256 去重、文件名识别来源、收件箱）、统计
- [ ] **M1** 收件箱批量整理界面
  - [x] M1a 本地网页服务、收件箱列表接口、缩略图
  - [x] M1b 前端骨架、缩略图网格、多选、键盘操作、大图预览
  - [ ] M1c 粘贴链接识别、归档为作品、画师绑定、撤销
  - [ ] M1d tag（补全、别名、默认 tag）
  - [ ] M1e 扫描找回被挪动的文件
- [ ] **M2** 浏览、搜索、画师页、作品页
- [ ] **M3** 内置下载器（gallery-dl）
- [ ] **M4** Android APK（Briefcase + CI 自动发布）
- [ ] **M5** pHash 相似图、画质优选、浏览器用户脚本

完整设计见 [docs/design.md](docs/design.md)，技术决策见 [docs/decisions/](docs/decisions/)。

> 目前网页界面可以浏览收件箱、多选、大图预览，但还不能归档和打 tag（M1c、M1d）。导入图片用命令行。

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

## 把图库带到手机上

图库就是一个普通文件夹（`library.db` + `images/`），**整个复制过去**即可，数据库里只存相对路径。

- 不用关服务也能复制：数据库不使用 WAL（见 [ADR 0006](docs/decisions/0006-wal-不开启.md)），图库里没有 `-wal`、`-shm` 之类的附属文件。只要避开正在导入或整理的瞬间就行。
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
