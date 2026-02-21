# -*- mode: python ; coding: utf-8 -*-
import os
import sys
import subprocess
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

# Entry point
entry_point = os.path.abspath(os.path.join(os.getcwd(), 'cli.py'))

# Basic PDAL collection
datas = collect_data_files('pdal')
binaries = collect_dynamic_libs('pdal')

# Handle PDAL shared libraries and plugins on macOS
# PDAL on macOS (especially via Homebrew or Conda) uses .dylib files.
# We need to ensure the base PDAL libraries and any plugins are bundled.

# 1. Check Conda environment
conda_prefix = os.environ.get('CONDA_PREFIX')
if conda_prefix:
    pdal_lib = os.path.join(conda_prefix, 'lib')
    if os.path.exists(pdal_lib):
        for f in os.listdir(pdal_lib):
            if 'libpdal' in f and f.endswith('.dylib'):
                binaries.append((os.path.join(pdal_lib, f), '.'))

# 2. Check Homebrew (as fallback or addition)
try:
    brew_prefix = subprocess.check_output(['brew', '--prefix'], encoding='utf-8').strip()
    pdal_homebrew_lib = os.path.join(brew_prefix, 'lib')
    if os.path.exists(pdal_homebrew_lib):
        for f in os.listdir(pdal_homebrew_lib):
            if 'libpdal' in f and f.endswith('.dylib'):
                # Avoid duplicates if already added by collect_dynamic_libs
                target_path = os.path.join(pdal_homebrew_lib, f)
                if not any(target_path == b[0] for b in binaries):
                    binaries.append((target_path, '.'))
except Exception:
    pass

a = Analysis(
    [entry_point],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=['pdal'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='pdal_filter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='pdal_filter',
)
