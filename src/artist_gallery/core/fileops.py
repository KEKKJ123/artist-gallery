"""安全文件复制：独占目标、校验、落盘，任何失败保留外部源文件。"""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from pathlib import Path

_CHUNK = 1 << 20


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def _fsync_dir(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def copy_verified(src: Path, dst: Path, expected_sha: str) -> None:
    """独占创建，不使用会覆盖竞争者文件的 replace；未返回前不允许删除源文件。

    临时副本先校验，再用 xb 取得最终文件。最终写入期间失败只清理自己创建的文件；
    未入库的中断残留下次导入会被视为占用，不覆盖。适用于无硬链接的 Android 存储。
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    created = False
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=dst.parent, prefix=".import-", suffix=".part", delete=False
        ) as f:
            tmp = Path(f.name)
            with src.open("rb") as source:
                shutil.copyfileobj(source, f, _CHUNK)
            f.flush()
            os.fsync(f.fileno())
        if sha256_file(tmp) != expected_sha:
            raise OSError(f"复制校验失败：{src}")
        with dst.open("xb") as target:
            created = True
            with tmp.open("rb") as source:
                shutil.copyfileobj(source, target, _CHUNK)
            target.flush()
            os.fsync(target.fileno())
        if sha256_file(dst) != expected_sha:
            raise OSError(f"目标校验失败：{dst}")
        try:
            shutil.copystat(src, dst)
        except OSError:
            pass
        _fsync_dir(dst.parent)
    except BaseException:
        if created:
            dst.unlink(missing_ok=True)
        raise
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
