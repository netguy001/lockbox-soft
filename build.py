"""
LockBox EXE Builder Script
Run this to create a standalone executable
"""

import PyInstaller.__main__
import sys
import os

# Get the absolute path to the project root
project_root = os.path.dirname(os.path.abspath(__file__))
icon_path = os.path.join(project_root, "lcbx.ico")

# PyInstaller arguments
args = [
    'app/main.py',  # Entry point
    '--name=LockBox',  # EXE name
    f'--icon={icon_path}',  # Icon file
    '--onefile',  # Single executable
    '--windowed',  # No console window (GUI app)
    '--clean',  # Clean cache before building
    
    # Add data files
    f'--add-data={icon_path};.',  # Include icon in exe
    
    # Hidden imports (sometimes needed)
    '--hidden-import=customtkinter',
    '--hidden-import=pyperclip',
    '--hidden-import=cryptography',
    '--hidden-import=argon2',
    '--hidden-import=PIL',
    '--hidden-import=PIL._tkinter_finder',
    
    # Exclude unnecessary modules to reduce size
    '--exclude-module=matplotlib',
    '--exclude-module=pandas',
    '--exclude-module=numpy',
    '--exclude-module=scipy',
    
    # Security
    '--noupx',  # Don't use UPX compression (better compatibility)
    
    # Output directory
    '--distpath=dist',
    '--workpath=build',
    '--specpath=.',
]

print("Building LockBox executable...")
print(f"Icon path: {icon_path}")
print(f"Icon exists: {os.path.exists(icon_path)}")
print("-" * 50)

try:
    PyInstaller.__main__.run(args)
    print("\n" + "=" * 50)
    print("✓ Build completed successfully!")
    print("✓ EXE location: dist/LockBox.exe")
    print("=" * 50)
except Exception as e:
    print(f"\n✗ Build failed: {e}")
    sys.exit(1)
