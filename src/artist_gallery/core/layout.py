"""图库内目录约定；只描述相对路径，不执行导入或文件操作。"""

from pathlib import PurePosixPath

IMAGES_DIR = "images"
INBOX_DIR = "_inbox"
ARCHIVED_DIR = "archived"
INBOX = PurePosixPath(IMAGES_DIR, INBOX_DIR)
ARCHIVED = PurePosixPath(IMAGES_DIR, ARCHIVED_DIR)
