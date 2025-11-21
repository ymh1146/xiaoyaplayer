@echo off
echo 使用 Nuitka 编译小雅播放器...
echo.

nuitka --standalone ^
    --onefile ^
    --windows-disable-console ^
    --enable-plugin=pyqt6 ^
    --include-package=PyQt6 ^
    --include-package=vlc ^
    --include-package=webdav4 ^
    --include-package=httpx ^
    --output-dir=dist ^
    --output-filename=小雅播放器.exe ^
    main.py

echo.
echo 编译完成！exe 位置: dist\小雅播放器.exe
pause
