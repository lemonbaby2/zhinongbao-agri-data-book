"""智农宝本地只读静态服务器。

设计要点：
* 只监听 127.0.0.1，不对外网开放，不写入用户数据；
* 站点是纯静态资源，不需要后端数据库；
* 支持单页应用的 hash 路由 → 非文件路径回落到 index.html；
* /data/ 下的缺失文件返回真正的 404，避免前端把 404 页面当 JSON 解析；
* 提供 /__zn/health 与 /__zn/shutdown 两个内部端点，供单实例复用与卸载流程使用。
"""

from __future__ import annotations

import json
import mimetypes
import os
import socket
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

APP_TOKEN = "zhinongbao"
DEFAULT_PORTS = (8765, 8766, 8767, 8768, 8769, 0)

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")


class SiteHandler(SimpleHTTPRequestHandler):
    server_version = "ZhiNongBao/2.0"
    protocol_version = "HTTP/1.1"

    # 由 create_server 注入
    site_dir = Path(".")
    app_version = "2.2.0"
    last_activity = time.time()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(self.site_dir), **kwargs)

    # ---------- 日志 ----------
    def log_message(self, fmt, *args):  # noqa: A003 - 覆盖基类签名
        from znlog import log  # 延迟导入，避免循环依赖
        log("http " + (fmt % args))

    # ---------- 路由 ----------
    def do_GET(self):  # noqa: N802
        SiteHandler.last_activity = time.time()
        path = unquote(urlsplit(self.path).path)
        if path == "/__zn/health":
            import os
            return self.send_json({"app": APP_TOKEN, "version": self.app_version, "port": self.server.server_address[1], "pid": os.getpid()})
        if path == "/favicon.ico":
            self.path = "/assets/favicon.svg"
            return super().do_GET()
        if not self._is_file(path):
            # 数据目录缺失文件必须真 404；其它未知路径交给前端路由
            if path.startswith("/data/"):
                return self.send_error(404, "Not Found")
            self.path = "/index.html"
        return super().do_GET()

    def do_HEAD(self):  # noqa: N802
        SiteHandler.last_activity = time.time()
        return super().do_HEAD()

    def do_POST(self):  # noqa: N802
        SiteHandler.last_activity = time.time()
        path = unquote(urlsplit(self.path).path)
        if path == "/__zn/shutdown":
            self.send_json({"ok": True})
            self.server.shutdown_pending = True
            return
        return self.send_error(405, "Method Not Allowed")

    # ---------- 工具 ----------
    def _is_file(self, url_path: str) -> bool:
        relative = url_path.lstrip("/")
        if not relative:
            return False
        target = (self.site_dir / relative).resolve()
        try:
            target.relative_to(self.site_dir.resolve())
        except ValueError:
            return False
        return target.is_file()

    def send_json(self, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        if not self._headers_buffer_has_cache():
            suffix = Path(urlsplit(self.path).path).suffix.lower()
            if suffix in {".html", ".js", ".css", ".json"}:
                self.send_header("Cache-Control", "no-store")
            else:
                self.send_header("Cache-Control", "public, max-age=3600")
        super().end_headers()

    def _headers_buffer_has_cache(self) -> bool:
        buffer = getattr(self, "_headers_buffer", None) or []
        return any(b"Cache-Control" in item for item in buffer)


def port_in_use(port: int, timeout: float = 0.1) -> bool:
    """端口是否已被别人监听。

    Windows 下仅靠 bind 判断不可靠：只要旧进程设置了 SO_REUSEADDR，
    新进程还能绑上同一端口，请求会被随机分给两个进程（实测会看到上一版页面）。
    所以先主动连一次，确认端口是否已有服务在听。
    """
    if not port:
        return False
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def create_server(site_dir: Path, version: str = "2.2.0", ports=DEFAULT_PORTS):
    """依次尝试端口，全部被占用时用系统临时端口。返回 (httpd, port)。"""
    SiteHandler.site_dir = Path(site_dir)
    SiteHandler.app_version = version
    last_error = None
    for port in ports:
        if port_in_use(port):
            last_error = OSError(f"端口 {port} 已被占用")
            continue
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", port), SiteHandler)
            httpd.daemon_threads = True
            httpd.shutdown_pending = False
            return httpd, httpd.server_address[1]
        except OSError as error:  # 端口占用，试下一个
            last_error = error
    raise RuntimeError(f"无法绑定本地端口: {last_error}")
