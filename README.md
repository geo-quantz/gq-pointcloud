# gq-filter: PDALベースの点群フィルタリングツール

`gq-filter` は、[PDAL](https://pdal.io/) を使用して、測量業務（地上レーザー・UAVレーザー）で頻繁に利用されるフィルタリング処理を自動化・簡略化するためのコマンドラインツールです。国土地理院の各種マニュアル等に準拠したプリセットを搭載しています。

## 主な機能
- **自動バッチ処理**: ディレクトリ内の全ファイル（.e57, .las, .laz）を順次処理。
- **一括マージ**: 複数ファイルを1つに結合し、同時に重複点除去を自動実行。
- **測量プリセット**: 地上レーザー(TLS)・UAVレーザーの規定値（入射角、距離、ボクセル等）をワンタップで適用。
- **自動器械点取得**: E57構造化ファイルからスキャナ位置を自動抽出し、距離フィルタを適用。
- **色クリーニング**: オルソ画像参照によるゴースト除去、または輝度ベースの簡易除去。
- **自動レポート**: 適用設定と処理点数を `processing_report.txt` に自動記録。

## セットアップ (Windows)

1. **Python 3.10+** をインストール。
2. **Conda/Miniconda** 環境（PDALインストール済み）を用意。
3. `setup_windows.bat` を実行。
    - 仮想環境の作成と、システム上の PDAL DLL の自動探索・設定が行われます。

環境の有効化：
```powershell
.venv\Scripts\activate
```

## 使い方

もっともシンプルな実行（`01_raw` 内のファイルを TLS 規定値で個別処理し、`04_product` に保存）：
```powershell
python main.py --preset tls
```

すべてのファイルを1つに結合して出力（自動で重複除去が有効になります）：
```powershell
python main.py --preset tls --merge
```

### 主要なオプション
- `-i, --input`: 入力パス（デフォルト: `01_raw`）
- `-o, --output`: 出力パス（デフォルト: `04_product`）
- `--preset`: `tls` または `uav` を選択。
- `--merge`: 複数ファイルを結合して出力。
- `--dry-run`: 実行せずに生成されるパイプラインを確認。

#### プリセット規定値
| プリセット | 振れ角(ScanAngle) | 入射角確保 | 距離(Range) | ボクセル |
| :--- | :--- | :--- | :--- | :--- |
| **tls** | 0.0 - 86.0° | 4°以上 | 0.5 - 25.0m | 0.01m |
| **uav** | 0.0 - 30.0° | - | 1.0 - 100.0m | 0.05m |

※ 個別の引数（例: `--range-max 50`）を指定することで、プリセット値の一部を上書き可能です。

#### フィルタ詳細
- **入射角**: `--incidence-angle-min`, `--incidence-angle-max`
- **距離**: `--range-min`, `--range-max`, `--origin X Y Z` (器械点手動指定)
- **色**: `--color-clean` (有効化), `--ortho-path <path>`, `--color-threshold <float>`
- **間引き**: `--voxel-size`
- **除去**: `--deduplicate`

## 開発とテスト
```powershell
pytest tests/test_filter.py
```

---
License: [MIT](LICENSE)
Copyright (c) 2026 geo-quantz
