#!/usr/bin/env python3
"""
Smooth plains world generator -> Sponge v2 schem (MC 1.21.11, DV 4671).

1000x1000x200: solid stone body, 2-block dirt layer, 1-block grass layer.
Gently rolling hills with ~8 blocks total elevation range, no caves, no
water, no features.  Deterministic (sum-of-sines terrain, seedless).

Output: smooth_plains_1000.schem + world_smooth.npz
"""
import os, gzip
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

P = {'minecraft:air': 0, 'minecraft:stone': 1, 'minecraft:dirt': 2,
     'minecraft:grass_block': 3}
STONE, DIRT, GRASS = 1, 2, 3

H, L, W = 200, 1000, 1000          # y, z, x
BASE = 190                          # mean surface y

# ---------------- heightmap: smooth sum-of-sines, ~8 blocks total range ----------------
xs = np.arange(W)[None, :].astype(np.float64)
zs = np.arange(L)[:, None].astype(np.float64)

def wave(ax, az, px, pz):
    return np.sin(2 * np.pi * xs / ax + px) * np.cos(2 * np.pi * zs / az + pz)

h = (2.60 * wave(310, 270, 1.7, 0.4) +
     1.50 * np.sin(2 * np.pi * xs / 150 + 4.2) * np.sin(2 * np.pi * zs / 190 + 2.9) +
     0.90 * np.sin(2 * np.pi * (xs + zs) / 230 + 5.1))
# rescale to exactly +-4 (total range 8) and round to integers
hmin, hmax = h.min(), h.max()
h = (h - (hmin + hmax) / 2) / ((hmax - hmin) / 2) * 4.0
hi = np.rint(BASE + h).astype(np.int64)
print("surface y: %d..%d (range %d), mean %d" % (hi.min(), hi.max(), hi.max() - hi.min(), int(round(hi.mean()))))
step = np.abs(np.diff(hi, axis=0)).max(), np.abs(np.diff(hi, axis=1)).max()
print("max neighbour step:", step)

# ---------------- fill: stone body + dirt x2 + grass x1 ----------------
grid = np.full((H, L, W), STONE, dtype=np.uint8)
for y0 in range(0, H, 40):
    y1 = min(y0 + 40, H)
    yy = np.arange(y0, y1)[:, None, None]
    hh = hi[None, :, :]
    slab = grid[y0:y1]
    slab[yy > hh] = 0                       # air above the surface
    slab[(yy >= hh - 2) & (yy <= hh - 1)] = DIRT
    slab[yy == hh] = GRASS
    grid[y0:y1] = slab
print("blocks:", int((grid != 0).sum()))

np.savez_compressed('world_smooth.npz', grid=grid, palette=np.array(list(P.keys()), dtype=object))

# ---------------- write schem ----------------
def write_schem(path='smooth_plains_1000.schem'):
    vals = grid.reshape(-1).astype(np.int8)
    import nbtlib
    from nbtlib import Compound, String, Int, Short, ByteArray
    sch = Compound({
        'Version': Int(2), 'DataVersion': Int(4671),
        'Width': Short(W), 'Height': Short(H), 'Length': Short(L),
        'Offset': nbtlib.IntArray([0, 0, 0]),
        'PaletteMax': Int(len(P)),
        'Palette': Compound({String(k): Int(v) for k, v in P.items()}),
        'BlockData': ByteArray(vals),
        'Metadata': Compound({String('Name'): String('smooth-plains-1000'), String('Author'): String('ISOLA World Studio')}),
    })
    f = nbtlib.File(); f.update(sch); f.root_name = 'Schematic'
    tmp = path + '.tmp'
    f.save(tmp, gzipped=True)
    payload = gzip.decompress(open(tmp, 'rb').read())
    os.unlink(tmp)
    with open(path, 'wb') as fh:
        fh.write(gzip.compress(payload, compresslevel=6, mtime=0))
    print("schem written:", os.path.getsize(path), "bytes")

write_schem()
print("DONE")
