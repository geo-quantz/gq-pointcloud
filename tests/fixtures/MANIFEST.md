# Fixture Manifest

フィクスチャはすべて Git LFS で管理されています。
`git lfs pull` を実行してからテストを走らせてください。

## autzen-small.laz

| 項目 | 値 |
|---|---|
| 由来 | PDAL 公式サンプルデータ [autzen-classified.laz](https://github.com/PDAL/data/tree/main/autzen) |
| ライセンス | CC BY 4.0（Watershed Sciences / Hobu Inc.） |
| 生成日 | 2026-08-11 |
| 切り出し範囲 | X: 636500–636620, Y: 851700–851820（Oregon GIC Lambert ft） |
| 点数 | 7,388 |
| ファイルサイズ | ~47 KB（LAZ 圧縮） |
| CRS | NAD83 / Oregon GIC Lambert (ft) + NAVD88 height (ftUS) |
| EPSG（水平） | EPSG:2992 |
| フィールド | X, Y, Z, Intensity, ReturnNumber, NumberOfReturns, ScanDirectionFlag, EdgeOfFlightLine, Classification, ScanAngleRank, UserData, PointSourceId, Red, Green, Blue, GpsTime |
| 分類ラベル | 0=未分類, 2=地面, 5=植生, **6=建物** |
| Ground truth | Classification フィールド（Hobu Inc. による手作業分類） |
| 参照実装 | PDAL CLI v2.10.1 |

### 生成コマンド（再現用）

```bash
pdal pipeline - << 'EOF'
{
  "pipeline": [
    "data/raw/autzen-classified.laz",
    {"type": "filters.crop", "bounds": "([636500, 636620], [851700, 851820])"},
    {"type": "writers.las", "filename": "tests/fixtures/autzen-small.laz", "compression": "laszip"}
  ]
}
EOF
```

## フィクスチャ追加時のルール

1. フィクスチャは **ハーネスが数分で回れる**サイズに切り出す（目安: 点数 5,000〜50,000）
2. この MANIFEST.md に由来・ライセンス・生成コマンドを記録する
3. フィクスチャの選定・追加は**必ず人間が承認**する（ハーネス自体は変更しない）
4. Ground truth が変わる場合は独立したコミットにする
