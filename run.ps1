# run.ps1 — start the assistant from the project root
# Usage: .\run.ps1
# Optional: .\run.ps1 --llm   (enables Ollama LLM planner)

param(
    [switch]$llm,
    [string]$model = "llama3.1",
    [int]$port = 8000
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "Personal Desktop Assistant" -ForegroundColor Cyan
Write-Host "==========================" -ForegroundColor Cyan
Write-Host ""

# Activate venv
if (Test-Path ".venv\Scripts\Activate.ps1") {
    & .\.venv\Scripts\Activate.ps1
} else {
    Write-Host "No .venv found. Run .\setup.ps1 first." -ForegroundColor Red
    exit 1
}

# Optional: enable LLM planner
if ($llm) {
    $env:LOCAL_MODEL_PROVIDER    = "ollama"
    $env:LOCAL_MODEL_NAME        = $model
    $env:LOCAL_MODEL_ENDPOINT    = "http://127.0.0.1:11434"
    Write-Host "LLM planner: enabled (model=$model)" -ForegroundColor Blue
} else {
    Remove-Item Env:\LOCAL_MODEL_PROVIDER -ErrorAction SilentlyContinue
    Write-Host "LLM planner: disabled (deterministic mode)" -ForegroundColor Green
}

Write-Host "Starting server on http://127.0.0.1:$port" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop." -ForegroundColor Yellow
Write-Host ""

python -m uvicorn app.main:app --reload --port $port
