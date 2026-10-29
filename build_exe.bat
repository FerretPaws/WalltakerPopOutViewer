@echo off
setlocal
cd /d "%~dp0"

echo Installing/updating build requirements...
python -m pip install --upgrade pyinstaller pyqt5 pillow requests pygame-ce websocket-client av
if errorlevel 1 goto :fail

echo Building WalltakerPopOutViewer.exe...
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name WalltakerPopOutViewer ^
    --icon "images\icon.ico" ^
    --add-data "images;images" ^
    --add-data "sounds;sounds" ^
    main.py
if errorlevel 1 goto :fail

echo.
echo Done: dist\WalltakerPopOutViewer.exe
echo (Settings and downloads are stored in the folder the exe is launched from.)
pause
exit /b 0

:fail
echo.
echo Build failed.
pause
exit /b 1
