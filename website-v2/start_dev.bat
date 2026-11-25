@echo off
chcp 65001 >nul
setlocal
rem 源码方式启动（需要本机已安装 Python 3.9+，不需要任何第三方库）
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo 未找到 python，请先安装 Python 3.9+ 并加入 PATH。
  pause
  exit /b 1
)
echo 正在以源码方式启动智农宝 ...
python "desktop\zhinongbao.py" --no-prompt
if errorlevel 1 pause
endlocal
