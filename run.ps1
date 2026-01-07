# ==========================================
# FashionistAI - Run Script (Windows)
# ==========================================

$ErrorActionPreference = "Stop"

# Get script directory
$SCRIPT_DIR = $PSScriptRoot
Set-Location $SCRIPT_DIR

Write-Host ""

Write-Host "       FashionistAI - Starting            "

Write-Host ""

# ==========================================
# Stop existing services
# ==========================================

Write-Host " Stopping existing services..." -ForegroundColor Yellow

# Function to kill process by port
function Kill-Port($port) {
    $process = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($process) {
        $pid_val = $process.OwningProcess
        Stop-Process -Id $pid_val -Force -ErrorAction SilentlyContinue
    }
}

Kill-Port 3000
Kill-Port 5001
Kill-Port 8000

# Kill by name if any remain
Get-Process | Where-Object {$_.ProcessName -match "node|python|uvicorn"} | ForEach-Object {
    if ($_.CommandLine -match "server.ts|main:app|react-scripts") {
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
}

Start-Sleep -Seconds 1
Write-Host " Services stopped" -ForegroundColor Green
Write-Host ""

# ==========================================
# Create log directory
# ==========================================

New-Item -ItemType Directory -Force -Path "logs" | Out-Null

# ==========================================
# Start Python Microservice
# ==========================================

Write-Host " Starting Python Microservice (YOLO)..." -ForegroundColor Cyan
Push-Location microservices/python

if (-not (Test-Path "venv")) {
    Write-Host " Python virtual environment not found" -ForegroundColor Red
    Write-Host "   Please run .\setup.ps1 first"
    exit 1
}

# Start Python service
$pythonProcess = Start-Process -FilePath "venv\Scripts\python.exe" `
    -ArgumentList "-m uvicorn main:app --host 0.0.0.0 --port 5001 --log-level info" `
    -RedirectStandardOutput "$SCRIPT_DIR\logs\python_out.log" `
    -RedirectStandardError "$SCRIPT_DIR\logs\python_err.log" `
    -NoNewWindow -PassThru

Start-Sleep -Seconds 2

if (-not $pythonProcess.HasExited) {
    Write-Host "   Started (PID: $($pythonProcess.Id)) on http://localhost:5001" -ForegroundColor Green
} else {
    Write-Host "   Failed to start Python microservice" -ForegroundColor Red
    Write-Host "   Check logs: logs\python.log"
    exit 1
}

Pop-Location
Write-Host ""

# ==========================================
# Start TypeScript Backend
# ==========================================

Write-Host "Starting TypeScript Backend..." -ForegroundColor Cyan

# Check mode
$backendArgs = @("node_modules\.bin\tsx.cmd", "watch", "src/server.ts")
if ($args[0] -eq "prod") {
    if (-not (Test-Path "dist")) {
        Write-Host "   Compiling TypeScript..."
        npm run build
    }
    $backendArgs = @("dist\server.js")
    $nodeCmd = "node"
} else {
    $nodeCmd = "cmd"
    $backendArgs = @("/c", "npx", "tsx", "watch", "src/server.ts")
}

$backendProcess = Start-Process -FilePath $nodeCmd `
    -ArgumentList $backendArgs `
    -RedirectStandardOutput "$SCRIPT_DIR\logs\backend_out.log" `
    -RedirectStandardError "$SCRIPT_DIR\logs\backend_err.log" `
    -NoNewWindow -PassThru

Start-Sleep -Seconds 3

if (-not $backendProcess.HasExited) {
    Write-Host "  Started (PID: $($backendProcess.Id)) on http://localhost:8000" -ForegroundColor Green
} else {
    Write-Host "  Failed to start Backend" -ForegroundColor Red
    Write-Host "   Check logs: logs\backend.log"
    Stop-Process -Id $pythonProcess.Id -Force -ErrorAction SilentlyContinue
    exit 1
}

Write-Host ""

# ==========================================
# Start React Frontend
# ==========================================

Write-Host "Starting React Frontend..." -ForegroundColor Cyan
Push-Location frontend

# Start React
# We use npm start. Since we can't easily suppress the browser opening or keep it cleanly in background without a window in PS without hiding it completely.
# We'll use Start-Process with cmd /c npm start
# We also need to set HTTPS=false.

$frontendProcess = Start-Process -FilePath "cmd" `
    -ArgumentList "/c npm start" `
    -RedirectStandardOutput "..\logs\frontend_out.log" `
    -RedirectStandardError "..\logs\frontend_err.log" `
    -NoNewWindow -PassThru

if (-not $frontendProcess.HasExited) {
    Write-Host "   Started (PID: $($frontendProcess.Id)) on http://localhost:3000" -ForegroundColor Green
} else {
    Write-Host "   Failed to start Frontend" -ForegroundColor Red
    Stop-Process -Id $pythonProcess.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
    exit 1
}

Pop-Location
Write-Host ""

# ==========================================
# Wait for services
# ==========================================

Write-Host "Waiting for services to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# ==========================================
# Health Checks
# ==========================================

Write-Host ""
Write-Host " Checking services health..." -ForegroundColor Cyan

function Check-Health($url, $name, $maxAttempts=5) {
    for ($i=1; $i -le $maxAttempts; $i++) {
        try {
            $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
            if ($response.StatusCode -eq 200) {
                Write-Host " $($name): OK" -ForegroundColor Green
                return $true
            }
        } catch {
            Write-Host "   $($name): Attempt $i/$maxAttempts failed" -ForegroundColor Yellow
            Start-Sleep -Seconds 1
        }
    }
    Write-Host "   $($name): UNAVAILABLE after $maxAttempts attempts" -ForegroundColor Red
    return $false
}

Check-Health "http://127.0.0.1:5001/health" "Python Microservice" | Out-Null
Check-Health "http://127.0.0.1:8000/health" "TypeScript Backend" | Out-Null
# Frontend might take longer
Check-Health "http://127.0.0.1:3000" "React Frontend" -maxAttempts 8 | Out-Null

Write-Host ""

# ==========================================
# Get Network IP
# ==========================================

$networkIP = (Get-Content ".env" | Select-String "^NETWORK_IP=(.*)$" ).Matches.Groups[1].Value
if (-not $networkIP) {
   $networkIP = "localhost"
}

# ==========================================
# Summary
# ==========================================


Write-Host "         FashionistAI Started!            "

Write-Host ""
Write-Host "PC Access :" -ForegroundColor Green
Write-Host "   http://localhost:3000"
Write-Host ""
Write-Host "Mobile Access (QR Code) :" -ForegroundColor Green
Write-Host "   http://$($networkIP):8000"
Write-Host ""
Write-Host "Services :" -ForegroundColor Green
Write-Host "   • Backend TypeScript : http://localhost:8000"
Write-Host "   • Python Microservice: http://localhost:5001"
Write-Host "   • Frontend React     : http://localhost:3000"
Write-Host ""
Write-Host "Logs :" -ForegroundColor Yellow
Write-Host "   Get-Content logs\backend_out.log -Wait"
Write-Host "   Get-Content logs\python_out.log -Wait"
Write-Host "   Get-Content logs\frontend_out.log -Wait"
Write-Host ""
Write-Host "To Stop :" -ForegroundColor Yellow
Write-Host "   Press Ctrl+C in this window"
Write-Host ""

# Loop to keep script running and handle Ctrl+C cleanup
try {
    while ($true) {
        Start-Sleep -Seconds 1
        if ($pythonProcess.HasExited -or $backendProcess.HasExited) {
             Write-Host "One or more services stopped unexpectedly." -ForegroundColor Red
             break
        }
    }
} finally {
    Write-Host ""
    Write-Host "Stopping services..." -ForegroundColor Yellow
    Stop-Process -Id $pythonProcess.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $frontendProcess.Id -Force -ErrorAction SilentlyContinue
    
    # Also cleanup children if possible (npm starts node, etc)
    Kill-Port 3000
    Kill-Port 5001
    Kill-Port 8000
    
    Write-Host "Stopped." -ForegroundColor Green
}
