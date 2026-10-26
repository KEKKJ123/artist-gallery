"""安全的文件操作。AGENTS.md 规则 2：复制 → 校验 sha256 → 才允许删除源文件。"""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

_CHUNK = 1 << 20


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def _fsync_file(path: Path) -> None:
    with path.open("rb+") as f:
        os.fsync(f.fileno())


def _fsync_dir(path: Path) -> None:
    """把目录项（新文件名）落盘。Windows 不支持对目录 fsync，部分 FUSE 也不支持，失败就算了。"""
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
    """把 src 复制到 dst 并校验内容。dst 已存在则报错；失败时不留下半成品。

    返回时新文件已经 fsync 落盘：调用方随后删除源文件，即使紧接着断电，也不会两头都丢。
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        raise FileExistsError(f"目标已存在：{dst}")
    tmp = dst.with_name(dst.name + ".part")
    try:
        shutil.copyfile(src, tmp)
        try:
            shutil.copystat(src, tmp)  # 保留修改时间；Android FUSE 上可能不支持，失败不影响
        except OSError:
            pass
        _fsync_file(tmp)
        if sha256_file(tmp) != expected_sha:
            raise OSError(f"复制校验失败：{src}")
        os.replace(tmp, dst)
        _fsync_dir(dst.parent)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
