"""
Helper script to set up dlib for face recognition
This script helps configure dlib to work with the virtual environment
"""
import os
import sys
import subprocess

def check_dlib():
    """Check if dlib is working"""
    try:
        import dlib
        import face_recognition
        print("SUCCESS: dlib and face_recognition are working!")
        print(f"dlib version: {dlib.__version__}")
        return True
    except ImportError as e:
        print(f"ERROR: dlib not working: {e}")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def main():
    print("=" * 60)
    print("dlib Setup Helper for Face Recognition")
    print("=" * 60)
    print()
    
    # Check current status
    print("Checking current dlib status...")
    if check_dlib():
        print("\nSUCCESS: Everything is working! No setup needed.")
        return
    
    print("\nERROR: dlib is not working in your virtual environment.")
    print("\nOptions to fix this:")
    print()
    print("OPTION 1: Use Conda Environment (Recommended)")
    print("-" * 60)
    print("1. Create conda environment:")
    print("   conda create -n fuelflux python=3.12 -y")
    print("   conda activate fuelflux")
    print("2. Install dlib:")
    print("   conda install -c conda-forge dlib -y")
    print("3. Install other packages:")
    print("   pip install -r requirements.txt")
    print()
    print("OPTION 2: Install Visual Studio Build Tools")
    print("-" * 60)
    print("1. Download: https://visualstudio.microsoft.com/downloads/")
    print("2. Install 'Build Tools for Visual Studio 2022'")
    print("3. Select 'Desktop development with C++' workload")
    print("4. Then run:")
    print("   pip install dlib")
    print("   pip install face-recognition")
    print()
    print("OPTION 3: Continue without face recognition")
    print("-" * 60)
    print("The app will work, but face recognition features will show")
    print("helpful error messages when used.")
    print()
    print("=" * 60)

if __name__ == "__main__":
    main()

