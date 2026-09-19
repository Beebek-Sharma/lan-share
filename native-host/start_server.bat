@echo off
REM Wrapper that invokes the real native host (Python) which implements
REM Chrome's native messaging protocol (length-prefixed JSON).
SET "PYTHON_EXE=C:\Users\bibek\AppData\Local\Programs\Python\Python314\python.exe"
SET "SCRIPT=%~dp0lan_share_host.py"

IF NOT EXIST "%PYTHON_EXE%" (
  REM Fallback to python on PATH
  SET "PYTHON_EXE=python"
)

"%PYTHON_EXE%" "%SCRIPT%"
exit /b %ERRORLEVEL%
