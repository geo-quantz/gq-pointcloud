# gq-filter（ジークフィルター）

PDAL（Point Data Abstraction Library）を使った点群データフィルタリングCLIツールです。
LAS / LAZファイルに対して、入射角・強度・距離・重複点などのフィルタを柔軟に組み合わせて適用できます。

> 具体的な使い方やユースケースをわかりやすく紹介した記事を note で公開しています。
> 初めての方はこちらもぜひご覧ください。
>
> [gq-filter の使い方・活用事例（note）](https://note.com/gq_ki)

---

## 目次

- [機能概要](#機能概要)
- [ディレクトリ構成](#ディレクトリ構成)
- [セットアップ](#セットアップ)
- [使い方](#使い方)
- [フィルタオプション一覧](#フィルタオプション一覧)
- [使用例](#使用例)
- [ビルド（実行ファイルの作成）](#ビルド実行ファイルの作成)
- [テスト](#テスト)
- [対応フォーマット](#対応フォーマット)
- [トラブルシューティング](#トラブルシューティング)

---

## 機能概要

| フィルタ | 説明 |
|---------|------|
| 入射角フィルタ | `ScanAngleRank` の絶対値が指定値以下の点のみ残す |
| 強度フィルタ | `Intensity` が指定範囲内の点のみ残す |
| 距離フィルタ | 原点からのユークリッド距離 `√(X²+Y²+Z²)` が指定範囲内の点のみ残す |
| 重複除去フィルタ | XYZが完全一致する重複点を除去する |

フィルタは独立して有効化でき、指定したもののみが実行されます。複数指定した場合は上記の順番で適用されます。

---

## ディレクトリ構成

```
gq-filter/
├── cli.py                  # CLIエントリポイント（引数解析・実行）
├── main.py                 # 簡易エントリポイント
├── pyproject.toml          # プロジェクト設定・依存関係
├── uv.lock                 # 依存ライブラリのロックファイル
├── lib/
│   ├── __init__.py
│   └── filter.py           # フィルタビルダーとパイプライン実行ロジック
├── tests/
│   ├── __init__.py
│   └── test_filter.py      # ユニットテスト
├── scripts/
│   ├── build_all.sh        # OS自動判別ビルドスクリプト
│   ├── build_macos.sh      # macOS向けビルドスクリプト
│   ├── build_linux.sh      # Linux向けビルドスクリプト
│   ├── build_windows.ps1   # Windows向けビルドスクリプト（PowerShell）
│   ├── build_windows.bat   # Windows向けビルドスクリプト（バッチ）
│   └── build_msi.ps1       # Windows MSIインストーラー生成スクリプト
├── packaging/
│   ├── pdal_filter_macos.spec   # PyInstaller設定（macOS）
│   ├── pdal_filter_linux.spec   # PyInstaller設定（Linux）
│   ├── pdal_filter.spec         # PyInstaller設定（Windows）
│   └── pdal_filter.wxs          # WiX MSI定義ファイル
├── README_macos.md         # macOS向けビルド・配布ガイド
├── README_linux.md         # Linux向けビルド・配布ガイド
└── README_windows.md       # Windows向けビルド・配布ガイド
```

### 主要ファイルの役割

- **`cli.py`** — コマンドライン引数を解析し、フィルタ設定を組み立てて実行します。まずここを読むと全体の流れがわかります。
- **`lib/filter.py`** — 各フィルタのビルダー関数とPDALパイプラインの構築・実行ロジックが集約されています。フィルタの動作を理解するにはこのファイルを参照してください。
- **`tests/test_filter.py`** — パイプライン構造の検証と実際の点群ファイルを使った統合テストが含まれています。

---

## セットアップ

### 必要環境

- Python 3.14 以上
- PDAL 3.5.3 以上（C++ライブラリ）

### PDALのインストール

**macOS（Homebrew）**

```bash
brew install pdal
```

**macOS / Linux（Conda）**

```bash
conda create -n pdal_env -c conda-forge pdal python=3.10
conda activate pdal_env
```

**Linux（Ubuntu / Debian）**

```bash
sudo apt-get update
sudo apt-get install pdal libpdal-dev
```

**Windows**

Conda（推奨）またはpip経由でインストールしてください。

### 依存ライブラリのインストール

```bash
# uvを使う場合（推奨）
uv sync

# pipを使う場合
pip install pdal
```

---

## 使い方

### 基本構文

```bash
python cli.py -i <入力ファイル> -o <出力ファイル> [オプション...]
```

### ビルド済み実行ファイルを使う場合

```bash
# macOS / Linux
./dist/pdal_filter/pdal_filter -i input.las -o output.las [オプション...]

# Windows
dist\pdal_filter\pdal_filter.exe -i input.las -o output.las [オプション...]
```

### ヘルプの表示

```bash
python cli.py --help
```

---

## フィルタオプション一覧

### 必須オプション

| オプション | 短縮形 | 説明 |
|-----------|--------|------|
| `--input <PATH>` | `-i` | 入力点群ファイルのパス |
| `--output <PATH>` | `-o` | 出力点群ファイルのパス |

### 入射角フィルタ

| オプション | 説明 |
|-----------|------|
| `--incidence-angle-max <値>` | 最大入射角（`ScanAngleRank` の絶対値の上限）。この値以下の点のみ残す |

### 強度フィルタ

| オプション | 説明 |
|-----------|------|
| `--intensity-min <値>` | 強度の下限値 |
| `--intensity-max <値>` | 強度の上限値 |

### 距離フィルタ

| オプション | 説明 |
|-----------|------|
| `--range-min <値>` | 原点からの最小距離（メートル） |
| `--range-max <値>` | 原点からの最大距離（メートル） |

### 重複除去フィルタ

| オプション | 説明 |
|-----------|------|
| `--deduplicate` | XYZが完全に一致する重複点を除去する |

### その他

| オプション | 説明 |
|-----------|------|
| `--dry-run` | PDALパイプラインのJSONを表示するだけで実行しない（動作確認に便利） |

---

## 使用例

### 重複点の除去

```bash
python cli.py -i input.las -o output.las --deduplicate
```

### 強度でフィルタリング

```bash
python cli.py -i input.las -o output.las --intensity-min 100 --intensity-max 500
```

### 入射角が15度以下の点のみ残す

```bash
python cli.py -i input.las -o output.las --incidence-angle-max 15.0
```

### 複数フィルタを組み合わせる

```bash
python cli.py -i input.las -o output.las \
  --incidence-angle-max 15.0 \
  --intensity-min 50 --intensity-max 1000 \
  --range-min 0.5 --range-max 100.0 \
  --deduplicate
```

### ドライラン（パイプラインの確認）

実際に実行せず、生成されるPDALパイプラインのJSONを確認できます。

```bash
python cli.py -i input.las -o output.las --intensity-min 100 --dry-run
```

### LAZ形式への出力

出力ファイルの拡張子で出力フォーマットが自動的に決まります。

```bash
python cli.py -i input.las -o output.copc.laz --deduplicate
```

---

## ビルド（実行ファイルの作成）

PyInstallerを使って、Python不要のスタンドアロン実行ファイルを生成できます。
各OS向けの詳細手順は下記ファイルを参照してください。

| OS | 詳細ガイド | ビルドスクリプト |
|----|-----------|----------------|
| macOS | [README_macos.md](./README_macos.md) | `scripts/build_macos.sh` |
| Linux | [README_linux.md](./README_linux.md) | `scripts/build_linux.sh` |
| Windows | [README_windows.md](./README_windows.md) | `scripts/build_windows.ps1` |

### macOS

Apple Silicon (arm64) / Intel (x86_64) の両アーキテクチャに対応しています。

```bash
chmod +x scripts/build_macos.sh
./scripts/build_macos.sh
# 出力: dist/pdal_filter/pdal_filter
# アーカイブ: dist/pdal_filter_macos.zip
```

### Linux

最大互換性のために、サポート対象の最も古いディストリビューション上でビルドすることを推奨します。

```bash
chmod +x scripts/build_linux.sh
./scripts/build_linux.sh
# 出力: dist/pdal_filter/pdal_filter
# アーカイブ: dist/pdal_filter_linux.tar.gz
```

### Windows（PowerShell）

```powershell
.\scripts\build_windows.ps1
# 出力: dist\pdal_filter\pdal_filter.exe
```

### Windows MSIインストーラー（オプション）

WiX Toolset v3 が必要です。

```powershell
.\scripts\build_msi.ps1
# 出力: dist/pdal_filter.msi
```

---

## テスト

```bash
# テスト実行
pytest tests/

# 詳細出力
pytest tests/ -v

# カバレッジ計測
pytest tests/ --cov=lib
```

テスト用サンプルファイル:
- `cli_test.las` — テストフィクスチャ用の点群ファイル

---

## 対応フォーマット

### 入力フォーマット

PDALがサポートするすべての形式（ファイル拡張子で自動判別）:
- `.las` — LAS点群ファイル
- `.laz` — 圧縮LAS（LASzip対応環境が必要）

### 出力フォーマット

拡張子によって出力形式が自動的に決まります:

| 拡張子 | フォーマット |
|--------|------------|
| `.copc.laz` | COPC（Cloud Optimized Point Cloud） |
| `.txt`, `.csv` | テキスト形式 |
| `.las`, その他 | LAS形式 |

---

## トラブルシューティング

### macOS: 実行ファイルがブロックされる

Gatekeeperによってブロックされた場合は以下を実行してください。

```bash
xattr -d com.apple.quarantine dist/pdal_filter/pdal_filter
```

または、Finderで右クリック →「開く」を選択してください。

### Linux: `GLIBC_X.Y not found` エラー

ビルドしたOSより古いディストリビューションでは動作しないことがあります。
できるだけ古い（サポート対象の最古の）ディストリビューション上でビルドしてください。

### Windows: DLLが見つからない

1. Conda環境でPDALがインストールされているか確認してください
2. ビルドスクリプトは自動でDLLを検出・同梱します
3. `--onefile`ではなく`--onedir`形式でビルドしてください（スクリプトのデフォルト）

### 重複除去フィルタが使えない

`filters.unique` または `filters.duplicate` が使用している環境のPDALに含まれていない場合、ツールは自動的にそのフィルタを除いて実行します。その際、コンソールに通知メッセージが表示されます。

---

## ライセンス

Apache License 2.0 — 詳細は [LICENSE](./LICENSE) を参照してください。
