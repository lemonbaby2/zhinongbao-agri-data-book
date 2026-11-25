# -*- coding: utf-8 -*-
"""打包后自动化验收：启动 exe → 检测异常对话框 → 检测主窗口 → 截图。"""
import subprocess, time, ctypes, sys
from ctypes import wintypes
from PIL import ImageGrab

EXE = r"E:/现代信息/智农宝阅读器/dist/智农宝农业数据全书_v8.0.0.exe"
u = ctypes.windll.user32
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def list_windows():
    wins = []
    def cb(hwnd, lp):
        n = u.GetWindowTextLengthW(hwnd)
        if n > 0 and u.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(n + 1)
            u.GetWindowTextW(hwnd, buf, n + 1)
            cls = ctypes.create_unicode_buffer(256)
            u.GetClassNameW(hwnd, cls, 256)
            wins.append((hwnd, buf.value, cls.value))
        return True
    u.EnumWindows(WNDENUMPROC(cb), 0)
    return wins


def dialog_texts(hwnd):
    texts = []
    def cb(child, lp):
        n = u.GetWindowTextLengthW(child)
        if n > 0:
            buf = ctypes.create_unicode_buffer(n + 1)
            u.GetWindowTextW(child, buf, n + 1)
            if buf.value.strip(): texts.append(buf.value)
        return True
    u.EnumChildWindows(hwnd, WNDENUMPROC(cb), 0)
    return texts


def main():
    p = subprocess.Popen([EXE], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(14)
    wins = list_windows()
    errs = [(h, dialog_texts(h)) for h, t, c in wins if "exception" in t.lower() or "error" in t.lower()]
    # 严格匹配：必须是 Qt 窗口 + 版本标题，避免误把资源管理器当主窗口
    mainwins = [(h, t) for h, t, c in wins
                if "农业数据全书" in t and ("v4." in t or "v5." in t or "v6." in t or "v7." in t or "v8." in t) and c.startswith("Qt")]

    ok = True
    if errs:
        ok = False
        print("FAIL: 异常对话框:")
        for h, txt in errs:
            print("  ", " | ".join(txt)[:400])
            u.PostMessageW(h, 0x0010, 0, 0)  # WM_CLOSE
    if not mainwins:
        ok = False
        print("FAIL: 未找到智农宝主窗口")
    else:
        h = mainwins[0][0]
        u.ShowWindow(h, 9)
        u.SetForegroundWindow(h)
        time.sleep(2)
        ImageGrab.grab().save(r"E:/现代信息/智农宝阅读器/preview_exe_final.png")
        print("OK: 主窗口 =", mainwins[0][1])
        print("OK: 截图已保存 preview_exe_final.png")

    if p.poll() is not None:
        out, err = p.communicate()
        print("进程已退出 code", p.returncode, "STDERR:", err.decode("utf-8", "ignore")[:800])
    p.terminate()
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
