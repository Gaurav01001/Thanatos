# ==============================================================================
# Thanatos Universal 1-Click Installer for Windows
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\install.ps1
# Or from web:
#   irm https://raw.githubusercontent.com/Gaurav01001/Thanatos/main/install.ps1 | iex
# ==============================================================================

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "`n[*] $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "  [OK] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "  [!] $Message" -ForegroundColor Yellow
}

function Write-Failure {
    param([string]$Message)
    Write-Host "  [X] $Message" -ForegroundColor Red
}

function Refresh-Path {
    $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machinePath;$userPath"
}

Write-Host "======================================================" -ForegroundColor Magenta
Write-Host "        THANATOS AI DESKTOP COMPANION SETUP           " -ForegroundColor Magenta
Write-Host "======================================================" -ForegroundColor Magenta

# ------------------------------------------------------------------------------
# STEP 1: Pre-Flight Checks & Environment Auto-Detection
# ------------------------------------------------------------------------------
Write-Step "Step 1/5: Checking system prerequisites..."

# 1. Check OS
if (-not ($IsWindows -or ($PSVersionTable.PSVersion.Major -le 5))) {
    Write-Failure "Thanatos is tailored for Windows 10/11 64-bit."
    exit 1
}
Write-Success "Operating System: Windows detected."

# 2. Check Git
if (Get-Command git -ErrorAction SilentlyContinue) {
    $gitVersion = (git --version)
    Write-Success "$gitVersion detected."
} else {
    Write-Warn "Git is missing. Attempting automatic installation via winget..."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install --id Git.Git -e --source winget --accept-source-agreements --accept-package-agreements
        Refresh-Path
        if (Get-Command git -ErrorAction SilentlyContinue) {
            Write-Success "Git installed successfully."
        } else {
            Write-Failure "Git was installed, but please restart your terminal to refresh PATH."
            exit 1
        }
    } else {
        Write-Failure "winget not found. Please install Git manually from https://git-scm.com"
        exit 1
    }
}

# 3. Check Python (>= 3.10)
$pythonCmd = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = "py"
}

if ($pythonCmd) {
    try {
        $pyVersionRaw = & $pythonCmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
        $pyMajor = & $pythonCmd -c "import sys; print(sys.version_info.major)"
        $pyMinor = & $pythonCmd -c "import sys; print(sys.version_info.minor)"
        
        if ([int]$pyMajor -eq 3 -and [int]$pyMinor -ge 10) {
            Write-Success "Python $pyVersionRaw detected (compatible)."
        } else {
            Write-Warn "Python $pyVersionRaw found, but Thanatos requires Python 3.10+."
            $pythonCmd = $null
        }
    } catch {
        $pythonCmd = $null
    }
}

if (-not $pythonCmd) {
    Write-Warn "Compatible Python is missing. Attempting automatic installation via winget..."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install --id Python.Python.3.12 -e --source winget --accept-source-agreements --accept-package-agreements
        Refresh-Path
        if (Get-Command python -ErrorAction SilentlyContinue) {
            Write-Success "Python 3.12 installed successfully."
            $pythonCmd = "python"
        } else {
            Write-Failure "Python was installed, but please restart your terminal to reload PATH."
            exit 1
        }
    } else {
        Write-Failure "Please install Python 3.10+ from https://www.python.org/downloads/ and check 'Add to PATH'."
        exit 1
    }
}

# 4. Check Ollama
if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Write-Success "Ollama detected on system."
} else {
    Write-Warn "Ollama is missing. Attempting automatic installation via winget..."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install --id Ollama.Ollama -e --source winget --accept-source-agreements --accept-package-agreements
        Refresh-Path
        if (Get-Command ollama -ErrorAction SilentlyContinue) {
            Write-Success "Ollama installed successfully."
        } else {
            Write-Warn "Ollama installed. You may need to launch it from the Start menu if the background service is not running."
        }
    } else {
        Write-Warn "Ollama not found. You can install it from https://ollama.ai"
    }
}

# ------------------------------------------------------------------------------
# STEP 2: Workspace & Repository Provisioning
# ------------------------------------------------------------------------------
Write-Step "Step 2/5: Provisioning workspace and repository..."

# Determine installation directory:
# If running inside existing clone with src/engine, use current directory.
# Otherwise, deploy to $env:USERPROFILE\.thanatos.
$installDir = $null
if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot "src\engine\__main__.py"))) {
    $installDir = $PSScriptRoot
    Write-Success "Using current repository at $installDir"
} else {
    $installDir = Join-Path $env:USERPROFILE ".thanatos"
    if (-not (Test-Path $installDir)) {
        Write-Host "  Cloning repository to $installDir..."
        git clone https://github.com/Gaurav01001/Thanatos.git $installDir
        Write-Success "Repository cloned."
    } else {
        Write-Success "Existing installation found at $installDir. Pulling latest..."
        Push-Location $installDir
        git pull --ff-only
        Pop-Location
    }
}

# Create required persistent directories
$dataDir = Join-Path $installDir "data"
$logsDir = Join-Path $installDir "logs"
$binDir  = Join-Path $installDir "bin"

New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
New-Item -ItemType Directory -Force -Path $binDir  | Out-Null
Write-Success "Data and log directories prepared."

# ------------------------------------------------------------------------------
# STEP 3: Virtual Environment & Dependencies
# ------------------------------------------------------------------------------
Write-Step "Step 3/5: Setting up Python virtual environment & dependencies..."

$venvDir = Join-Path $installDir ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$venvPip = Join-Path $venvDir "Scripts\pip.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "  Creating isolated virtual environment..."
    & $pythonCmd -m venv $venvDir
    Write-Success "Virtual environment created at $venvDir"
} else {
    Write-Success "Virtual environment exists."
}

Write-Host "  Installing core dependencies (this may take a couple of minutes)..."
& $venvPython -m pip install --upgrade pip setuptools wheel --quiet

$reqPath = Join-Path $installDir "requirements.txt"
if (Test-Path $reqPath) {
    & $venvPip install -r $reqPath --quiet
    Write-Success "Python dependencies installed from requirements.txt."
}

# Install package in editable mode
Push-Location $installDir
& $venvPip install -e . --quiet
Pop-Location
Write-Success "Thanatos engine registered in environment."

# Playwright browser automation provisioning
$playwrightCli = Join-Path $venvDir "Scripts\playwright.exe"
if (Test-Path $playwrightCli) {
    Write-Host "  Verifying Playwright browser automation drivers..."
    & $playwrightCli install chromium --quiet
    Write-Success "Playwright Chromium browser installed."
}

# ------------------------------------------------------------------------------
# STEP 4: Local AI Models & TTS Voice Verification
# ------------------------------------------------------------------------------
Write-Step "Step 4/5: Verifying AI models & TTS voice files..."

# Ensure background Ollama service is responsive
try {
    $null = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/version" -TimeoutSec 3 -ErrorAction SilentlyContinue
    Write-Success "Ollama server is active on port 11434."
} catch {
    Write-Warn "Starting Ollama server in background..."
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3
}

# Check installed Ollama models before pulling
$installedModels = ""
try {
    $installedModels = (ollama list 2>&1) | Out-String
} catch {
    $installedModels = ""
}

# Qwen 2.5 Coder (Core Brain & Writing)
if ($installedModels -match "qwen2\.5-coder:7b") {
    Write-Success "Model 'qwen2.5-coder:7b' verified (already installed)."
} else {
    Write-Host "  Downloading 'qwen2.5-coder:7b' LLM model..."
    try {
        ollama pull qwen2.5-coder:7b
        Write-Success "Model 'qwen2.5-coder:7b' ready."
    } catch {
        Write-Warn "Could not pull 'qwen2.5-coder:7b'. You can run 'ollama pull qwen2.5-coder:7b' later."
    }
}

# Gemma 3 4B (Vision & DSA Mentor)
if ($installedModels -match "gemma3:4b") {
    Write-Success "Model 'gemma3:4b' verified (already installed)."
} else {
    Write-Host "  Downloading 'gemma3:4b' Vision model..."
    try {
        ollama pull gemma3:4b
        Write-Success "Model 'gemma3:4b' ready."
    } catch {
        Write-Warn "Could not pull 'gemma3:4b'. You can run 'ollama pull gemma3:4b' later."
    }
}

# Download Piper TTS voice model if not present locally
$ttsModelPath = Join-Path $installDir "en_US-ryan-medium.onnx"
$ttsJsonPath  = Join-Path $installDir "en_US-ryan-medium.onnx.json"

if (-not (Test-Path $ttsModelPath)) {
    Write-Host "  Downloading Piper TTS voice model (en_US-ryan-medium)..."
    $onnxUrl = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/medium/en_US-ryan-medium.onnx"
    Invoke-WebRequest -Uri $onnxUrl -OutFile $ttsModelPath
    Write-Success "Voice model downloaded."
} else {
    Write-Success "Piper TTS voice model verified."
}

if (-not (Test-Path $ttsJsonPath)) {
    $jsonUrl = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/medium/en_US-ryan-medium.onnx.json"
    Invoke-WebRequest -Uri $jsonUrl -OutFile $ttsJsonPath -ErrorAction SilentlyContinue
}

# ------------------------------------------------------------------------------
# STEP 5: Global CLI Shims & Launcher Registration
# ------------------------------------------------------------------------------
Write-Step "Step 5/5: Registering global 'thanatos' command..."

# 1. Create thanatos.cmd (For CMD, Run Dialog, Scripts)
$cmdShimContent = @"
@echo off
setlocal
cd /d "$installDir"
"$venvPython" -m src.engine %*
endlocal
"@
$cmdShimPath = Join-Path $binDir "thanatos.cmd"
Set-Content -Path $cmdShimPath -Value $cmdShimContent -Encoding ASCII
Write-Success "Created $cmdShimPath"

# 2. Create thanatos.ps1 (For PowerShell)
$psShimContent = @"
Push-Location "$installDir"
try {
    & "$venvPython" -m src.engine `$args
} finally {
    Pop-Location
}
"@
$psShimPath = Join-Path $binDir "thanatos.ps1"
Set-Content -Path $psShimPath -Value $psShimContent -Encoding UTF8
Write-Success "Created $psShimPath"

# 3. Add $binDir to User PATH Environment Variable
$currentUserPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
$pathList = ($currentUserPath -split ';') | ForEach-Object { $_.Trim() }

if ($pathList -notcontains $binDir) {
    $newPath = "$currentUserPath;$binDir"
    [System.Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    $env:Path = "$env:Path;$binDir"
    Write-Success "Added $binDir to Windows User PATH."
} else {
    Write-Success "Directory $binDir is already on PATH."
}

# 4. Create Desktop Shortcut for easy 1-click launching
try {
    $wshShell = New-Object -ComObject WScript.Shell
    $desktopPath = [System.Environment]::GetFolderPath("Desktop")
    $shortcutPath = Join-Path $desktopPath "Thanatos AI.lnk"
    $shortcut = $wshShell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $cmdShimPath
    $shortcut.WorkingDirectory = $installDir
    $shortcut.Description = "Thanatos Personal Desktop AI Assistant"
    $shortcut.Save()
    Write-Success "Created Desktop shortcut: 'Thanatos AI'"
} catch {
    # Non-fatal if COM object fails
}

Write-Host "`n======================================================" -ForegroundColor Green
Write-Host "        THANATOS INSTALLED SUCCESSFULLY!              " -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host ""
Write-Host "To launch Thanatos right now, open any terminal and type:" -ForegroundColor Cyan
Write-Host "  thanatos" -ForegroundColor Yellow
Write-Host ""
Write-Host "Or double-click the 'Thanatos AI' shortcut on your Desktop." -ForegroundColor Cyan
Write-Host "Press Ctrl+Space anytime to summon your Tokyo Night Mini-Deck." -ForegroundColor Magenta
Write-Host "Press F8 anytime for instant screen DSA / LeetCode mentoring." -ForegroundColor Magenta
Write-Host ""
