#!/usr/bin/env python3
"""
Big nature island: 500x500, NO buildings. Mountains w/ snowcaps, meandering
rivers, lake, sea bays with beaches, waterfalls over the rim, cherry grove,
bamboo patch, desert sector, forests, hanging rock underside. -> Sponge v2.
"""
import struct, json, gzip, os, io
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
W, H, L = 500, 240, 500
AIR = 0

P = {n: i for i, n in enumerate([
    'minecraft:air',
    'minecraft:grass_block', 'minecraft:dirt', 'minecraft:stone', 'minecraft:andesite', 'minecraft:cobblestone',
    'minecraft:oak_planks', 'minecraft:birch_planks', 'minecraft:spruce_planks', 'minecraft:dark_oak_planks',
    'minecraft:spruce_log', 'minecraft:oak_log', 'minecraft:birch_log',
    'minecraft:oak_leaves', 'minecraft:birch_leaves', 'minecraft:spruce_leaves', 'minecraft:dark_oak_leaves',
    'minecraft:flowering_azalea_leaves', 'minecraft:pink_terracotta',
    'minecraft:glass', 'minecraft:glowstone', 'minecraft:dirt_path', 'minecraft:sand', 'minecraft:snow_block',
    'minecraft:water', 'minecraft:stone_bricks', 'minecraft:smooth_stone', 'minecraft:hay_block',
    'minecraft:cherry_log', 'minecraft:cherry_leaves', 'minecraft:bamboo_block',
    'minecraft:sandstone', 'minecraft:cactus', 'minecraft:mycelium', 'minecraft:red_mushroom_block',
    'minecraft:mushroom_stem', 'minecraft:white_wool', 'minecraft:red_wool', 'minecraft:packed_ice',
])}
assert len(P) < 128
G, D, S, AN, CO = P['minecraft:grass_block'], P['minecraft:dirt'], P['minecraft:stone'], P['minecraft:andesite'], P['minecraft:cobblestone']
SN, SD, WAT = P['minecraft:snow_block'], P['minecraft:sand'], P['minecraft:water']
SST = P['minecraft:sandstone']

# ---------------- fractal noise (bilinear-upsampled value noise) ----------------

def fbm(seed, octs=(3, 6, 12, 24, 48), weights=(1, .55, .3, .16, .08), size=500):
    total = np.zeros((size, size)); wsum = sum(weights)
    for o, w in zip(octs, weights):
        rng = np.random.default_rng(seed * 1000 + o)
        g = (rng.random((o, o)) * 255).astype(np.uint8)
        img = Image.fromarray(g).resize((size, size), Image.BICUBIC)
        total += w * (np.asarray(img, dtype=np.float64) / 255)
    return total / wsum

# ---------------- island mask ----------------
xs = np.arange(W)[None, :].astype(np.float64)
zs = np.arange(L)[:, None].astype(np.float64)
cx = cz = 250
dx = xs - cx; dz = zs - cz
r = np.sqrt(dx * dx + dz * dz)
ang = np.arctan2(dz, dx)

rng = np.random.default_rng(20260911)
radius = np.full((L, W), 234.0)
for k, amp in ((2, 9), (3, 7), (5, 5), (7, 3.2), (11, 2.0)):
    ph = rng.random() * 6.283
    radius = radius + amp * np.sin(ang * k + ph)
n_mask = (fbm(11, size=500) - 0.5) * 26
radius = radius + n_mask
mask = r <= radius
t = np.clip(r / np.maximum(radius, 1), 0, 1.4)

# ---------------- height field ----------------
SEA = 54
base = 60 + 16 * fbm(21) + 7 * fbm(22)
m1 = np.exp(-(((xs - 240) / 105) ** 2 + ((zs - 150) / 78) ** 2))
m2 = np.exp(-(((xs - 330) / 62) ** 2 + ((zs - 205) / 58) ** 2))
mnt = 82 * m1 * np.clip(fbm(23) * 1.35, .22, 1) ** 1.15 + 56 * m2 * np.clip(fbm(24) * 1.3, .25, 1)
h = np.where(mask, base + mnt, 0)

# ridged mountain detail
ridge = np.abs(fbm(25) - .5)
h = h - np.where(mask, 14 * np.clip(ridge * 2 - .3, 0, 1) * (mnt > 12), 0)

# river: ridge-crossing carve
rv = np.abs(fbm(26) - .5)
river = mask & (rv < .035) & (r < radius - 6) & (h < 118) & (h > SEA - 6)
h = np.where(river, np.minimum(h, SEA - 2), h)  # riverbed at 52
# carve a smooth V->U valley: lower banks proportional to closeness to river centerline
rvw = np.clip((.10 - rv) / .10, 0, 1)          # 1 at centerline -> 0 at .10
valley = mask & (r < radius - 6) & (h < 118) & (h > SEA)
h = np.where(valley, h * (1 - .55 * rvw ** 1.7 * ((h - SEA) / np.maximum(h - SEA, 1))), h)
h = np.where(river, np.minimum(h, SEA - 2), h)

# lake
lake = np.exp(-(((xs - 305) / 46) ** 2 + ((zs - 320) / 34) ** 2)) > .62
lake &= mask
h = np.where(lake, np.minimum(h, SEA - 4), h)

# mountain ponds
pond = (fbm(27) > .80) & mask & (h > 60) & (h < 84) & (r < radius - 8)
h = np.where(pond, np.minimum(h, SEA - 2), h)

# sea bays: rim dips
bay = mask & (r > radius - 13) & (fbm(28) > .72)
h = np.where(bay, np.minimum(h, SEA - 2 + 3 * fbm(29)), h)

h = np.round(h).astype(np.int64)
h = np.clip(h, 8, 200)

# IMPORTANT: all carving (rivers/lake/ponds/bays) is done above; only now
# derive the underside so river/lake beds have solid ground beneath them.
thick = (6 + (1 - t) ** 1.25 * 66 * (0.72 + 0.56 * fbm(31))).astype(np.int64)
spike = (fbm(32) > .74) & (t < .55)
thick = thick + spike * ((fbm(33) * 18).astype(np.int64))
u = np.maximum(h - thick, 7)
u = np.minimum(u, h - 2)

# ---------------- fill columns ----------------
grid = np.zeros((H, L, W), dtype=np.uint8)
fill_lo = np.maximum(u, 0)
hh = np.minimum(h, H - 1)
print("filling columns...")
patchnoise = fbm(34)
for y0 in range(0, H, 40):
    y1 = min(y0 + 40, H)
    yy = np.arange(y0, y1)[:, None, None]
    m = (yy >= fill_lo[None]) & (yy <= hh[None]) & mask[None]
    slab = grid[y0:y1]
    rock = np.where(np.broadcast_to(patchnoise[None] < .26, slab.shape), AN, S).astype(np.uint8)
    rock = np.where(np.broadcast_to(patchnoise[None] > .86, slab.shape), CO, rock)
    slab[m] = rock[m]
    grid[y0:y1] = slab

# ---------------- surface layers ----------------
surf = hh
# slope -> stone cliffs
gy, gx = np.gradient(h.astype(np.float64))
slope = np.abs(gx) + np.abs(gy)
cliff = mask & ((slope > 2.1) | (h >= 100))
snowy = mask & (h >= 116)

watercells = mask & (h < SEA)
# sand: underwater + beach ring near water
water_d = watercells.copy()
for _ in range(5):
    wd = water_d.copy()
    wd[:, :-1] |= water_d[:, 1:]; wd[:, 1:] |= water_d[:, :-1]
    wd[:-1, :] |= water_d[1:, :]; wd[1:, :] |= water_d[:-1, :]
    water_d = wd
beach = mask & (h <= SEA + 3) & water_d

desert = mask & (ang > -0.62) & (ang < 0.34) & (r < 172) & (h > SEA + 3) & ~cliff
desert_top3 = desert | (beach & ~desert)

# apply tops
top_y = hh
zz, xx = np.nonzero(mask)
tops = grid[top_y[zz, xx], zz, xx]
def set_top(sel_z, sel_x, blk, depth_=1, under=None):
    if not len(sel_z): return
    yy = top_y[sel_z, sel_x]
    for d in range(depth_ + 1):
        yv = yy - d
        ok = (yv >= fill_lo[sel_z, sel_x]) & (yv >= 0)
        if d == 0:
            grid[yv[ok], sel_z[ok], sel_x[ok]] = blk
        elif under is not None:
            grid[yv[ok], sel_z[ok], sel_x[ok]] = under

sel = tuple(np.nonzero(mask))
set_top(sel[0], sel[1], G)                      # default grass
snowsel = tuple(np.nonzero(snowy))
set_top(snowsel[0], snowsel[1], SN, 1, S)
cliffsel = tuple(np.nonzero(cliff & ~snowy))
set_top(cliffsel[0], cliffsel[1], S, 2)
# dirt under grass
grass = mask & ~snowy & ~cliff & ~desert_top3 & (h > SEA + 3)
gsel = np.nonzero(grass)
yy = top_y[gsel]
for d in (1, 2, 3):
    yv = yy - d
    ok = (yv >= fill_lo[gsel]) & (yv >= 0)
    grid[yv[ok], gsel[0][ok], gsel[1][ok]] = D if d < 3 else S
# desert sand
dsel = np.nonzero(desert_top3)
yy = top_y[dsel]
for d in range(4):
    yv = yy - d
    ok = (yv >= fill_lo[dsel]) & (yv >= 0)
    grid[yv[ok], dsel[0][ok], dsel[1][ok]] = SD if d < 3 else SST
# snow underlay
sssel = np.nonzero(snowy)
yy = top_y[sssel]
yv = yy - 1
ok = (yv >= fill_lo[sssel]) & (yv >= 0)
grid[yv[ok], sssel[0][ok], sssel[1][ok]] = S

# ---------------- water ----------------
print("water...")
for y0 in range(0, H, 40):
    y1 = min(y0 + 40, H)
    yy = np.arange(y0, y1)[:, None, None]
    m = (yy > hh[None]) & (yy <= SEA) & mask[None]
    slab = grid[y0:y1]
    slab[m] = WAT
    grid[y0:y1] = slab

# ---------------- rim waterfalls (limited, deterministic) ----------------
rim = mask & ~(np.roll(mask, 1, 0) & np.roll(mask, -1, 0) & np.roll(mask, 1, 1) & np.roll(mask, -1, 1))
rim_water = rim & (h <= SEA) & (fbm(36) > .62)
rz, rx = np.nonzero(rim_water)
print(f"rim waterfall columns: {len(rx)}")
for z, x in zip(rz, rx):
    bottom = max(u[z, x] - 6, 14)
    for y in range(h[z, x] - 1, bottom, -1):
        grid[y, z, x] = WAT

# ---------------- trees & flora ----------------
print("flora...")
rnd = np.random.default_rng(7)

def tree(x, z, y0, kind):
    if kind == 'spruce':
        ht = int(6 + rnd.random() * 5)
        for i in range(ht):
            if y0 + i < H: grid[y0 + i, z, x] = P['minecraft:spruce_log']
        for li, (rad, ly) in enumerate(((2, 2), (2, 4), (1, 6), (1, ht))):
            for ddx in range(-rad, rad + 1):
                for ddz in range(-rad, rad + 1):
                    if abs(ddx) + abs(ddz) > rad + 1: continue
                    yy2 = y0 + ly
                    if 0 <= yy2 < H and grid[yy2, z + ddz, x + ddx] == AIR and (ddx or ddz):
                        grid[yy2, z + ddz, x + ddx] = P['minecraft:spruce_leaves']
        grid[min(y0 + ht, H - 1), z, x] = P['minecraft:spruce_leaves']
    elif kind in ('oak', 'birch'):
        log = P['minecraft:oak_log'] if kind == 'oak' else P['minecraft:birch_log']
        lv = P['minecraft:oak_leaves'] if kind == 'oak' else P['minecraft:birch_leaves']
        ht = int(4 + rnd.random() * 3)
        for i in range(ht):
            if y0 + i < H: grid[y0 + i, z, x] = log
        for ddx in range(-2, 3):
            for ddz in range(-2, 3):
                for ddy in (0, 1):
                    yy2 = y0 + ht - 1 + ddy
                    if abs(ddx) + abs(ddz) + ddy <= 3 and 0 <= yy2 < H and grid[yy2, z + ddz, x + ddx] == AIR:
                        grid[yy2, z + ddz, x + ddx] = lv
    elif kind == 'cherry':
        ht = int(4 + rnd.random() * 3)
        for i in range(ht):
            if y0 + i < H: grid[y0 + i, z, x] = P['minecraft:cherry_log']
        for ddx in range(-3, 4):
            for ddz in range(-3, 4):
                for ddy in (-1, 0, 1):
                    yy2 = y0 + ht + ddy
                    if ddx * ddx + ddz * ddz * 1.3 + ddy * ddy * 1.6 <= 7 - ddy and 0 <= yy2 < H and grid[yy2, z + ddz, x + ddx] == AIR:
                        grid[yy2, z + ddz, x + ddx] = P['minecraft:cherry_leaves']

def free(x, z, y):
    if not (2 <= x < W - 2 and 2 <= z < L - 2): return False
    if grid[y, z, x] not in (G, SN, SD, S): return False
    if grid[y + 1, z, x] != AIR: return False
    return True

# spruce on mountain fringes
cnt = 0
while cnt < 130:
    x, z = int(rnd.random() * W), int(rnd.random() * L)
    if not mask[z, x]: continue
    y = hh[z, x]
    if 88 <= y <= 128 and free(x, z, y) and rnd.random() < .5:
        tree(x, z, y + 1, 'spruce'); cnt += 1
# oak/birch lowland forest
forest = fbm(41) > .56
cnt = 0
while cnt < 320:
    x, z = int(rnd.random() * W), int(rnd.random() * L)
    if not mask[z, x] or not forest[z, x]: continue
    y = hh[z, x]
    if SEA + 4 <= y <= 86 and free(x, z, y):
        tree(x, z, y + 1, 'oak' if rnd.random() < .55 else 'birch'); cnt += 1
# cherry grove sector
cnt = 0
while cnt < 55:
    x, z = int(rnd.random() * W), int(rnd.random() * L)
    if not mask[z, x]: continue
    aa = np.arctan2(z - cz, x - cx)
    rr = np.hypot(x - cx, z - cz)
    if not (2.05 <= aa <= 2.85 and 92 <= rr <= 185): continue
    y = hh[z, x]
    if SEA + 4 <= y <= 80 and free(x, z, y):
        tree(x, z, y + 1, 'cherry'); cnt += 1
# bamboo patch (SW)
cnt = 0
while cnt < 70:
    x = 150 + int(rnd.random() * 56)
    z = 315 + int(rnd.random() * 48)
    if not (0 <= x < W and 0 <= z < L and mask[z, x]): continue
    y = hh[z, x]
    if SEA + 4 <= y <= 82 and free(x, z, y):
        ht = int(4 + rnd.random() * 7)
        for i in range(ht):
            if y + i < H and grid[y + i, z, x] == AIR: grid[y + i, z, x] = P['minecraft:bamboo_block']
        cnt += 1
# cacti in desert
cnt = 0
while cnt < 30:
    x, z = int(rnd.random() * W), int(rnd.random() * L)
    if not desert[z, x] or not free(x, z, hh[z, x]): continue
    ht = int(2 + rnd.random() * 3)
    for i in range(ht):
        if hh[z, x] + 1 + i < H: grid[hh[z, x] + 1 + i, z, x] = P['minecraft:cactus']
    cnt += 1
# flower sprinkles (azalea bushes)
cnt = 0
while cnt < 160:
    x, z = int(rnd.random() * W), int(rnd.random() * L)
    if not mask[z, x]: continue
    y = hh[z, x]
    if grass[z, x] and free(x, z, y) and rnd.random() < .5:
        grid[y + 1, z, x] = P['minecraft:flowering_azalea_leaves'] if rnd.random() < .7 else P['minecraft:pink_terracotta']
        cnt += 1
# boulders
cnt = 0
while cnt < 40:
    x, z = int(rnd.random() * W), int(rnd.random() * L)
    if not mask[z, x]: continue
    y = hh[z, x]
    if ((86 <= y <= 110) or (SEA + 6 <= y <= 75 and rnd.random() < .2)) and free(x, z, y):
        rr2 = int(1 + rnd.random() * 2)
        for ddx in range(-rr2, rr2 + 1):
            for ddz in range(-rr2, rr2 + 1):
                for ddy in range(rr2 + 1):
                    if ddx * ddx + ddz * ddz + ddy * ddy <= rr2 * rr2 + 1:
                        yy2 = y + 1 + ddy
                        if 0 <= yy2 < H and grid[yy2, z + ddz, x + ddx] == AIR:
                            grid[yy2, z + ddz, x + ddx] = CO if rnd.random() < .4 else S
        cnt += 1

# cleanup: orphaned log columns (trunk segments with no leaves anywhere near)
LOGS = {P['minecraft:oak_log'], P['minecraft:birch_log'], P['minecraft:spruce_log'], P['minecraft:cherry_log']}
LEAVES = {P['minecraft:oak_leaves'], P['minecraft:birch_leaves'], P['minecraft:spruce_leaves'],
          P['minecraft:dark_oak_leaves'], P['minecraft:cherry_leaves']}
removed = 0
for z in range(2, L - 2):
    for x in range(2, W - 2):
        col = grid[:, z, x]
        y = 40
        while y < H - 1:
            if col[y] in LOGS:
                y0 = y
                while y < H - 1 and col[y] in LOGS:
                    y += 1
                seg = col[max(0, y0 - 2):min(H, y + 2)]
                has_leaf = any(col[yy] in LEAVES for yy in range(max(0, y0 - 3), min(H, y + 3)))
                near_leaf = False
                for zz2 in range(max(0, z - 3), min(L, z + 4)):
                    for xx2 in range(max(0, x - 3), min(W, x + 4)):
                        c2 = grid[:, zz2, xx2]
                        if c2[y0:min(H, y + 2)].max() if False else False:
                            pass
                # any leaf adjacent horizontally?
                for yy2 in range(max(0, y0 - 3), min(H, y + 3)):
                    if has_leaf: break
                    for zz2 in (z - 1, z + 1):
                        if 0 <= zz2 < L and grid[yy2, zz2, x] in LEAVES: has_leaf = True; break
                    for xx2 in (x - 1, x + 1):
                        if 0 <= xx2 < W and grid[yy2, z, xx2] in LEAVES: has_leaf = True; break
                if not has_leaf:
                    col[y0:y] = AIR
                    removed += (y - y0)
            else:
                y += 1
print("orphan trunk blocks removed:", removed)

nonair = int((grid != AIR).sum())
print(f"world blocks: {nonair:,} / {grid.size:,}")

# ---------------- save ----------------
np.savez_compressed('world_big.npz', grid=grid, palette=np.array(list(P.keys()), dtype=object))

def write_schem(path='nature-island_500.schem'):
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
        'Metadata': Compound({String('Name'): String('suifu-nature-island'), String('Author'): String('ISOLA World Studio')}),
    })
    f = nbtlib.File(); f.update(sch); f.root_name = 'Schematic'
    tmp = path + '.tmp'
    f.save(tmp, gzipped=True)
    payload = gzip.decompress(open(tmp, 'rb').read())
    os.unlink(tmp)
    with open(path, 'wb') as fh:
        fh.write(gzip.compress(payload, compresslevel=9, mtime=0))
    print("schem written:", os.path.getsize(path), "bytes")

write_schem()

# feature coordinates for cameras
peak = np.unravel_index(np.argmax(np.where(mask, h, 0)), h.shape)
print("PEAK:", int(peak[1]), int(peak[0]), "h=", int(h[peak]))
rw = np.nonzero(river & (h == SEA - 2))
if len(rw[0]):
    i = len(rw[0]) // 3
    print("RIVER:", int(rw[1][i]), int(rw[0][i]))
bw = np.nonzero(beach)
if len(bw[0]):
    i = int(len(bw[0]) * .6)
    print("BEACH:", int(bw[1][i]), int(bw[0][i]))
print("DONE")
