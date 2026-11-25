"""极简日志：写入 %LOCALAPPDATA%\\ZhiNongBao\\logs\\app.log（超过 1 MB 自动截断）。"""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

_lock = threading.Lock()
MAX_BYTES = 1024 * 1024


def log_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
    folder = Path(base) / "ZhiNongBao" / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def log_file() -> Path:
    return log_dir() / "app.log"


def log(message: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {message}\n"
    try:
        with _lock:
            target = log_file()
            if target.exists() and target.stat().st_size > MAX_BYTES:
                target.write_text("", encoding="utf-8")
            with target.open("a", encoding="utf-8") as handle:
                handle.write(line)
    except Exception:
        pass
    if getattr(sys, "frozen", False) is False and os.environ.get("ZN_VERBOSE"):
        sys.stderr.write(line)
