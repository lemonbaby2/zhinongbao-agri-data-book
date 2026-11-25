"""安装 / 卸载逻辑（纯用户态，不需要管理员权限）。

安装做四件事：
1. 把 exe 复制到 %LOCALAPPDATA%\\ZhiNongBao\\智农宝.exe；
2. 在桌面和开始菜单创建快捷方式；
3. 写入当前用户的卸载注册表项（设置 → 应用 里可见）；
4. 记录 version.json 便于判断是否已安装。

站点资源始终从 exe 内嵌的 bundle 提供，因此安装目录只有 exe，
不存在“装了两份数据”的问题；需要改源码请用配套的源码包。
"""

from __future__ import annotations

import ctypes
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

from znlog import log

APP_ID = "ZhiNongBao"
DISPLAY_NAME = "智农宝"
PUBLISHER = "智农宝重建版（本机比赛资料）"
EXE_NAME = "智农宝.exe"
VERSION = "2.2.0"

REG_ROOT = r"Software\Microsoft\Windows\CurrentVersion\Uninstall" + "\\" + APP_ID
FOLDERID_DESKTOP = "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}"
FOLDERID_PROGRAMS = "{A77F5D77-2E2B-44C3-A6A2-ABA601054A51}"
CREATE_NO_WINDOW = 0x08000000


# --------------------------------------------------------------------------
# 系统路径
# --------------------------------------------------------------------------
class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def known_folder(guid_text: str) -> Path:
    """通过 SHGetKnownFolderPath 取系统目录，兼容 OneDrive 重定向后的桌面。"""
    guid = _GUID()
    if ctypes.windll.ole32.CLSIDFromString(ctypes.c_wchar_p(guid_text), ctypes.byref(guid)):
        raise OSError("GUID 解析失败: " + guid_text)
    pointer = ctypes.c_wchar_p()
    result = ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(pointer))
    if result != 0:
        raise OSError(f"SHGetKnownFolderPath 失败: 0x{result & 0xFFFFFFFF:08X}")
    try:
        return Path(pointer.value)
    finally:
        ctypes.windll.ole32.CoTaskMemFree(pointer)


def local_app_data() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base)
    return Path.home() / "AppData" / "Local"


def install_dir() -> Path:
    return local_app_data() / APP_ID


def installed_exe() -> Path:
    return install_dir() / EXE_NAME


def version_file() -> Path:
    return install_dir() / "version.json"


def current_executable() -> Path:
    """当前进程的可执行文件；源码方式运行时返回 python 解释器。"""
    return Path(sys.executable if getattr(sys, "frozen", False) else sys.executable)


# --------------------------------------------------------------------------
# 快捷方式
# --------------------------------------------------------------------------
def create_shortcut(link_path: Path, target: Path, workdir: Path, description: str, icon: Path | None = None) -> bool:
    """用 WScript.Shell 创建 .lnk。

    脚本正文保持纯 ASCII，中文目标路径通过环境变量传入，
    避免 PowerShell 读取无 BOM 脚本时把中文读成乱码。
    """
    link_path.parent.mkdir(parents=True, exist_ok=True)
    script = (
        "$ErrorActionPreference='Stop';"
        "$sh=New-Object -ComObject WScript.Shell;"
        "$s=$sh.CreateShortcut($env:ZN_LNK);"
        "$s.TargetPath=$env:ZN_TARGET;"
        "$s.WorkingDirectory=$env:ZN_WORKDIR;"
        "$s.IconLocation=$env:ZN_ICON;"
        "$s.Description=$env:ZN_DESC;"
        "$s.WindowStyle=1;"
        "$s.Save()"
    )
    env = dict(os.environ)
    env.update({
        "ZN_LNK": str(link_path),
        "ZN_TARGET": str(target),
        "ZN_WORKDIR": str(workdir),
        "ZN_ICON": str(icon or target),
        "ZN_DESC": description,
    })
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
            env=env, capture_output=True, text=True, timeout=45, creationflags=CREATE_NO_WINDOW,
        )
        if completed.returncode != 0:
            log(f"创建快捷方式失败 {link_path}: {completed.stderr.strip()[:300]}")
            return False
        log(f"已创建快捷方式 {link_path}")
        return link_path.exists()
    except Exception as error:  # PowerShell 被策略禁用等情况
        log(f"创建快捷方式异常 {link_path}: {error}")
        return False


def shortcut_paths() -> list[Path]:
    paths = []
    try:
        paths.append(known_folder(FOLDERID_DESKTOP) / f"{DISPLAY_NAME}.lnk")
    except Exception as error:
        log(f"读取桌面目录失败: {error}")
        fallback = Path.home() / "Desktop" / f"{DISPLAY_NAME}.lnk"
        paths.append(fallback)
    try:
        paths.append(known_folder(FOLDERID_PROGRAMS) / f"{DISPLAY_NAME}.lnk")
    except Exception as error:
        log(f"读取开始菜单目录失败: {error}")
        paths.append(Path(os.environ.get("APPDATA", str(Path.home()))) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / f"{DISPLAY_NAME}.lnk")
    return paths


# --------------------------------------------------------------------------
# 注册表
# --------------------------------------------------------------------------
def write_registry() -> None:
    import winreg

    exe = installed_exe()
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_ROOT) as key:
            values = {
                "DisplayName": f"{DISPLAY_NAME}（农业数据工作台）",
                "DisplayVersion": VERSION,
                "Publisher": PUBLISHER,
                "InstallLocation": str(install_dir()),
                "DisplayIcon": str(exe),
                "UninstallString": f'"{exe}" --uninstall',
                "QuietUninstallString": f'"{exe}" --uninstall --silent',
                "InstallDate": time.strftime("%Y%m%d"),
                "NoModify": 1,
                "NoRepair": 1,
            }
            for name, value in values.items():
                kind = winreg.REG_DWORD if isinstance(value, int) else winreg.REG_SZ
                winreg.SetValueEx(key, name, 0, kind, value)
            try:
                size = exe.stat().st_size // 1024
                winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, size)
            except OSError:
                pass
        log("已写入卸载注册表项")
    except Exception as error:
        log(f"写入注册表失败（不影响使用）: {error}")


def delete_registry() -> None:
    import winreg

    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REG_ROOT)
        log("已删除卸载注册表项")
    except FileNotFoundError:
        pass
    except Exception as error:
        log(f"删除注册表失败: {error}")


# --------------------------------------------------------------------------
# 安装状态
# --------------------------------------------------------------------------
def is_installed() -> bool:
    return installed_exe().is_file()


def installed_info() -> dict:
    try:
        return json.loads(version_file().read_text(encoding="utf-8"))
    except Exception:
        return {}


def install(run_after: bool = True) -> Path:
    target_dir = install_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    source = current_executable()
    target = installed_exe()
    log(f"开始安装: {source} -> {target}")

    if source.resolve() != target.resolve():
        # 复制自身；如果目标正被占用，先改名再替换
        if target.exists():
            try:
                backup = target.with_suffix(".old")
                if backup.exists():
                    backup.unlink()
                target.rename(backup)
            except OSError:
                pass
        shutil.copy2(source, target)

    # 覆盖安装留下的备份文件，成功后再清理
    backup = target.with_suffix(".old")
    if backup.exists():
        try:
            backup.unlink()
        except OSError:
            pass

    info = {
        "app": APP_ID,
        "displayName": DISPLAY_NAME,
        "version": VERSION,
        "installedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
        "installDir": str(target_dir),
    }
    version_file().write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")

    for link in shortcut_paths():
        create_shortcut(link, target, target_dir, "智农宝 · 农业数据工作台")
    write_registry()
    log("安装完成")
    return target


def uninstall(silent: bool = False) -> bool:
    from runtime import request_shutdown  # 延迟导入，避免循环引用

    log("开始卸载")
    request_shutdown()
    time.sleep(0.3)

    for link in shortcut_paths():
        try:
            if link.exists():
                link.unlink()
                log(f"已删除快捷方式 {link}")
        except OSError as error:
            log(f"删除快捷方式失败 {link}: {error}")

    delete_registry()

    target_dir = install_dir()
    running_from_install = current_executable().resolve().parent == target_dir
    if not target_dir.exists():
        return True

    if running_from_install:
        # 正在运行的就是要删除的 exe：写一个重试脚本，等本进程退出后再删目录
        script = Path(tempfile.gettempdir()) / "zn_uninstall_cleanup.cmd"
        try:
            cleanup_lines = [
                "@echo off",
                "for /l %%i in (1,1,12) do (",
                "  ping -n 2 127.0.0.1 >nul",
                '  rmdir /s /q "%s" 2>nul' % target_dir,
                '  if not exist "%s" exit /b 0' % target_dir,
                ")",
            ]
            script.write_bytes(os.linesep.join(cleanup_lines).encode("ascii") + os.linesep.encode("ascii"))
            subprocess.Popen(
                ["cmd.exe", "/c", str(script)],
                creationflags=CREATE_NO_WINDOW | 0x00000008,
                close_fds=True,
            )
            log("已安排退出后清理安装目录（最多重试 12 次）")
        except Exception as error:
            log(f"安排清理失败: {error}")
            return False
    else:
        try:
            shutil.rmtree(target_dir, ignore_errors=True)
            log("已删除安装目录")
        except Exception as error:
            log(f"删除安装目录失败: {error}")
            return False
    return True
