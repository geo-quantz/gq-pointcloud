# data/raw/

このディレクトリは `.gitignore` で除外されています。Git には入りません。

## 用途

フィクスチャの元となる生データ（大容量 LAS/LAZ）をローカルに置く場所です。

## 入手方法

### Autzen Stadium（PDAL 公式サンプル）

```bash
curl -L -o data/raw/autzen-classified.laz \
  "https://github.com/PDAL/data/raw/refs/heads/main/autzen/autzen-classified.laz"
```

- サイズ: ~74 MB
- ライセンス: CC BY 4.0
- 用途: `tests/fixtures/autzen-small.laz` の生成元

### GeoQuantz 共有 Google Drive

大容量の生 LAS データは Google Drive を参照してください。
（アクセス方法は gq-dev の README を参照）
