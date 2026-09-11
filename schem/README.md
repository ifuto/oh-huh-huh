# Suifu Island → Minecraft Sponge v2 Schematics

`convert.py` が GLB をボクセライズして Sponge v2 (.schem, DataVersion 4671 = MC 1.21.11) に変換する。

## ファイル
- `suifu-island_96.schem`  — 100x58x100 (実質96幅+マージン), 10.4万ブロック
- `suifu-island_192.schem` — 200x114x200, 高解像度版
- `*_map.png`   上面図 / `*_slice.png` 断面図(確認用レンダー)

## ブロック対応(自然マッピング)
- 芝生メッシュ → grass_block + 下3層 dirt/stone
- 岩盤(逆円錐) → stone / andesite / cobblestone をハッシュで自然に混ぜる
- 建物: lightwood→birch板材, wood→oak板材, roof→spruce板材, roof2→dark_oak板材,
  timber→spruce原木, 窓→glowstone, ガラス→glass, 土台→cobblestone
- 木: trunk→oak原木, 葉は4種の原木の葉, 花→flowering_azalea_leaves
- 水: 湖・川・滝 → water(自然に3ブロックまで流下), 泡 → snow
- 小径 → dirt_path

## 使い方 (WorldEdit)
1. `suifu-island_96.schem` を `plugins/WorldEdit/schematics/`(FAWEなら `plugins/FastAsyncWorldEdit/schematics/`)に置く
2. `//schem load suifu-island_96`
3. 貼り付けたい地点に立って `//paste -a`(-a は空気ブロックをスキップ)

再変換: `python3 schem/convert.py suifu-island_96.glb schem/suifu-island_96.schem`
検証: `python3 schem/verify_schem.py schem/suifu-island_96.schem suifu-island_96.glb`(gzip/NBT/varint/再現性/レンダ照合の5層チェック)
