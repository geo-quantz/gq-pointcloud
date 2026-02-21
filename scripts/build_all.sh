#!/bin/bash
set -e

# Dispatcher script for PDAL Filter CLI builds

OS="$(uname -s)"

case "${OS}" in
    Linux*)     
        echo "Detected Linux"
        ./scripts/build_linux.sh
        ;;
    Darwin*)    
        echo "Detected macOS"
        ./scripts/build_macos.sh
        ;;
    CYGWIN*|MINGW32*|MSYS*|MINGW*)
        echo "Detected Windows (Bash)"
        echo "Please use scripts/build_windows.ps1 in PowerShell for Windows builds."
        exit 1
        ;;
    *)
        echo "Unknown OS: ${OS}"
        exit 1
        ;;
esac
