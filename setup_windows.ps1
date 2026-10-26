# ==============================================================================
# Printer InkSaver / InkYard - Windows 10/11 Classroom PC Auto-Configuration Script
# Run in Administrator PowerShell to prepare an idle classroom PC
# ==============================================================================

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "  [InkYard] Configuring Classroom PC for 24/7 Server" -ForegroundColor Green
Write-Host "=================================================================" -ForegroundColor Cyan

# 1. Disable Windows Sleep/Standby/Hibernation when plugged in
Write-Host "`n[1/4] Disabling automatic PC sleep / standby / hibernation..." -ForegroundColor Yellow
try {
    powercfg /change standby-timeout-ac 0
    powercfg /change hibernate-timeout-ac 0
    powercfg /change monitor-timeout-ac 15
    Write-Host "  [OK] PC sleep & hibernation disabled (Monitor turns off after 15 min to save screen)." -ForegroundColor Green
} catch {
    Write-Host "  [WARN] Failed to configure power settings: $_" -ForegroundColor DarkYellow
}

# 2. Allow Inbound Traffic on Port 5000, 5050, 8080, 8000 in Windows Firewall
Write-Host "`n[2/4] Adding Windows Firewall Rule for Ports 5000, 5050, 8080, 8000..." -ForegroundColor Yellow
try {
    $existingRule = Get-NetFirewallRule -DisplayName "InkYard Web Portal" -ErrorAction SilentlyContinue
    if (-not $existingRule) {
        New-NetFirewallRule -DisplayName "InkYard Web Portal" `
                            -Direction Inbound `
                            -LocalPort 5000,5050,8080,8000 `
                            -Protocol TCP `
                            -Action Allow `
                            -Description "Allows students on school Wi-Fi to access InkYard" | Out-Null
        Write-Host "  [OK] Inbound firewall rule for ports 5000, 5050, 8080, 8000 created." -ForegroundColor Green
    } else {
        Set-NetFirewallRule -DisplayName "InkYard Web Portal" -LocalPort 5000,5050,8080,8000 | Out-Null
        Write-Host "  [OK] Firewall rule updated for ports 5000, 5050, 8080, 8000." -ForegroundColor Green
    }

} catch {
    Write-Host "  [WARN] Firewall rule setup requires Administrator privileges: $_" -ForegroundColor DarkYellow
}

# 3. Check / Assist Python 3 Environment
Write-Host "`n[3/4] Checking Python 3 Environment..." -ForegroundColor Yellow
$py = Get-Command python, py -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $py) {
    $localPy = Get-ChildItem -Path "$env:LOCALAPPDATA\Programs\Python" -Filter "python.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($localPy) {
        $py = $localPy
    }
}
if ($py) {
    $pyPath = if ($py.Source) { $py.Source } else { $py.FullName }
    Write-Host "  [OK] Python detected: $pyPath" -ForegroundColor Green
} else {
    Write-Host "  [NOTICE] Python 3 was not detected in PATH." -ForegroundColor DarkYellow
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        Write-Host "  [*] Attempting to install Python 3.11 via winget..." -ForegroundColor Yellow
        try {
            winget install --id Python.Python.3.11 -e --silent --accept-package-agreements --accept-source-agreements
            Write-Host "  [OK] Python 3.11 installed via winget." -ForegroundColor Green
        } catch {
            Write-Host "  [NOTICE] Please run install_python.bat to complete Python setup." -ForegroundColor Yellow
        }
    } else {
        Write-Host "  [NOTICE] Please run install_python.bat to install Python automatically." -ForegroundColor Yellow
    }
}

# 4. Create Desktop & Startup Shortcut
Write-Host "`n[4/4] Setting up 1-click startup..." -ForegroundColor Yellow
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$batPath = Join-Path $scriptDir "run_server_windows.bat"

if (Test-Path $batPath) {
    $wsh = New-Object -ComObject WScript.Shell
    $desktopPath = [System.Environment]::GetFolderPath('Desktop')
    $shortcut = $wsh.CreateShortcut((Join-Path $desktopPath "Start InkYard.lnk"))
    $shortcut.TargetPath = $batPath
    $shortcut.WorkingDirectory = $scriptDir
    $shortcut.Save()
    Write-Host "  [OK] Shortcut created on Desktop: 'Start InkYard.lnk'" -ForegroundColor Green
}

# 5. Display Network Address
$ipObj = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { 
    $_.IPAddress -notmatch '^127\.' -and 
    $_.IPAddress -notmatch '^169\.254\.' -and 
    $_.IPAddress -notmatch '^198\.18\.' -and 
    $_.IPAddress -notmatch '^0\.' 
} | Select-Object -First 1

$ip = if ($ipObj) { $ipObj.IPAddress } else { $null }

Write-Host "`n=================================================================" -ForegroundColor Cyan
Write-Host "  CONFIGURATION COMPLETE!" -ForegroundColor Green
if ($ip) {
    Write-Host "  Classroom Portal URL: http://${ip}:5000" -ForegroundColor White -BackgroundColor DarkGreen
} else {
    Write-Host "  Port 5000 is open. Check 'ipconfig' for your IP address." -ForegroundColor White
}
Write-Host "=================================================================" -ForegroundColor Cyan
