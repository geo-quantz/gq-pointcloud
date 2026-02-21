#!/bin/bash
set -e

# Linux Build Script for PDAL Filter CLI

echo "Starting Linux build process..."

# 1. Setup environment
PYTHON_EXE=${PYTHON_EXE:-python3}
VENV_DIR="build_venv_linux"

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating temporary virtual environment..."
    $PYTHON_EXE -m venv $VENV_DIR
fi

source $VENV_DIR/bin/activate

echo "Installing dependencies..."
pip install --upgrade pip
pip install pyinstaller pdal

# 2. Run PyInstaller
echo "Running PyInstaller..."
pyinstaller --clean packaging/pdal_filter_linux.spec

# 3. Sanity check
if [ -d "dist/pdal_filter" ]; then
    echo "Build successful: dist/pdal_filter/"
    echo "Running sanity check (--help)..."
    ./dist/pdal_filter/pdal_filter --help > /dev/null
    echo "Sanity check passed."
else
    echo "Build failed: dist/pdal_filter directory not found."
    exit 1
fi

# 4. Create archive
echo "Creating tar.gz archive..."
tar -czf dist/pdal_filter_linux.tar.gz -C dist pdal_filter
echo "Archive created: dist/pdal_filter_linux.tar.gz"

echo "Linux build complete."
