# Quick Start Guide - Running the App with Face Recognition

## The Problem
Conda is not in your PowerShell PATH, so `conda activate` doesn't work directly.

## Solution: Use the Startup Scripts

### Option 1: PowerShell Script (Recommended)
```powershell
.\start_conda.ps1
```

This script automatically:
- Finds conda
- Activates the `fuelflux` environment
- Runs your Flask app

### Option 2: Batch File (Windows CMD)
Double-click `start_conda.bat` or run:
```cmd
start_conda.bat
```

### Option 3: Manual (If scripts don't work)

**Step 1:** Initialize conda in PowerShell (one-time setup):
```powershell
& "$env:USERPROFILE\anaconda3\Scripts\conda.exe" init powershell
```
Then close and reopen PowerShell.

**Step 2:** After reopening PowerShell:
```powershell
conda activate fuelflux
python app.py
```

### Option 4: Direct Command (No activation needed)
```powershell
& "$env:USERPROFILE\anaconda3\Scripts\conda.exe" run -n fuelflux python app.py
```

## Verify It's Working

After the app starts, you should see:
```
✅ Database tables created successfully!
✅ Admin user already exists
 * Running on http://127.0.0.1:5001
```

## Troubleshooting

**If you see "conda not recognized":**
- Use Option 4 (direct command) above
- Or run the startup scripts (Option 1 or 2)

**If you see "No module named 'flask'":**
- Make sure you're using the conda environment
- The venv doesn't have all packages - use conda instead

**To check if conda environment has packages:**
```powershell
& "$env:USERPROFILE\anaconda3\Scripts\conda.exe" run -n fuelflux python -c "import flask; print('OK')"
```

---

**Easiest way:** Just run `.\start_conda.ps1` in PowerShell! 🚀





