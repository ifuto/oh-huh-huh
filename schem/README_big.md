# nature-island_500.schem — 建物なし 500×500 大自然島 (MC 1.21.11, DataVersion 4671)

`build_big.py` が生成。多次元フラクタルノイズによる純地形島:
- **雪を頂く山脈2座**(最高峰 y=128、雪線116〜、マツの亜高山帯)
- **蛇行する大河**(なだらかなU字谷、渓谷の洞門)+ 湖・山頂池
- **砂浜+入り江**(水域拡張5回で自然なビーチリング)
- **砂漠セクター**(サボテン+砂岩層)/ **桜の林**(cherry_log/leaves)
- 低地のオーク・白樺林、花の茂み、岩塊、崖
- **縁からの滝**(149柱、 void へ落ちるカーテン)
- 分割のない一枚岩の浮遊大陸(下側は逆円錐+スパイク)

## 検証 (すべて合格)
gzip CRC32/ISIZE / FAWEルートレイアウト / 60,000,000 varint = W×H×L /
生成グリッドとbyte一致 / 再ビルドbyte一致 / **浮遊水 0**

## 使い方
`//schem load nature-island_500` → `//paste -a`

視点写真: `renders/walk_big_*.png` / 俯瞰図: `renders/big_topdown.png`
再生成: `python3 schem/build_big.py`、一人称撮影: `python3 schem/walk.py`
