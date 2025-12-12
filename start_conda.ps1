# Start Flask app using conda environment
Write-Host "Starting Flask app with conda environment 'fuelflux'..." -ForegroundColor Green
Set-Location $PSScriptRoot

# Use direct path to Python in conda environment (more reliable than conda run)
$pythonPath = "$env:USERPROFILE\anaconda3\envs\fuelflux\python.exe"

if (Test-Path $pythonPath) {
    Write-Host "Using conda environment: fuelflux" -ForegroundColor Cyan
    Write-Host "Python: $pythonPath" -ForegroundColor Gray
    Write-Host "Starting Flask app..." -ForegroundColor Yellow
    Write-Host ""
    
    # Run the app directly using Python from conda environment
    & $pythonPath app.py
} else {
    Write-Host "ERROR: Python not found at $pythonPath" -ForegroundColor Red
    Write-Host "Please check your Anaconda installation and ensure 'fuelflux' environment exists." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

