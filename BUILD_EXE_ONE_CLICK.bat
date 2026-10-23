@echo off
REM ============================================================
REM  Facebook Pages Manager - ONE CLICK Windows .exe builder
REM  Owner: Muhammad Aamir
REM  Just double-click this file. It will:
REM    1) Install Python automatically if it is missing
REM    2) Install the app libraries
REM    3) Build ONE single file: dist\FacebookPagesManager.exe
REM  The final .exe needs NOTHING installed - send it to anyone,
REM  they double-click and it runs.
REM ============================================================
setlocal
cd /d "%~dp0"
echo.
echo  Facebook Pages Manager - .exe builder
echo  --------------------------------------

where python >nul 2>nul
if %ERRORLEVEL%==0 goto have_python

echo  Python not found - installing it for you (one time only)...
where winget >nul 2>nul
if %ERRORLEVEL%==0 (
  winget install -e --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
  set "PATH=%LOCALAPPDATA%\Programs\Python\Python312\;%LOCALAPPDATA%\Programs\Python\Python312\Scripts\;%PATH%"
  goto have_python
)
echo  Downloading Python installer...
powershell -Command "Invoke-WebRequest -Uri https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe -OutFile %TEMP%\python-setup.exe"
"%TEMP%\python-setup.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312\;%LOCALAPPDATA%\Programs\Python\Python312\Scripts\;%PATH%"

:have_python
python --version
echo  Installing libraries (one time)...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
if %ERRORLEVEL% NEQ 0 goto fail

echo  Building single-file exe (few minutes)...
python -m PyInstaller --noconfirm FacebookPagesManager-OneFile.spec
if %ERRORLEVEL% NEQ 0 goto fail

echo.
echo  ================================================
echo   DONE! Your software is here:
echo   %CD%\dist\FacebookPagesManager.exe
echo   This ONE file is the whole software.
echo   No Python or anything else needed to run it.
echo  ================================================
explorer "%CD%\dist"
pause
exit /b 0

:fail
echo.
echo  Something failed. Take a screenshot of this window and send it to the developer.
pause
exit /b 1
