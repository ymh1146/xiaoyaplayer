@echo off
chcp 65001
echo 正在准备构建环境...

REM 检查并安装必要依赖
pip install -r requirements.txt
pip install nuitka

echo 清理旧的构建文件...
if exist "dist\XiaoyaPlayer.exe" del "dist\XiaoyaPlayer.exe"
if exist "dist\小雅播放器.exe" del "dist\小雅播放器.exe"

echo 开始编译...
nuitka --standalone --onefile ^
    --enable-plugin=pyqt6 ^
    --windows-console-mode=disable ^
    --windows-icon-from-ico=gui/logo.ico ^
    --include-data-dir=gui=gui ^
    --include-package=vlc ^
    --include-package=webdav4 ^
    --include-package=httpx ^
    --output-dir=dist ^
    --output-filename="XiaoyaPlayer.exe" ^
    main.py

if errorlevel 1 (
    echo.
    echo [错误] 编译失败，请检查上方的报错信息。
    pause
    exit /b
)

echo 正在重命名文件...
cd dist
ren XiaoyaPlayer.exe 小雅播放器.exe
cd ..

echo.
echo 编译完成！文件位于 dist 目录: 小雅播放器.exe
pause