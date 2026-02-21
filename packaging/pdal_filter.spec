# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

# We'll use 'cli.py' as the main entry point
entry_point = os.path.abspath(os.path.join(os.getcwd(), 'cli.py'))

# Collect PDAL data files and libraries
# PDAL often has JSON files for its configuration and various DLLs
datas = collect_data_files('pdal')
binaries = collect_dynamic_libs('pdal')

# If PDAL is installed via Conda, we might need to manually add the Library/bin folder 
# for PDAL plugins (filters, readers, writers).
# This is a common requirement for PDAL + PyInstaller on Windows.
conda_prefix = os.environ.get('CONDA_PREFIX')
if conda_prefix:
    pdal_bin = os.path.join(conda_prefix, 'Library', 'bin')
    if os.path.exists(pdal_bin):
        # We add all DLLs from Library/bin to the root of the app
        # This ensures PDAL can find its plugins at runtime.
        for f in os.listdir(pdal_bin):
            if f.endswith('.dll'):
                binaries.append((os.path.join(pdal_bin, f), '.'))

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
