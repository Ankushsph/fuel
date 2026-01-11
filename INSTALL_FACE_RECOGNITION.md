# Installing Face Recognition Library

The employee attendance feature requires the `face_recognition` library. Follow these steps to install it:

## Windows Installation

### Option 1: Using pip (Recommended if you have Visual Studio Build Tools)

```bash
pip install face-recognition dlib
```

**Note:** If you encounter errors, you may need to install Visual Studio Build Tools first.

### Option 2: Using conda (Easier on Windows)

```bash
conda install -c conda-forge dlib
pip install face-recognition
```

### Option 3: Pre-built wheels (Alternative)

If the above methods fail, you can try installing pre-built wheels:

```bash
pip install cmake
pip install dlib
pip install face-recognition
```

## Linux/Mac Installation

```bash
# Install system dependencies (Linux)
sudo apt-get update
sudo apt-get install -y python3-dev build-essential cmake

# Install Python packages
pip install face-recognition dlib
```

## Verify Installation

After installation, restart your Flask application. The face recognition features will be available once the library is installed.

## Troubleshooting

If you see `ModuleNotFoundError: No module named 'face_recognition'`:

1. Make sure you're in the correct virtual environment
2. Activate your virtual environment: `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Linux/Mac)
3. Install the library: `pip install face-recognition dlib`
4. Restart your Flask application

## Note

The application will start even without face_recognition installed, but the employee attendance features will show an error when used. Install the library to enable these features.








