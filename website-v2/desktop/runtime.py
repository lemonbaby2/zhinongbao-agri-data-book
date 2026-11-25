"""运行时探测与浏览器唤起。

注意：这里用 http.client 而不是 urllib。
urllib 会读取系统代理环境变量，把 127.0.0.1 的探测请求也交给代理，
在开了 Clash / VPN 的机器上每次探测都要等超时（实测累计 7 秒以上）。
http.client 直连回环地址，端口未监听时会立即被拒绝。
"""

from __future__ import annotations

import http.client
import json
import os
import socket
import time
import webbrowser
from pathlib import Path

from znlog import log

APP_TOKEN = "zhinongbao"
PROBE_PORTS = tuple(range(8765, 8776))


def _port_open(port: int, timeout: float = 0.08) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def state_file() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
    folder = Path(base) / "ZhiNongBao"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "runtime.json"


def write_state(port: int) -> None:
    """记录当前监听端口，保证 --port 自定义时也能被下一次启动找到。"""
    try:
        state_file().write_text(json.dumps({
            "port": port, "pid": os.getpid(), "started": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, ensure_ascii=False), encoding="utf-8")
    except Exception as error:
        log(f"写入运行状态失败: {error}")


def clear_state() -> None:
    try:
        state_file().unlink(missing_ok=True)
    except Exception:
        pass


def read_state() -> dict:
    try:
        return json.loads(state_file().read_text(encoding="utf-8"))
    except Exception:
        return {}


def health(port: int, timeout: float = 0.4) -> dict | None:
    if not _port_open(port):
        return None
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        connection.request("GET", "/__zn/health")
        response = connection.getresponse()
        if response.status != 200:
            return None
        data = json.loads(response.read().decode("utf-8"))
        return data if data.get("app") == APP_TOKEN else None
    except Exception:
        return None
    finally:
        connection.close()


def find_running() -> tuple[int, dict] | None:
    state = read_state()
    if state.get("port"):
        info = health(int(state["port"]))
        if info:
            return int(state["port"]), info
    for port in PROBE_PORTS:
        info = health(port)
        if info:
            return port, info
    return None


def request_shutdown() -> bool:
    """尝试优雅关闭正在运行的服务（仅本机回环地址）。"""
    found = find_running()
    if not found:
        return False
    port, _ = found
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=1.5)
    try:
        connection.request("POST", "/__zn/shutdown", body=b"")
        response = connection.getresponse()
        response.read()
        log(f"已请求关闭服务 :{port} -> {response.status}")
        if response.status == 200:
            clear_state()
        return response.status == 200
    except Exception as error:
        log(f"关闭请求失败: {error}")
        return False
    finally:
        connection.close()


def open_browser(url: str) -> None:
    try:
        if not webbrowser.open(url):
            raise RuntimeError("webbrowser.open 返回 False")
        log(f"已唤起浏览器 {url}")
    except Exception as error:
        log(f"唤起浏览器失败: {error}")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
