# PDAL Filter CLI - macOS Distribution

This document describes how to build and run the standalone macOS executable for the PDAL filter CLI.

## Prerequisites

To build the executable, you need:

- macOS (Intel or Apple Silicon).
- Python 3.9 or newer.
- PDAL installed via Homebrew or Conda.

### Installing PDAL

**Via Homebrew (Recommended):**

```bash
brew install pdal
```

**Via Conda:**

```bash
conda create -n pdal_build -c conda-forge pdal python=3.10
conda activate pdal_build
```

## Building the Executable

Run the provided build script:

```bash
chmod +x scripts/build_macos.sh
./scripts/build_macos.sh
```

The script will:

1. Create a temporary virtual environment.
2. Install necessary Python dependencies (`pyinstaller`, `pdal`).
3. Build a standalone executable using `packaging/gqfilter_macos.spec`.
4. Perform a sanity check.
5. Create a `dist/gqfilter_macos.zip` archive.

The resulting binary will be located at `dist/gqfilter/gqfilter`.

## Architecture Support

By default, the executable is built for the architecture of the machine running the build script:

- **Apple Silicon (arm64):** Runs natively on M1/M2/M3 chips.
- **Intel (x86_64):** Runs on Intel Macs.

To create a universal binary, you would need to build on both and use `lipo`, or use a cross-compilation setup, which is
currently outside the scope of this script.

## Gatekeeper and Security

GitHub Release からダウンロードしたバイナリは、macOS Gatekeeper によってブロックされます（Apple Developer ID で署名・公証されていないため）。

### ダウンロード後の初回実行手順

zip を展開したら、**実行前に** 以下のコマンドで quarantine 属性を再帰的に除去してください。
gqfilter 本体だけでなく `_internal/` 内の全 dylib にも quarantine が付いているため、`-cr`（再帰）が必要です。

```bash
# 展開したディレクトリに移動
cd <展開先>

# quarantine 属性を再帰的に除去
xattr -cr ./gqfilter

# 実行確認
./gqfilter/gqfilter --help
```

> **注意**: ローカルで `scripts/build_macos.sh` を使ってビルドした場合は quarantine 属性が付かないため、この手順は不要です。

## Usage

```bash
./dist/gqfilter/gqfilter --input input.las --output output.las --deduplicate
```

For more options, run:

```bash
./dist/gqfilter/gqfilter --help
```
