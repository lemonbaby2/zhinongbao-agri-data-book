import subprocess, time, ctypes
from ctypes import wintypes
from PIL import ImageGrab
exe = r'E:/现代信息/智农宝阅读器/dist/智农宝农业数据全书_v3.1.0.exe'
p = subprocess.Popen([exe])
time.sleep(13)
u = ctypes.windll.user32
PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
wins = []
def cb(h, lp):
    n = u.GetWindowTextLengthW(h)
    if n > 0 and u.IsWindowVisible(h):
        b = ctypes.create_unicode_buffer(n + 1); u.GetWindowTextW(h, b, n + 1)
        c = ctypes.create_unicode_buffer(256); u.GetClassNameW(h, c, 256)
        r = wintypes.RECT(); u.GetWindowRect(h, ctypes.byref(r))
        wins.append((h, b.value, c.value, (r.right - r.left, r.bottom - r.top)))
    return True
u.EnumWindows(PROC(cb), 0)
print('proc alive:', p.poll() is None)
for w in wins:
    print(' win:', repr(w[1][:44]), '|', w[2], '| size', w[3])
cand = [w for w in wins if '智农宝' in w[1] and w[2] != 'CabinetWClass' and w[3][0] > 300]
print('candidates:', [(w[1], w[3]) for w in cand])
if cand:
    h = cand[0][0]
    u.ShowWindow(h, 9); u.SetForegroundWindow(h); time.sleep(1.5)
    ImageGrab.grab().save('preview_diag.png')
    print('shot saved')
else:
    print('NO OUR WINDOW FOUND')
p.terminate()
