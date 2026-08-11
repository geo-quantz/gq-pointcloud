# GeoQuantz Loop PR テンプレート

このファイルは `tools/pr_creator.py` が PR 本文を自動生成する際に使用するテンプレートです。
`{{...}}` は自動置換されます。

---

## 変更の要約

{{SUMMARY}}

---

## ハーネス結果

### メトリクス差分

{{METRICS_TABLE}}

### 不変条件チェック

{{INVARIANTS_RESULT}}

### 参照実装との比較（PDAL CLI）

{{REFERENCE_RESULT}}

---

## チェックリスト

- [ ] `make harness` が全件グリーン
- [ ] ベースライン変更がある場合、実装変更と**別コミット**になっている
- [ ] 差分が 400 行以内
- [ ] `main` への直接コミット・force push をしていない

---

*このPRは [gq-filter ループエンジニアリング](../.github/geoquantz-loop.md) によって自動生成されました。*
