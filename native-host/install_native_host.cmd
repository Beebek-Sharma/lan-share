@echo off
setlocal
set "JSON_PATH=%~dp0lan_share_host_windows.json"

echo Registering LAN Share Native Messaging Host...
echo Manifest path: %JSON_PATH%

reg add "HKCU\Software\Google\Chrome\NativeMessagingHosts\lan_share_host" /ve /t REG_SZ /d "%JSON_PATH%" /f
reg add "HKCU\Software\Microsoft\Edge\NativeMessagingHosts\lan_share_host" /ve /t REG_SZ /d "%JSON_PATH%" /f
reg add "HKCU\Software\BraveSoftware\Brave\NativeMessagingHosts\lan_share_host" /ve /t REG_SZ /d "%JSON_PATH%" /f
reg add "HKCU\Software\Chromium\NativeMessagingHosts\lan_share_host" /ve /t REG_SZ /d "%JSON_PATH%" /f

echo.
echo [OK] Registered successfully for Chrome, Edge, Brave, and Chromium!
echo NOTE: Ensure allowed_origins in lan_share_host_windows.json includes your extension ID.
pause
