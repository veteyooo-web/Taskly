@echo off
rem ============================================================
rem  Taskly launcher - double-click to start the site.
rem  All interactive logic (Russian prompts, test data, logins,
rem  passwords) lives in launcher.py.
rem
rem  Cyrillic text is intentionally NOT used here: cmd.exe breaks
rem  batch parsing when chcp 65001 is applied mid-file.
rem ============================================================
setlocal
cd /d "%~dp0"
title Taskly

set "PYCMD="
for %%V in (3.13 3.12 3.11 3.10 3.14) do (
    if not defined PYCMD (
        py -%%V -c "import sys" >nul 2>nul && set "PYCMD=py -%%V"
    )
)
if not defined PYCMD (
    python -c "import sys; sys.exit(0 if (3,10)<=sys.version_info[:2]<=(3,14) else 1)" >nul 2>nul && set "PYCMD=python"
)

if defined PYCMD goto :run

echo.
echo  [ERROR] Python 3.10 - 3.14 was not found on this computer.
echo.
echo  Install Python 3.12 from:
echo      https://www.python.org/downloads/
echo  and tick "Add Python to PATH" during installation.
echo  Then run this file again.
echo.
pause
exit /b 1

:run
%PYCMD% launcher.py

echo.
pause
