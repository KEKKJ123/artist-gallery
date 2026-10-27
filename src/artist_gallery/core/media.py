"""媒体格式能力表；查询、导入和缩略图生成共用，不依赖 Pillow。"""

IMAGE_EXTS = frozenset({".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"})
VIDEO_EXTS = frozenset({".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"})
MEDIA_EXTS = IMAGE_EXTS | VIDEO_EXTS
# GIF 和视频不生成缩略图。
THUMB_EXTS = IMAGE_EXTS - {".gif"}
