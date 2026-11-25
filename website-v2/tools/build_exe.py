"""一键打包 exe 并重命名为中文文件名。

用法：
    python tools/build_exe.py            # 正常打包
    python tools/build_exe.py --console  # 保留控制台窗口，便于排错

产物：dist/智农宝_安装程序_v2.0.0.exe
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESKTOP = ROOT / "desktop"
DIST = ROOT / "dist"
VERSION = "2.2.0"
FINAL_NAME = f"智农宝_安装程序_v{VERSION}.exe"


def run(command: list[str], cwd: Path, env=None) -> None:
    print("→", " ".join(command))
    completed = subprocess.run(command, cwd=str(cwd), env=env)
    if completed.returncode != 0:
        raise SystemExit(f"命令失败（{completed.returncode}）：{' '.join(command)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--console", action="store_true", help="打包带控制台的调试版本")
    args = parser.parse_args()

    if not (ROOT / "site" / "index.html").is_file():
        raise SystemExit("缺少 site/index.html，请先准备站点文件")

    # 1. 核心数据包（保证 exe 内的数据与 site/data 同步）
    run([sys.executable, str(ROOT / "tools" / "build_core_data.py")], ROOT)

    # 2. 图标
    icon = DESKTOP / "assets" / "zhinongbao.ico"
    if not icon.is_file():
        run([sys.executable, str(ROOT / "tools" / "make_icon.py")], ROOT)

    # 3. PyInstaller
    spec = DESKTOP / "zhinongbao.spec"
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", str(spec)]
    env = dict(os.environ)
    env["ZN_CONSOLE"] = "1" if args.console else "0"
    run(command, DESKTOP, env=env)

    built = DESKTOP / "dist" / "ZhiNongBao.exe"
    if not built.is_file():
        raise SystemExit(f"未找到打包产物：{built}")

    DIST.mkdir(parents=True, exist_ok=True)
    target = DIST / (FINAL_NAME if not args.console else "智农宝_调试版.exe")
    shutil.copy2(built, target)
    size = target.stat().st_size / (1024 * 1024)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n✅ 打包完成 {stamp}\n   {target}\n   体积 {size:.1f} MB")


if __name__ == "__main__":
    main()
