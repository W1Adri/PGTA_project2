@echo off
:: ASTERIX Decoder — Windows launcher
:: Checks for WebView2 Runtime and installs it if missing, then launches the app.

echo Checking WebView2 Runtime...

:: Check if WebView2 is already installed (registry key)
reg query "HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" >nul 2>&1
if %errorlevel% == 0 (
    echo WebView2 Runtime found. Launching ASTERIX Decoder...
    goto launch
)

reg query "HKCU\Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" >nul 2>&1
if %errorlevel% == 0 (
    echo WebView2 Runtime found. Launching ASTERIX Decoder...
    goto launch
)

:: Not found — download and install silently
echo WebView2 Runtime not found. Downloading installer...
curl -L -o "%TEMP%\MicrosoftEdgeWebview2Setup.exe" "https://go.microsoft.com/fwlink/p/?LinkId=2124703"

echo Installing WebView2 Runtime (this may take a moment)...
"%TEMP%\MicrosoftEdgeWebview2Setup.exe" /silent /install

echo Done. Launching ASTERIX Decoder...

:launch
:: Replace the filename below with the actual .exe name after build
start "" "%~dp0asterix_decoder_windows_DATE.exe"
