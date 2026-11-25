# -*- coding: utf-8 -*-
"""智农宝农业数据全书 — 用户态安装器（双击 exe 即安装，无管理权限）。
支持：安装（桌面快捷方式+开始菜单）、便携运行、卸载。"""
import os, sys, shutil, subprocess, tempfile, ctypes
from pathlib import Path

APP_NAME = "智农宝农业数据全书"
VERSION = "4.0.0"


def is_installed():
    key = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\ZhinongbaoBook"
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key)
        p, _ = winreg.QueryValueEx(k, "InstallLocation")
        winreg.CloseKey(k)
        return Path(p) if Path(p).exists() else None
    except Exception:
        return None


def desktop_path():
    # SHGetKnownFolderPath 处理 OneDrive 重定向
    try:
        from ctypes import wintypes
        class GUID(ctypes.Structure):
            _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort),
                        ("Data3", ctypes.c_ushort), ("Data4", ctypes.c_ubyte * 8)]
        FOLDERID_Desktop = GUID(0xB4BFCC3A, 0xDB2C, 0x424C, bytes.fromhex("B0297FE99A87"))
        path_ptr = ctypes.c_wchar_p()
        ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(FOLDERID_Desktop), 0, None, ctypes.byref(path_ptr))
        return Path(path_ptr.value)
    except Exception:
        return Path.home() / "Desktop"


def make_shortcut(target, link, workdir, icon=None):
    ps = f'''
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut("{link}")
$s.TargetPath = "{target}"
$s.WorkingDirectory = "{workdir}"
$s.WindowStyle = 1
'''
    if icon:
        ps += f'$s.IconLocation = "{icon},0"\n'
    ps += "$s.Save()\n"
    with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8") as f:
        f.write(ps); tmp = f.name
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", tmp],
                   capture_output=True, timeout=30)
    os.unlink(tmp)


def register_uninstall(install_dir, exe_path):
    try:
        import winreg
        key = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\ZhinongbaoBook"
        k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key)
        winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, f"{APP_NAME} v{VERSION}")
        winreg.SetValueEx(k, "DisplayVersion", 0, winreg.REG_SZ, VERSION)
        winreg.SetValueEx(k, "Publisher", 0, winreg.REG_SZ, "智农宝")
        winreg.SetValueEx(k, "InstallLocation", 0, winreg.REG_SZ, str(install_dir))
        winreg.SetValueEx(k, "UninstallString", 0, winreg.REG_SZ, f'"{exe_path}" --uninstall')
        winreg.SetValueEx(k, "DisplayIcon", 0, winreg.REG_SZ, exe_path)
        winreg.CloseKey(k)
    except Exception as e:
        print("register failed:", e)


def unregister():
    try:
        import winreg
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                         r"Software\Microsoft\Windows\CurrentVersion\Uninstall\ZhinongbaoBook")
    except Exception:
        pass


def do_uninstall():
    inst = is_installed()
    print("卸载：", inst)
    if inst:
        # 删除快捷方式
        for base in [desktop_path(), Path.home() / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs"]:
            for name in [f"{APP_NAME}.lnk"]:
                p = base / name
                if p.exists():
                    try: p.unlink()
                    except Exception: pass
        unregister()
        # 用延时 cmd 删除安装目录（exe 自身可能还在运行）
        cmd = f'@echo off\nping 127.0.0.1 -n 3 >nul\nrmdir /S /Q "{inst}"'
        with tempfile.NamedTemporaryFile("w", suffix=".cmd", delete=False, encoding="utf-8") as f:
            f.write(cmd); tmp = f.name
        subprocess.Popen(["cmd", "/c", tmp], creationflags=subprocess.CREATE_NO_WINDOW)
    print("卸载完成，可关闭此窗口。")


def do_install():
    src_exe = Path(sys.argv[0]).resolve()
    inst = Path.home() / "AppData/Local/Programs" / APP_NAME
    inst.mkdir(parents=True, exist_ok=True)
    # 复制自身到安装目录
    target = inst / f"{APP_NAME}.exe"
    if src_exe.resolve() != target.resolve():
        shutil.copy2(src_exe, target)
    # 快捷方式
    desk = desktop_path() / f"{APP_NAME}.lnk"
    make_shortcut(str(target), str(desk), str(inst), str(target))
    start = Path.home() / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs"
    start.mkdir(parents=True, exist_ok=True)
    make_shortcut(str(target), str(start / f"{APP_NAME}.lnk"), str(inst), str(target))
    register_uninstall(inst, str(target))
    print(f"安装完成：{inst}")
    print(f"桌面快捷方式：{desk}")
    # 启动
    subprocess.Popen([str(target)], cwd=str(inst))


def main():
    if "--uninstall" in sys.argv:
        do_uninstall()
        return
    if "--install" in sys.argv:
        do_install()
        return
    # 默认：双击即直接打开书（像小说软件一样），安装仅为可选能力
    from app.main import main as reader_main
    reader_main()


if __name__ == "__main__":
    main()
