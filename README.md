# artist-gallery

本地画师作品图库：按 **画师 / 来源（平台+作品ID）/ tag** 管理图片，支持 Pixiv、X 及自定义平台，图库可整体复制到手机使用。

纯本地运行，不需要联网，不依赖任何平台 API。图片数据只存在你自己的磁盘上。

## 功能现状

- [x] **M0** 命令行建库、导入（sha256 去重、文件名识别来源、收件箱）、统计
- [x] **M1a** 本地网页服务启动、收件箱列表 API、缩略图懒生成
- [ ] **M1** 收件箱批量整理界面（粘贴链接、打 tag、合并作品）
- [ ] **M2** 浏览、搜索、画师页、作品页
- [ ] **M3** 内置下载器（gallery-dl）
- [ ] **M4** Android APK（Briefcase + CI 自动发布）
- [ ] **M5** pHash 相似图、画质优选、浏览器用户脚本

完整设计见 [docs/design.md](docs/design.md)，技术决策见 [docs/decisions/](docs/decisions/)。

## 快速开始

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"

# 新建图库
.venv\Scripts\artist-gallery init D:\MyGallery

# 导入图片（只复制，不删源文件）
.venv\Scripts\artist-gallery import D:\MyGallery D:\下载\图片 -n   # 预演
.venv\Scripts\artist-gallery import D:\MyGallery D:\下载\图片      # 正式导入

# 统计
.venv\Scripts\artist-gallery status D:\MyGallery

# 启动网页服务（M1a，浏览器打开 http://localhost:8765）
.venv\Scripts\artist-gallery serve D:\MyGallery
```

> 需要 Python 3.12+。图片、数据库、cookies 均被 `.gitignore` 排除，不会进仓库。

## 技术栈

- Python 3.12 + SQLite + Pillow
- Starlette + uvicorn（纯 Python，无原生扩展，兼容 Android Termux）
- 前端 Vue 3 + Vite（M1b 起，构建产物提交进仓库，使用时不依赖 Node）

## 许可证

[GPL-2.0-or-later](LICENSE)。自己使用、修改不受限制；如果要把本项目或基于它修改的版本分发给别人，需要同样以 GPL 开源。

## 贡献

见 [CONTRIBUTING.md](CONTRIBUTING.md)。`main` 只通过 Pull Request 合入，CI 必须通过（Windows / Ubuntu × Python 3.12 / 3.14）。
