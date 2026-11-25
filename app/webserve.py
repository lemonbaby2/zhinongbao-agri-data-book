# -*- coding: utf-8 -*-
"""把 exe 内置的交互式网页版（21 页数据分析站）用本地回环服务跑起来，
交给系统默认浏览器打开。只绑 127.0.0.1，不对外暴露。"""
import os
import socket
import threading
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


class WebService:
    """惰性启动、复用端口、幂等。"""

    def __init__(self, site_dir):
        self.site = Path(site_dir)
        self.httpd = None
        self.port = None
        self._lock = threading.Lock()

    def _free_port(self):
        for p in range(18765, 18795):
            with socket.socket() as s:
                try:
                    s.bind(("127.0.0.1", p))
                    return p
                except OSError:
                    continue
        raise RuntimeError("找不到空闲端口")

    def start(self):
        with self._lock:
            if self.httpd is not None:
                return self.port
            if not self.site.exists():
                raise RuntimeError(f"网页版资源缺失：{self.site}")
            self.port = self._free_port()
            handler = partial(Handler, directory=str(self.site))
            self.httpd = ThreadingHTTPServer(("127.0.0.1", self.port), handler)
            t = threading.Thread(target=self.httpd.serve_forever, daemon=True)
            t.start()
            return self.port

    def open(self):
        port = self.start()
        webbrowser.open(f"http://127.0.0.1:{port}/index.html")
        return f"http://127.0.0.1:{port}/index.html"

    def stop(self):
        if self.httpd is not None:
            try:
                self.httpd.shutdown()
            except Exception:
                pass
            self.httpd = None
            self.port = None
