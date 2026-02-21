# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

# Entry point
entry_point = os.path.abspath(os.path.join(os.getcwd(), 'cli.py'))

# Basic PDAL collection
datas = collect_data_files('pdal')
binaries = collect_dynamic_libs('pdal')

# Handle PDAL shared libraries and plugins on Linux
# PDAL on Linux (via Conda or system package manager) uses .so files.

# Check Conda environment
conda_prefix = os.environ.get('CONDA_PREFIX')
if conda_prefix:
    pdal_lib = os.path.join(conda_prefix, 'lib')
    if os.path.exists(pdal_lib):
        for f in os.listdir(pdal_lib):
            if 'libpdal' in f and ('.so' in f):
                binaries.append((os.path.join(pdal_lib, f), '.'))

# Common system paths for PDAL on Linux (e.g., /usr/lib, /usr/local/lib)
system_lib_paths = ['/usr/lib', '/usr/lib/x86_64-linux-gnu', '/usr/local/lib']
for path in system_lib_paths:
    if os.path.exists(path):
        for f in os.listdir(path):
            if 'libpdal' in f and ('.so' in f):
                target_path = os.path.join(path, f)
                if not any(target_path == b[0] for b in binaries):
                    binaries.append((target_path, '.'))

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
