"""智农宝 · 桌面启动器与安装器入口。

用法示例：
    智农宝.exe                     首次运行询问是否安装；已安装则直接启动
    智农宝.exe --install --silent  静默安装（安装完继续启动）
    智农宝.exe --uninstall         卸载（删除快捷方式、注册表项与安装目录）
    智农宝.exe --no-browser        只启动服务，不唤起浏览器
    智农宝.exe --port 9000         指定端口
    智农宝.exe --idle 0            关闭空闲自动退出
    智农宝.exe --status            打印安装状态 JSON 后退出
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import threading
import time
import traceback
from pathlib import Path

import installer
import runtime
from server import DEFAULT_PORTS, SiteHandler, create_server
from znlog import log, log_file

VERSION = installer.VERSION
APP_TITLE = installer.DISPLAY_NAME

MB_OK = 0x0
MB_YESNO = 0x4
MB_ICONERROR = 0x10
MB_ICONQUESTION = 0x20
MB_ICONINFORMATION = 0x40
MB_TOPMOST = 0x40000
IDYES = 6

_mutex_handle = None


# --------------------------------------------------------------------------
# 基础
# --------------------------------------------------------------------------
def msgbox(text: str, title: str = APP_TITLE, flags: int = MB_ICONINFORMATION) -> int:
    try:
        return ctypes.windll.user32.MessageBoxW(None, str(text), title, flags | MB_TOPMOST)
    except Exception:
        return 0


def resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def site_dir() -> Path:
    candidates = [
        resource_root() / "site",
        Path(__file__).resolve().parent.parent / "site",
        installer.install_dir() / "site",
    ]
    for candidate in candidates:
        if (candidate / "index.html").is_file():
            return candidate
    raise SystemExit("找不到站点资源：缺少 site/index.html")


def acquire_single_instance() -> bool:
    """同名互斥体：已经有一个实例时返回 False（随后转为唤起浏览器）。"""
    global _mutex_handle
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        _mutex_handle = kernel32.CreateMutexW(None, False, "Local\\ZhiNongBao.SingleInstance")
        # 必须用 get_last_error 读取，否则 ctypes 的后续调用会把错误码冲掉
        return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS
    except Exception:
        return True


def parse_args(argv):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--install", action="store_true", help="安装到本机")
    parser.add_argument("--uninstall", action="store_true", help="卸载")
    parser.add_argument("--silent", action="store_true", help="不弹确认框")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--no-prompt", action="store_true", help="首次运行不询问，直接便携运行")
    parser.add_argument("--port", type=int, default=0, help="指定监听端口")
    parser.add_argument("--idle", type=int, default=900, help="无访问后自动退出秒数，0 表示常驻")
    parser.add_argument("--status", action="store_true", help="打印安装状态后退出")
    return parser.parse_args(argv)


# --------------------------------------------------------------------------
# 子流程
# --------------------------------------------------------------------------
def do_uninstall(args) -> int:
    if not installer.is_installed():
        msgbox("本机没有检测到已安装的智农宝。", APP_TITLE, MB_ICONINFORMATION)
        return 0
    if not args.silent:
        answer = msgbox(
            "确定要卸载「智农宝」吗？\n\n将删除：\n"
            f"· 程序文件：{installer.install_dir()}\n"
            "· 桌面与开始菜单快捷方式\n"
            "· 当前用户的卸载注册表项\n\n"
            "源码包与比赛数据文件不在卸载范围内。",
            "卸载智农宝", MB_YESNO | MB_ICONQUESTION,
        )
        if answer != IDYES:
            return 0
    ok = installer.uninstall(silent=args.silent)
    log(f"卸载结果: {ok}")
    if not args.silent:
        msgbox("卸载完成。" if ok else f"卸载未完全成功，请查看日志：\n{log_file()}", APP_TITLE,
               MB_ICONINFORMATION if ok else MB_ICONERROR)
    return 0


def serve(args) -> int:
    running = runtime.find_running()
    if running:
        port = running[0]
        log(f"检测到已在运行的服务 :{port}，仅唤起浏览器")
        if not args.no_browser:
            runtime.open_browser(f"http://127.0.0.1:{port}/")
        return 0

    ports = (args.port,) if args.port else DEFAULT_PORTS
    httpd, port = create_server(site_dir(), VERSION, ports)
    # 端口被上一版进程占用时，宁可用临时端口也不要和别人的服务混在一起
    occupant = runtime.health(port)
    if occupant and occupant.get("pid") != os.getpid():
        log(f"端口 {port} 已有其它智农宝实例，改用临时端口")
        httpd.server_close()
        httpd, port = create_server(site_dir(), VERSION, (0,))
    url = f"http://127.0.0.1:{port}/"
    runtime.write_state(port)
    log(f"服务已启动 {url} (site={site_dir()})")

    threading.Thread(target=httpd.serve_forever, name="http", daemon=True).start()
    if not args.no_browser:
        runtime.open_browser(url)

    started = time.time()
    try:
        while True:
            time.sleep(0.5)
            if getattr(httpd, "shutdown_pending", False):
                log("收到关闭请求，退出")
                break
            idle = args.idle
            if idle and time.time() - SiteHandler.last_activity > idle and time.time() - started > idle:
                log("空闲超时，退出")
                break
    except KeyboardInterrupt:
        log("收到 Ctrl+C，退出")
    finally:
        runtime.clear_state()
        try:
            httpd.shutdown()
            httpd.server_close()
        except Exception:
            pass
    return 0


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    log(f"=== 启动 {VERSION} argv={argv} frozen={getattr(sys, 'frozen', False)}")

    if args.status:
        payload = {
            "installed": installer.is_installed(),
            "installDir": str(installer.install_dir()),
            "version": installer.installed_info().get("version"),
            "running": (runtime.find_running() or [None])[0],
            "site": str(site_dir()),
        }
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        print(text)
        log("status " + text.replace("\n", " "))
        return 0

    if args.uninstall:
        return do_uninstall(args)

    # 安装流程不受单实例限制：否则上一个实例刚退出时会被误判为“已在运行”而跳过安装
    if args.install:
        if not args.silent:
            answer = msgbox(
                f"即将把「智农宝」安装到本机：\n\n{installer.install_dir()}\n\n"
                "安装后会创建桌面与开始菜单快捷方式，并登记到「设置 → 应用」列表。\n\n继续吗？",
                "安装智农宝", MB_YESNO | MB_ICONQUESTION,
            )
            if answer != IDYES:
                return 0
        target = installer.install()
        if not args.silent:
            msgbox(f"安装完成。\n\n程序位置：{target}\n桌面与开始菜单已创建「{installer.DISPLAY_NAME}」快捷方式。",
                   APP_TITLE, MB_ICONINFORMATION)
        return serve(args)

    if not acquire_single_instance():
        if runtime.find_running():
            return serve(args)  # 已有实例在跑：只会唤起浏览器
        log("互斥体残留但没有服务在运行，继续启动新实例")

    # 首次双击：询问安装还是便携运行
    running_from_install_dir = installer.current_executable().resolve().parent == installer.install_dir().resolve()
    if getattr(sys, "frozen", False) and not args.no_prompt and not running_from_install_dir and not installer.is_installed():
        answer = msgbox(
            "要把「智农宝」安装到本机吗？\n\n"
            f"是：安装到 {installer.install_dir()}，创建桌面快捷方式，可在「设置 → 应用」中卸载\n"
            "否：仅本次运行（便携模式，不改动系统）",
            "智农宝 · 安装向导", MB_YESNO | MB_ICONQUESTION,
        )
        if answer == IDYES:
            target = installer.install()
            msgbox(f"安装完成，正在打开。\n\n程序位置：{target}", APP_TITLE, MB_ICONINFORMATION)

    return serve(args)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except SystemExit:
        raise
    except Exception as error:  # 兜底：窗口模式下没有控制台，只能弹窗
        log("未捕获异常:\n" + traceback.format_exc())
        msgbox(f"程序异常退出：\n{error}\n\n日志：{log_file()}", APP_TITLE, MB_ICONERROR)
        sys.exit(1)
