# setup.ps1 — run once from the project root to create the venv and install all deps
# Usage: .\setup.ps1

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "Personal Desktop Assistant — Setup" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

# 1 ── Check Python version
$pyVersion = python --version 2>&1
if ($pyVersion -notmatch "3\.(11|12|13)") {
    Write-Host "WARNING: Python 3.11 or 3.12 is recommended. Found: $pyVersion" -ForegroundColor Yellow
}
Write-Host "Python: $pyVersion" -ForegroundColor Green

# 2 ── Create venv
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
    Write-Host "Virtual environment created." -ForegroundColor Green
} else {
    Write-Host "Virtual environment already exists." -ForegroundColor Green
}

# 3 ── Activate and install
Write-Host "Installing dependencies..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1
pip install --upgrade pip --quiet
pip install -r requirements.txt

Write-Host ""
Write-Host "Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "To start the assistant:" -ForegroundColor Cyan
Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "  python -m uvicorn app.main:app --reload" -ForegroundColor White
Write-Host ""
Write-Host "Then open http://127.0.0.1:8000 in your browser." -ForegroundColor Cyan
Write-Host ""
