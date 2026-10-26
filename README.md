# artist-gallery

本地画师作品图库：按 **画师 / 来源（平台+作品ID）/ tag** 管理图片，支持 Pixiv、X 及自定义平台，图库可整体复制到手机使用。

- 设计文档：[docs/design.md](docs/design.md)
- 开发约定：[AGENTS.md](AGENTS.md)
- 状态：M0 已完成（2026-10-27）：命令行建库、导入、统计。下一步 M1（Web 界面 + 收件箱整理）。

## 快速开始
```
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"

.venv\Scripts\artist-gallery init D:\MyGallery                    # 新建图库
.venv\Scripts\artist-gallery import D:\MyGallery D:\下载\图片 -n   # 预演：看看会怎么归档
.venv\Scripts\artist-gallery import D:\MyGallery D:\下载\图片      # 正式导入（移动；加 --copy 则保留原文件）
.venv\Scripts\artist-gallery status D:\MyGallery                  # 统计
```

> 本仓库只存代码和文档。图片、数据库、cookies 均被 `.gitignore` 排除。
