# Windows Distribution Guide - PDAL Filter CLI

このドキュメントでは、`gq-filter` をスタンドアロンの Windows 実行ファイル (EXE) としてビルドし、配布する方法について説明します。
基本的なセットアップと使用方法については、ルートの [README.md](../README.md) を参照してください。

## ビルド環境の準備

スタンドアロン実行ファイルを作成するには、以下のツールが必要です：

- **Python 3.10+**
- **PDAL**: DLLを同梱するため、Conda環境（`gq-pdal`等）にインストールされている必要があります。
- **WiX Toolset v3** (MSIインストーラを作成する場合のみ)

## ビルド手順

1. **プロジェクトのルートディレクトリで PowerShell を開きます。**
2. **ビルドスクリプトを実行します**:
    ```powershell
    .\scripts\build_windows.ps1
    ```

このスクリプトは以下の処理を行います：
- ビルド専用の仮想環境 (`.venv-build`) を作成。
- `pyinstaller`, `pdal`, および本パッケージをインストール。
- `packaging/pdal_filter.spec` を使用して、必要な DLL をすべて同梱した実行ファイルディレクトリを `dist\pdal_filter\` に生成。
- `pdal_filter.exe --help` による正常性確認。

## MSI インストーラの作成 (オプション)

WiX Toolset がインストールされている場合、以下のスクリプトで MSI インストーラを作成できます。これにより、ツールがシステム PATH に自動的に追加されます。
```powershell
.\scripts\build_msi.ps1
```
インストーラは `dist\pdal_filter.msi` に生成されます。

## 出力物の構成

ビルド成功後、`dist\pdal_filter\` ディレクトリに以下が含まれます：
- `pdal_filter.exe`: メインの実行ファイル
- `pdalcpp.dll`, `libpdal_plugin_*.dll` 等: PDALの動作に必要なDLL群

## 配布時の注意点

- **DLLの依存関係**: `pdal_filter.spec` は、ビルド時にアクティブな Conda 環境から DLL を収集するように設定されています。特定のドライバ（E57など）が必要な場合は、ビルド環境にそれらがインストールされていることを確認してください。
- **ディレクトリ配布**: `--onedir` 形式でビルドしているため、配布時は `dist\pdal_filter\` フォルダをまるごと配布する必要があります。

## トラブルシューティング

### 起動時に DLL が見つからないエラーが出る場合
- `packaging/pdal_filter.spec` 内の `conda_prefix` の解決が正しく行われているか確認してください。
- ビルド時に正しい Conda 環境がアクティブになっている必要があります。
