# artist-gallery

本地画师作品图库：按 **画师 / 来源（平台+作品ID）/ tag** 管理图片，支持 Pixiv、X 及自定义平台，图库可整体复制到手机使用。

- 设计文档：[docs/design.md](docs/design.md)
- 开发约定：[AGENTS.md](AGENTS.md)
- 状态：M0 开发中（已有数据库结构和 `init` 命令）。

## 快速开始
```
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\artist-gallery init D:\MyGallery
.venv\Scripts\python -m pytest
```

> 本仓库只存代码和文档。图片、数据库、cookies 均被 `.gitignore` 排除。
