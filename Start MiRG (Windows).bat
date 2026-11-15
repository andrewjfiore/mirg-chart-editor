@echo off
rem Double-click to start MiRG Chart Editor.
rem The first start downloads Python and the parts it needs (about 2 GB); later starts take a few seconds.
cd /d "%~dp0"
set "UV=uv"
where uv >nul 2>nul && goto haveuv
set "UV=%~dp0.tools\uv.exe"
if exist "%UV%" goto haveuv
set "UV=%~dp0.tools\bin\uv.exe"
if exist "%UV%" goto haveuv
echo Getting uv, the Python installer...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$env:UV_INSTALL_DIR='%~dp0.tools'; $env:UV_NO_MODIFY_PATH='1'; irm https://astral.sh/uv/install.ps1 | iex" || goto fail
set "UV=%~dp0.tools\uv.exe"
if not exist "%UV%" set "UV=%~dp0.tools\bin\uv.exe"
:haveuv
if not exist .venv\Scripts\python.exe ("%UV%" venv --python 3.12 .venv || goto fail)
echo Checking the Python packages...
rem --torch-backend auto picks the NVIDIA GPU build of PyTorch when a GPU driver is present
"%UV%" pip install --quiet --torch-backend auto --python .venv\Scripts\python.exe -r requirements.txt || "%UV%" pip install --quiet --python .venv\Scripts\python.exe -r requirements.txt || goto fail
.venv\Scripts\python.exe tools\get_models.py || goto fail
if not defined MIRG_PORT set "MIRG_PORT=8651"
if not defined MIRG_NO_BROWSER start "" cmd /c "timeout /t 4 >nul & start http://localhost:%MIRG_PORT%/"
echo MiRG Chart Editor is running at http://localhost:%MIRG_PORT%/ . Keep this window open; close it to stop.
.venv\Scripts\python.exe server.py %MIRG_PORT%
goto :eof
:fail
echo Setup stopped. The message above says why; start the app again to retry.
pause
