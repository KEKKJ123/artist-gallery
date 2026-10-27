"""图库内目录约定；只描述相对路径，不执行导入或文件操作。"""

from pathlib import PurePosixPath

IMAGES_DIR = "images"
INBOX_DIR = "_inbox"
INBOX = PurePosixPath(IMAGES_DIR, INBOX_DIR)
