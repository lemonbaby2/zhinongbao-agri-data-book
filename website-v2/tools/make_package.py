"""把交付物打成一个 zip：源码 + 数据 + exe + 文档。

用法：python tools/make_package.py
产物：dist/智农宝_网站与安装源码_v2.0.0.zip
"""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = "2.2.0"
ZIP_NAME = f"智农宝_网站与安装源码_v{VERSION}.zip"

INCLUDE_DIRS = ["site", "desktop", "tools", "docs", "dist"]
INCLUDE_FILES = ["README.md", "start_dev.bat", "requirements-dev.txt"]

SKIP_DIR_NAMES = {"__pycache__", "node_modules", "build", ".git", ".playwright-cli", "outputs"}
SKIP_FILE_NAMES = {"package.json", "package-lock.json"}
SKIP_SUFFIXES = {".pyc", ".pyo", ".old", ".log"}


def should_skip(path: Path) -> bool:
    if any(part in SKIP_DIR_NAMES for part in path.parts):
        return True
    if path.name in SKIP_FILE_NAMES:
        return True
    # dist 里若残留旧版本的 exe / zip，只收录当前版本，避免重复与体积膨胀
    name = path.name
    if name.startswith("智农宝_安装程序_") and name != f"智农宝_安装程序_v{VERSION}.exe":
        return True
    if name.startswith("智农宝_网站与安装源码_") and name != ZIP_NAME:
        return True
    return path.suffix.lower() in SKIP_SUFFIXES


def iter_files(base: Path):
    for path in sorted(base.rglob("*")):
        if path.is_dir() or should_skip(path):
            continue
        yield path


def main() -> None:
    dist = ROOT / "dist"
    out = dist / ZIP_NAME
    # 先写到 dist 之外再搬进来：如果直接把 zip 写进 dist 目录，
    # 遍历打包时会把正在写的 zip 自己也收进去，文件会无限膨胀。
    temp = ROOT / (ZIP_NAME + ".building")
    if temp.exists():
        temp.unlink()

    count = 0
    total = 0
    with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name in INCLUDE_FILES:
            path = ROOT / name
            if path.is_file():
                archive.write(path, f"智农宝_v{VERSION}/{name}")
                count += 1
                total += path.stat().st_size
        for folder in INCLUDE_DIRS:
            base = ROOT / folder
            if not base.is_dir():
                continue
            for path in iter_files(base):
                # desktop/dist 与 desktop/build 是 PyInstaller 中间产物，不重复收录
                first = path.relative_to(base).parts[0]
                if folder == "desktop" and first in {"dist", "build"}:
                    continue
                if path.name == ZIP_NAME or path.name == "package.sha256":
                    continue
                relative = path.relative_to(ROOT)
                archive.write(path, f"智农宝_v{VERSION}/{relative.as_posix()}")
                count += 1
                total += path.stat().st_size

    if out.exists():
        out.unlink()
    temp.replace(out)

    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    size = out.stat().st_size / (1024 * 1024)
    print(f"已生成 {out}")
    print(f"  条目 {count} 个 · 原始 {total / 1024 / 1024:.1f} MB · 压缩后 {size:.1f} MB")
    print(f"  SHA-256 {digest}")
    (dist / "package.sha256").write_text(f"{digest}  {ZIP_NAME}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
