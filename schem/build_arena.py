#!/usr/bin/env python3
"""
Colosseum-style PvP arena generator -> Sponge v2 schem (MC 1.21.11, DV 4671).

Ellipse plan (Roman amphitheatre): sandy arena floor r 11.5, four seating
tiers (cavea), podium wall, outer wall with arch storeys + attic, one
collapsed ruin sector, four gates.  Palette: mud bricks, packed mud,
tuff / tuff bricks (the real thing's dark tufo), cut/smooth sandstone
(travertine), stone bricks, cobble rubble.

Scale: spawn plaza is right outside the east gate; centre is a 28-block
sprint from spawn (~5 s at 5.6 blocks/s sprint speed).
Output: colosseum_arena.schem + world_arena.npz
"""
import os, gzip
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

# ---------------- palette ----------------
P = {'minecraft:air': 0}
def add(name):
    if name not in P:
        P[name] = len(P)
    return P[name]

AIR = add('minecraft:air')
MB   = add('minecraft:mud_bricks')            # warm brown brick
PM   = add('minecraft:packed_mud')            # darker brown
TUF  = add('minecraft:tuff')                  # grey-brown (tufo!)
TB   = add('minecraft:tuff_bricks')
PT   = add('minecraft:polished_tuff')
CHT  = add('minecraft:chiseled_tuff')
CS   = add('minecraft:cut_sandstone')         # pale travertine
SS   = add('minecraft:smooth_sandstone')
CHS  = add('minecraft:chiseled_sandstone')
SAND = add('minecraft:sand')
SB   = add('minecraft:stone_bricks')
SBX  = add('minecraft:cracked_stone_bricks')
SBM  = add('minecraft:mossy_stone_bricks')
COB  = add('minecraft:cobblestone')
MCOB = add('minecraft:mossy_cobblestone')
GRV  = add('minecraft:gravel')
AND  = add('minecraft:andesite')
PAND = add('minecraft:polished_andesite')
LOG  = add('minecraft:stripped_spruce_log')   # gates / masts
RWOOL= add('minecraft:red_wool')              # banners
WWOOL= add('minecraft:white_wool')
YWOOL= add('minecraft:yellow_wool')
GLOW = add('minecraft:glowstone')

# ---------------- geometry (absolute block radii from centre) ----------------
H, L, W = 46, 104, 120
CX, CZ = 60.0, 52.0
A, B = 26.5, 22.0          # outer wall face semi-axes (x, z)

R_FLOOR = 11.5             # arena sand edge
R_POD   = 13.0             # podium outer face
R_CAVEA = 21.0             # top of seating
R_W0    = 22.0             # wall inner face
R_WI1   = 23.5             # inner leaf outer face
R_WO0   = 25.5             # outer leaf inner face   (corridor 23.5..25.5)
# wall outer face = A / B

def dnorm(xs, zs):
    return np.sqrt(((xs - CX) / A) ** 2 + ((zs - CZ) / B) ** 2)

xx = np.arange(W)[None, :]
zz = np.arange(L)[:, None]
dmap = dnorm(xx, zz)                                   # 1.0 at wall face
a2 = np.arctan2(zz - CZ, xx - CX)                      # angle map
rng = np.random.default_rng(44)
grid = np.zeros((H, L, W), np.uint8)

D_FLOOR, D_POD = R_FLOOR / A, R_POD / A
D_CAVEA, D_WALL0 = R_CAVEA / A, R_W0 / A
D_WI1, D_WO0 = R_WI1 / A, R_WO0 / A

FLOOR_Y = 10                 # arena floor surface y
G_Y = 8                      # terrace paving y

# ---------------- 1. terrace / ground ----------------
base = dmap <= 1.06
grid[0:G_Y + 1][:, base] = AND
pav = rng.random(dmap.shape)
p2 = rng.random(dmap.shape)
surf = base
grid[G_Y][surf & (pav < .5)] = PAND
grid[G_Y][surf & (pav < .5) & (p2 < .3)] = COB
grid[G_Y][surf & (pav >= .5) & (pav < .78)] = COB
grid[G_Y][surf & (pav >= .78) & (pav < .86)] = MCOB
grid[G_Y][surf & (pav >= .86) & (pav < .92)] = GRV

# ---------------- 2. arena floor ----------------
fl = dmap <= D_FLOOR
grid[FLOOR_Y][fl] = SAND
grid[FLOOR_Y - 1][fl] = SS
r_px = np.sqrt((xx - CX) ** 2 + (zz - CZ) ** 2)
grid[FLOOR_Y][fl & (np.abs(r_px - 4.5) < .8)] = SB
grid[FLOOR_Y][fl & (r_px < 3.4) & (rng.random(dmap.shape) < .5)] = SBX
for k in range(8):
    th = k * np.pi / 4
    for rr in np.arange(5.5, 11.0, .55):
        x, z = CX + rr * np.cos(th), CZ + rr * np.sin(th)
        xi, zi = int(round(x)), int(round(z))
        if grid[FLOOR_Y, zi, xi] == SAND:
            grid[FLOOR_Y, zi, xi] = SB if (int(rr * 2) % 2) else SBX

# ---------------- 3. podium wall ----------------
pod = (dmap > D_FLOOR) & (dmap <= D_POD)
ph = np.where(rng.random(dmap.shape) < .12, 3, 2)
for y in range(FLOOR_Y + 1, FLOOR_Y + 4):
    sel = pod & (y <= FLOOR_Y + ph)
    grid[y][sel] = MB
idx_pod = np.nonzero(pod)
for z, x in zip(*idx_pod):
    a3 = abs((a2[z, x] % (np.pi / 2)) - np.pi / 4)
    if a3 < .022 and grid[FLOOR_Y + 2, z, x] == MB:
        grid[FLOOR_Y + 2, z, x] = CHS

# ---------------- 4. seating (cavea) ----------------
seat = (dmap > D_POD) & (dmap <= D_CAVEA)
tier = np.clip(np.floor((dmap - D_POD) / ((D_CAVEA - D_POD) / 4)).astype(int), 0, 3)
aisle_ang = np.array([k * np.pi / 4 for k in range(8)])
a2p = np.abs(((a2[:, :, None] - aisle_ang[None, None, :] + np.pi) % (2 * np.pi)) - np.pi)
is_aisle = a2p.min(axis=2) < .05
for z, x in zip(*np.nonzero(seat)):
    t = tier[z, x]
    ytop = FLOOR_Y + 1 + t
    # solid Roman-concrete mass: fill from the terrace up to the seat surface
    for yy in range(G_Y + 1, ytop):
        grid[yy, z, x] = CS if rng.random() < .8 else SB
    grid[ytop, z, x] = CS
    grid[ytop - 1, z, x] = CS if rng.random() < .7 else SB
    if is_aisle[z, x]:
        grid[ytop, z, x] = SBM if rng.random() < .15 else SB
prom = (dmap > D_CAVEA) & (dmap < D_WALL0)
grid[FLOOR_Y + 4][prom] = CS
grid[FLOOR_Y + 3][prom] = SB

# ---------------- 5. outer wall with arches ----------------
NARC = 40
u = (a2 + np.pi) / (2 * np.pi) * NARC
kunit = np.floor(u).astype(int) % NARC
fu = u - np.floor(u)
OPEN = fu < .52
STOREY = [(10, 15), (17, 22), (24, 26)]
ATTIC0, ATTIC1 = 28, 31
R3 = (kunit >= 12) & (kunit <= 18)        # ruined sector: attic + 3rd gone
R2 = (kunit >= 13) & (kunit <= 17)        # 2nd storey partially gone

in_leaf  = (dmap >= D_WALL0) & (dmap <= D_WI1)
out_leaf = (dmap >= D_WO0) & (dmap <= 1.0)
corr     = (dmap > D_WI1) & (dmap < D_WO0)
wall_cols = in_leaf | corr | out_leaf

for y in range(G_Y + 1, ATTIC1 + 1):
    grid[y][wall_cols] = TB
face = out_leaf & (dmap >= .965)
for y in range(G_Y + 1, ATTIC1 + 1):
    band = ((y // 3) % 2 == 0)
    grid[y][face & band] = CS
    grid[y][face & ~band] = TB
# weathering
wpts = np.nonzero(wall_cols)
for (z, x), s in zip(zip(*wpts), rng.random(len(wpts[0])) < .06):
    if s:
        y = int(rng.integers(G_Y + 1, ATTIC1 + 1))
        grid[y, z, x] = SBX if grid[y, z, x] != CS else SS

for si, (y0, y1) in enumerate(STOREY):
    ah = y1 - y0
    for y in range(y0, y1 + 1):
        op = OPEN.copy()
        if si < 2:
            frac = (y - y0) / max(ah - 1, 1)
            if frac > .62:
                # arch top: solid corner must connect to the pier so nothing floats
                op = OPEN & (fu > .12) & (fu < .52)
        if si == 2:
            op = OPEN & (fu > .18) & (fu < .34)
            if y > y0 + 2:
                op = np.zeros_like(op)
            op = op | R3                      # ruin sector: 3rd storey collapsed
        if si == 1:
            op = op | R2                      # ruin sector: 2nd storey partly gone
        carve = np.zeros_like(op)
        carve[in_leaf | out_leaf] = op[in_leaf | out_leaf]
        carve[corr] = True
        grid[y][carve] = AIR

# attic + cornice
for y in range(ATTIC0, ATTIC1 + 1):
    grid[y][wall_cols & ~R3] = TB if y < ATTIC1 else PT
corn = out_leaf & (dmap >= .98) & ~R3
grid[ATTIC1 + 1][corn] = CS
grid[ATTIC1][corn & (kunit % 2 == 0)] = CS
# banner wool on attic
for k in range(0, NARC, 5):
    if 12 <= k <= 18: continue
    sel = (kunit == k) & (dmap >= .93) & (dmap <= 1.0)
    grid[ATTIC0 + 1][sel] = RWOOL if k % 10 == 0 else WWOOL
# pilasters between arches
pil = out_leaf & (dmap >= .985) & ~OPEN
grid[G_Y + 1:22][:, pil] = CS

# ---------------- 6. gates (E/N/W/S) ----------------
gate_ang = (0, np.pi / 2, np.pi, -np.pi / 2)
for th in gate_ang:
    dxg, dzg = np.cos(th), np.sin(th)
    ux, uz = -dzg, dxg
    for t in np.arange(R_POD * .5, (A + 3.5) * 1.02, .3):
        px, pz = CX + t * dxg, CZ + t * dzg
        for w in (-2.5, -1.5, -0.5, 0.5, 1.5, 2.5):
            xxp = int(round(px + w * ux)); zzp = int(round(pz + w * uz))
            if not (0 <= xxp < W and 0 <= zzp < L): continue
            if dmap[zzp, xxp] < D_FLOOR: continue
            grid[FLOOR_Y:FLOOR_Y + 6, zzp, xxp] = AIR
            grid[FLOOR_Y - 1, zzp, xxp] = SS   # flush with plaza level (y8 stand)

# gate lintels / keystone / glowstone soffits
a2g = np.abs(((a2[:, :, None] - np.array(gate_ang)[None, None, :] + np.pi) % (2 * np.pi)) - np.pi).min(axis=2)
lintel = wall_cols & (a2g < .085)
grid[FLOOR_Y + 6][lintel] = CHS
grid[FLOOR_Y + 7][lintel & (dmap >= .9)] = CS
glow_sel = lintel & (out_leaf | in_leaf) & (kunit % 2 == 0)
grid[FLOOR_Y + 4][glow_sel] = GLOW
grid[FLOOR_Y + 6][lintel & (dmap >= .96)] = CHS

# ---------------- 7. spawn plaza (east gate, 28 blocks from centre) ----------------
sx, sz = CX + 28.0, CZ
print("spawn at (%d,%d) -> centre 28 blocks, sprint ~5.0s" % (sx, sz))
pl = (np.hypot(xx - sx, zz - sz) < 5.4) & base & (dmap > 1.0)
grid[G_Y][pl & (rng.random(dmap.shape) < .8)] = PAND
grid[G_Y][pl & (rng.random(dmap.shape) >= .8)] = COB
for off in (-3, 3):
    mz = int(round(sz + off)); mx = int(round(sx))
    if dmap[mz, mx] <= 1.0: continue
    for y in range(G_Y + 1, G_Y + 6):
        grid[y, mz, mx] = LOG
    grid[G_Y + 6, mz, mx] = RWOOL if off < 0 else WWOOL
    grid[G_Y, mz, mx] = PT

# ---------------- 8. ruin rubble ----------------
rzone = (kunit >= 11) & (kunit <= 19) & (dmap > .72) & (dmap < 1.25)
rpts = np.nonzero(rzone & (rng.random(dmap.shape) < .16))
for z, x in zip(*rpts):
    if dmap[z, x] > 1.0 and base[z, x]:
        hh = int(rng.integers(1, 3))
        for i in range(hh):
            blk = [MCOB, COB, MB, SBX, GRV][int(rng.integers(0, 5))]
            grid[G_Y + 1 + i, z, x] = blk
    else:
        if grid[FLOOR_Y + 4, z, x] == AIR and grid[FLOOR_Y, z, x] != AIR and rng.random() < .5:
            grid[FLOOR_Y + 1, z, x] = MB if rng.random() < .6 else SBX

# ---------------- 9. masts outside N/S gates ----------------
for th, col in ((np.pi / 2, YWOOL), (-np.pi / 2, RWOOL)):
    gx = CX + (A + 2.5) * np.cos(th); gz = CZ + (B + 2.5) * np.sin(th)
    mxx, mzz = int(round(gx)), int(round(gz))
    if not (0 <= mxx < W and 0 <= mzz < L): continue
    for y in range(G_Y + 1, G_Y + 5):
        grid[y, mzz, mxx] = LOG
    grid[G_Y + 5, mzz, mxx] = col

print("blocks:", int((grid != AIR).sum()))
np.savez_compressed('world_arena.npz', grid=grid, palette=np.array(list(P.keys()), dtype=object))

# ---------------- write schem ----------------
def write_schem(path='colosseum_arena.schem'):
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
        'Metadata': Compound({String('Name'): String('colosseum-pvp-arena'), String('Author'): String('ISOLA World Studio')}),
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
print("DONE")
