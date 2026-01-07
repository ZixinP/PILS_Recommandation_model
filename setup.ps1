# ==========================================
# FashionistAI - Setup Script (Windows)
# ==========================================

$ErrorActionPreference = "Stop"

Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     FashionistAI - Installation Setup       ║"
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ==========================================
# 1. Check Prerequisites
# ==========================================

Write-Host "🔍 Checking prerequisites..."
Write-Host ""

# Check Node.js
try {
    $nodeVersion = node -v
    Write-Host "✅ Node.js $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Node.js is not installed." -ForegroundColor Red
    Write-Host "   Please install Node.js from https://nodejs.org/"
    exit 1
}

# Check npm
try {
    $npmVersion = npm -v
    Write-Host "✅ npm v$npmVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ npm is not installed." -ForegroundColor Red
    exit 1
}

# Check Python
$pythonCmd = "python"
try {
    $pythonVersion = python --version 2>&1
    if ($pythonVersion -match "Python 3\.(10|11)") {
        Write-Host "✅ $pythonVersion" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Python 3.10 or 3.11 recommended (found: $pythonVersion)" -ForegroundColor Yellow
        Write-Host "   PyTorch often requires specific versions."
        $confirmation = Read-Host "   Continue anyway? (y/n)"
        if ($confirmation -notmatch "^[Yy]$") {
            exit 1
        }
    }
} catch {
    Write-Host "❌ Python is not installed." -ForegroundColor Red
    Write-Host "   Please install Python 3.10 from https://www.python.org/"
    exit 1
}

Write-Host ""

# ==========================================
# 2. Detect Network IP
# ==========================================

Write-Host "🌐 Detecting Network IP..."

try {
    $networkIP = (Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias *Wi-Fi*,*Ethernet* | Where-Object { $_.IPAddress -notmatch "127.0.0.1" -and $_.IPAddress -notmatch "^169\.254" } | Select-Object -First 1 -ExpandProperty IPAddress)
} catch {
    $networkIP = $null
}

if (-not $networkIP) {
    $networkIP = "192.168.1.21"
    Write-Host "⚠️  Could not detect IP, using default: $networkIP" -ForegroundColor Yellow
} else {
    Write-Host "✅ Network IP detected: $networkIP" -ForegroundColor Green
}

Write-Host ""

# ==========================================
# 3. Create .env file
# ==========================================

Write-Host "📝 Configuring environment..."

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "✅ .env file created" -ForegroundColor Green
}

# Update NETWORK_IP in .env
$envContent = Get-Content ".env"
$newEnvContent = @()
$ipUpdated = $false

foreach ($line in $envContent) {
    if ($line -match "^NETWORK_IP=") {
        $newEnvContent += "NETWORK_IP=$networkIP"
        $ipUpdated = $true
    } elseif ($line -match "^# NETWORK_IP=") {
        $newEnvContent += "NETWORK_IP=$networkIP"
        $ipUpdated = $true
    } else {
        $newEnvContent += $line
    }
}

if (-not $ipUpdated) {
    $newEnvContent += "NETWORK_IP=$networkIP"
}

$newEnvContent | Set-Content ".env"
Write-Host "✅ NETWORK_IP configured: $networkIP" -ForegroundColor Green

Write-Host ""

# ==========================================
# 4. Install Backend Dependencies
# ==========================================

Write-Host "📦 Installing Backend Dependencies..."
npm install
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Backend dependencies installed" -ForegroundColor Green
} else {
    Write-Host "❌ Error installing backend dependencies" -ForegroundColor Red
    exit 1
}

Write-Host ""

# ==========================================
# 5. Install Frontend Dependencies
# ==========================================

Write-Host "📦 Installing Frontend Dependencies..."
Push-Location frontend
npm install
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Frontend dependencies installed" -ForegroundColor Green
} else {
    Write-Host "❌ Error installing frontend dependencies" -ForegroundColor Red
    Pop-Location
    exit 1
}
Pop-Location

Write-Host ""

# ==========================================
# 6. Setup Python Microservice
# ==========================================

Write-Host "🐍 Configuring Python Microservice..."

Push-Location microservices/python

# Create virtual environment
if (-not (Test-Path "venv")) {
    Write-Host "   Creating virtual environment..."
    python -m venv venv
    Write-Host "✅ Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "⚠️  venv already exists" -ForegroundColor Yellow
}

# Install dependencies
Write-Host "   Installing Python dependencies..."
# Use the venv pip directly
& .\venv\Scripts\python.exe -m pip install --upgrade pip | Out-Null
& .\venv\Scripts\pip.exe install -r requirements.txt

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Python dependencies installed" -ForegroundColor Green
} else {
    Write-Host "❌ Error installing Python dependencies" -ForegroundColor Red
    Pop-Location
    exit 1
}

Pop-Location

Write-Host ""

# ==========================================
# 7. Create necessary directories
# ==========================================

Write-Host "📁 Creating directories..."

New-Item -ItemType Directory -Force -Path "uploads" | Out-Null
New-Item -ItemType Directory -Force -Path "logs" | Out-Null
New-Item -ItemType Directory -Force -Path "microservices/python/uploads" | Out-Null
New-Item -ItemType Directory -Force -Path "microservices/python/models" | Out-Null

Write-Host "✅ Directories created" -ForegroundColor Green
Write-Host ""

# ==========================================
# 8. Check YOLO and SMPL Models
# ==========================================

Write-Host "🤖 Checking AI Models..."

if (Test-Path "microservices/python/yolov8n-pose.pt") {
    Write-Host "✅ YOLO model found" -ForegroundColor Green
} else {
    Write-Host "⚠️  YOLO model not found" -ForegroundColor Yellow
    Write-Host "   The model will be downloaded automatically on first run."
}

if (Test-Path "microservices/python/models/SMPL_NEUTRAL.pkl") {
    Write-Host "✅ SMPL model found" -ForegroundColor Green
} else {
    Write-Host "⚠️  SMPL model (SMPL_NEUTRAL.pkl) not found" -ForegroundColor Yellow
    Write-Host "   To enable 3D body reconstruction:"
    Write-Host "   1. Download SMPL_NEUTRAL.pkl (requires license registration)"
    Write-Host "   2. Place it in: microservices/python/models/"
}

Write-Host ""

# ==========================================
# Final Instructions
# ==========================================

Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║         ✅ Installation Complete!            ║"
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "To start the application:" -ForegroundColor Green
Write-Host "   .\run.ps1"
Write-Host ""
Write-Host "Access URLs:" -ForegroundColor Green
Write-Host "   • Backend  : http://localhost:8000"
Write-Host "   • Frontend : http://localhost:3000"
Write-Host "   • Python   : http://localhost:5001"
Write-Host ""
Write-Host "QR Code (mobile):" -ForegroundColor Green
Write-Host "   • http://$($networkIP):8000"
Write-Host ""
