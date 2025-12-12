# Initialize and activate conda environment for PowerShell
# Run this once to set up conda in your PowerShell session

$condaPath = "$env:USERPROFILE\anaconda3\Scripts\conda.exe"

if (Test-Path $condaPath) {
    Write-Host "Initializing conda for PowerShell..." -ForegroundColor Green
    
    # Initialize conda
    & $condaPath init powershell
    
    Write-Host "`nConda initialized! Please:" -ForegroundColor Yellow
    Write-Host "1. Close and reopen this PowerShell window" -ForegroundColor Yellow
    Write-Host "2. Then run: conda activate fuelflux" -ForegroundColor Yellow
    Write-Host "3. Then run: python app.py" -ForegroundColor Yellow
    Write-Host "`nOr use: .\start_conda.ps1" -ForegroundColor Cyan
} else {
    Write-Host "ERROR: Conda not found at $condaPath" -ForegroundColor Red
    Write-Host "Please check your Anaconda installation." -ForegroundColor Yellow
}




