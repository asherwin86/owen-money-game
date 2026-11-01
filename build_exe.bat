@echo off
cd /d "%~dp0"
python -m pip install --upgrade pyinstaller ursina
python -m PyInstaller --noconfirm --clean --onefile --noconsole --name MoneyTycoon3D ^
  --collect-all ursina --collect-all panda3d --collect-all panda3d_gltf --collect-all panda3d_simplepbr ^
  --add-data "%~dp0data;data" main.py
echo.
echo Built: dist\MoneyTycoon3D.exe
pause
