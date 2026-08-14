# autzen-small.laz — テストフィクスチャ詳細説明

## 概要

| 項目 | 値 |
| :--- | :--- |
| ファイル名 | `autzen-small.laz` |
| 由来 | PDAL 公式サンプルデータセット（Autzen Stadium, Oregon, USA） |
| 元データ | [autzen-classified.laz](https://github.com/PDAL/data/tree/main/autzen)（Watershed Sciences / Hobu Inc.） |
| ライセンス | CC BY 4.0 |
| 生成日 | 2026-08-11 |
| ファイルサイズ | ~47 KB（LAZ 圧縮） |
| フォーマット | LAS 1.4 / Point Format 7（LAZ 圧縮） |

## 座標参照系 (CRS)

| 項目 | 値 |
| :--- | :--- |
| 複合 CRS 名 | NAD83 / Oregon GIC Lambert (ft) + NAVD88 height (ftUS) |
| 水平 CRS | EPSG:2992（NAD83 / Oregon GIC Lambert, 単位: フィート） |
| 垂直 CRS | EPSG:6360（NAVD88 height, 単位: 米国測量フィート） |
| 投影法 | Lambert 正角円錐図法（2 標準緯線） |
| 単位 | フィート（水平・垂直ともに） |
| Proj4 | `+proj=lcc +lat_0=41.75 +lon_0=-120.5 +lat_1=43 +lat_2=45.5 +datum=NAD83 +units=ft` |

> **注意**: 単位がメートルではなくフィートです。フィルターの距離パラメータはフィート単位で指定する必要があります（例: `--range-max 300` = 約 91m）。

## 点群の範囲と属性統計

### バウンディングボックス

| 軸 | 最小値 | 最大値 | 範囲 |
| :--- | ---: | ---: | ---: |
| X（東方向）| 636,500.07 ft | 636,620.00 ft | 119.93 ft（約 36.6 m） |
| Y（北方向）| 851,700.03 ft | 851,820.00 ft | 119.97 ft（約 36.6 m） |
| Z（高さ）| 424.76 ft | 498.26 ft | 73.50 ft（約 22.4 m） |

切り出し範囲は約 **120 ft × 120 ft（約 36 m × 36 m）** の正方形エリア。

### 点数

| 項目 | 値 |
| :--- | ---: |
| 総点数 | **7,388** |

### 分類コード（Classification）

ASPRS LAS 標準の分類コードを使用。Hobu Inc. による手作業分類。

| コード | ラベル | 点数 | 割合 |
| :---: | :--- | ---: | ---: |
| 0 | Unclassified（未分類） | 54 | 0.7% |
| 2 | Ground（地面） | 385 | 5.2% |
| 6 | Building（建物） | 6,949 | **94.1%** |

このデータは **建物点群が支配的**（Autzen Stadium の屋根・外壁）。植生（Class 5）は含まれない。分類コードフィルターのテストに最適。

### リターン番号（ReturnNumber / NumberOfReturns）

| ReturnNumber | 点数 | 割合 |
| :---: | ---: | ---: |
| 1（1st return） | 7,361 | **99.6%** |
| 2（2nd return） | 27 | 0.4% |

| NumberOfReturns | 点数 | 割合 |
| :---: | ---: | ---: |
| 1（単一リターン） | 7,334 | 99.3% |
| 2（複数リターン） | 54 | 0.7% |

硬い建物面への照射がほとんどのため、複数リターンは極めて少ない。`--keep-returns 1` で除去される点はわずか 27 点（0.4%）。

### 強度（Intensity）

| 項目 | 値 |
| :--- | ---: |
| 最小 | 0 |
| 最大 | 63,488 |
| 平均 | 17,470 |

16-bit 強度値（0〜65535 相当）。値域が広く、強度フィルターのテストに活用できる。

### スキャン角度（ScanAngleRank）

| 項目 | 値 |
| :--- | ---: |
| 最小 | −11.00° |
| 最大 | −4.00° |
| 平均 | −7.74° |

すべてのスキャン角が **負の値**（機体左側方向からの走査）で、範囲は −11° 〜 −4° と狭い。入射角フィルターの動作確認に使用する場合、値の符号と絶対値に注意。

### 利用可能なディメンション

```
X, Y, Z, Intensity, ReturnNumber, NumberOfReturns, ScanDirectionFlag,
EdgeOfFlightLine, Classification, Synthetic, KeyPoint, Withheld, Overlap,
ScanAngleRank, UserData, PointSourceId, GpsTime, ScanChannel,
Red, Green, Blue
```

RGB カラー情報も含む（色クリーニングフィルターの検証が可能）。

## フィクスチャの生成方法（再現用）

```bash
pdal pipeline - << 'EOF'
{
  "pipeline": [
    "data/raw/autzen-classified.laz",
    {
      "type": "filters.crop",
      "bounds": "([636500, 636620], [851700, 851820])"
    },
    {
      "type": "writers.las",
      "filename": "tests/fixtures/autzen-small.laz",
      "compression": "laszip"
    }
  ]
}
EOF
```

元データの取得:
```bash
wget https://github.com/PDAL/data/raw/main/autzen/autzen-classified.laz -O data/raw/autzen-classified.laz
```

## テストでの使用実績

### 機能評価（tools/evaluate_new_filters.py）

以下の 14 ケースすべてで PASS（2026-08-14 実施）:

| テストケース | 設定 | 結果（出力点数） | 除去率 |
| :--- | :--- | ---: | ---: |
| 統計的外れ値 (デフォルト) | k=8, 2σ | 7,262 | −1.7% |
| 統計的外れ値 (厳格) | k=16, 1.5σ | 7,221 | −2.3% |
| 半径外れ値 (デフォルト) | r=1.0ft, min_k=2 | 7,388 | 0.0% |
| 半径外れ値 (過剰) ⚠️ | r=0.5ft, min_k=5 | 0 | −100% |
| 分類コード: Ground のみ | Class=2 | 385 | −94.8% |
| 分類コード: Ground+Building | Class=2,6 | 7,334 | −0.7% |
| リターン番号: 1st のみ | ReturnNumber=1 | 7,361 | −0.4% |
| リターン番号: 1st+2nd | ReturnNumber=1,2 | 7,388 | 0.0% |
| 空間クリップ: SW 象限 | X: 636500-636560, Y: 851700-851760 | 1,855 | −74.9% |
| 空間クリップ: Z≤460ft | Z ≤ 460 ft | 885 | −88.0% |
| Z フィルター: 下限のみ | Z ≥ 444.76 ft | 7,365 | −0.3% |
| Z フィルター: 範囲 | Z: 424.76〜461.51 ft | 885 | −88.0% |
| ポアソン間引き (小) | radius=0.5ft | 4,474 | −39.4% |
| ポアソン間引き (大) | radius=2.0ft | 430 | −94.2% |

### 発見された挙動の特記事項

- **半径外れ値フィルター r=0.5ft/min_k=5**: 全点削除。建物屋根面の点密度（約 1 点/0.25 ft²）に対して半径が小さすぎるため、ほぼすべての点が「孤立点」と判定される。PDAL も警告を出力する。実運用では r=1.0ft 以上を推奨。

- **統計的外れ値**: 7,388 点中 126〜167 点を外れ値として検出。建物エッジ付近の遷移部分が外れ値とみなされる傾向がある。

- **入射角フィルター**: ScanAngleRank が −11°〜−4° に集中しているため、絶対値（4〜11°相当）を基準とした入射角フィルターとは直接対応しない。入射角計算には法線ベクトル推定が必要。

## 注意事項・制限

1. **単位がフィート**: パラメータをメートルとして指定すると、期待より大幅に緩い/厳しいフィルタリングになる
2. **建物点群に偏重**: 地面点が 5.2% のみのため、地面フィルタリング（TLS プリセット等）の実効性評価には向かない
3. **航空 LiDAR データ**: 地上 TLS フィルターの入射角・距離フィルターとは特性が異なる
4. **スキャン角度の偏り**: 全点が左舷走査（負の ScanAngleRank）のため、両方向走査の評価は不可

## Git LFS 管理

このファイルは Git LFS で管理されています。クローン後に以下を実行してください:

```bash
git lfs pull
```
