# 500x500 浮遊群島ワールド (suifu-island_500.schem)

道幅5ブロック基準(本島スケール = 96幅 × 2.63倍 ≒ 253ブロック幅)、
500×500×230 の浮遊群島ワールド。DataVersion 4671 = Minecraft 1.21.11。

## 構成
- **本島** 翠風の浮島(村・時計塔・湖・滝・小径[幅5]・橋・灯籠) — 中央
  - 追加: 石灯籠の道、小麦農場(水路付き)、桜並木、温泉(石枠+白樺デッキ)
- **テーマ浮島6**: 桜の林 / 竹林 / 砂漠(サボテン) / 雪と氷 / キノコ(菌糸) / 花畑
- 浮遊岩片24個

## 検証 (すべて合格)
- gzip: CRC32 / ISIZE / 独立デコンプレッサ一致 / 決定論的出力
- varint: 全ブロック57,500,000 = W×H×L、全ID 0-38 (1バイトvarint)
- world生成グリッドとbyte一致 / 再実行でbyte一致 / DataVersion 4671

## 使い方
`//schem load suifu-island_500` → `//paste -a`

## 再生成
```
python3 schem/build500.py     # GLBから世界を構築してschem+npzを書き出し
python3 schem/render_iso.py   # 実テクスチャのアイソメ描画 (renders/)
```

## テクスチャについて
`render_iso.py` は公式 client.jar から抽出した 1.21.11 テクスチャを
`schem/textures/` に置いて使用する(Mojang EULA上の再配布を避けるためリポジトリには含めない)。
抽出方法:
```
# version_manifest_v2.json → 1.21.11 → client.jar → 解凍
# assets/minecraft/textures/block/*.png を schem/textures/ へ
```
