#!/usr/bin/env python3
"""
Build the 500x500 floating-archipelago world.

- Main Suifu island (from suifu-island_main253.glb; paths ~5 blocks) voxelized at center.
- 6 themed floating islets around it: cherry grove, bamboo, desert, snow,
  mushroom, flower meadow (+ stone-lantern path, farm, hot spring on main island).
- Saves world_500.npz (ids grid + palette) and suifu-island_500.schem (Sponge v2, 4671).
"""
import struct, json, gzip, hashlib, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

W = H = L = 500          # X, Y, Z
H = 230
AIR = 255

# ---------------- palette ----------------
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
N = {v: k for k, v in P.items()}
assert len(P) < 128  # single-byte varint

grid = np.full((H, L, W), AIR, dtype=np.uint8)

# ---------------- GLB loader ----------------

def load_prims(path):
    data = open(path, 'rb').read()
    clen = struct.unpack('<I', data[12:16])[0]
    obj = json.loads(data[20:20+clen].decode('utf-8'))
    off = 20 + clen
    blen = struct.unpack('<I', data[off:off+4])[0]
    binb = data[off+8:off+8+blen]
    M = np.array(obj['nodes'][0]['matrix'], dtype=np.float64).reshape(4, 4).T
    node_of_mesh = {}
    for nd in obj['nodes']:
        if 'mesh' in nd: node_of_mesh[nd['mesh']] = nd.get('name', '')
    out = []
    for mi, mesh in enumerate(obj['meshes']):
        for prim in mesh['primitives']:
            acc = obj['accessors'][prim['attributes']['POSITION']]
            bv = obj['bufferViews'][acc['bufferView']]
            pts = np.frombuffer(binb, dtype='<f4', count=acc['count']*3,
                                offset=bv.get('byteOffset', 0)+acc.get('byteOffset', 0)).reshape(-1,3,3).astype(np.float64)
            Pw = (M @ np.dstack([pts, np.ones(pts.shape[:2])]).transpose(0,2,1)).transpose(0,2,1)[..., :3]
            out.append((node_of_mesh.get(mi, 'mesh'), Pw))
    return out, obj

# ---------------- voxelize main island (vectorized) ----------------

def voxelize_main():
    prims, obj = load_prims('../suifu-island_main253.glb')
    allv = np.concatenate([p.reshape(-1,3) for _, p in prims])
    lo = allv.min(axis=0); hi = allv.max(axis=0)
    size = hi - lo
    s = 253.0 / max(size[0], size[2])          # blocks per scene unit
    cx, cz = (lo[0]+hi[0])/2, (lo[2]+hi[2])/2
    y0 = 70                                     # island base y in world
    print(f"scene bounds {size.round(1)}, scale {s:.3f} blocks/unit")

    MAT = {}
    def mkey(node):
        if node == 'Meadow_surface': return 'terrain'
        if node == 'Floating_rock_base': return 'rock'
        return node.split('_', 1)[1] if '_' in node else node
    rank_of = {'terrain': 10, 'rock': 20, 'stone': 20, 'timber': 25, 'trunk': 25,
               'wood': 30, 'lightwood': 30, 'roof': 30, 'roof2': 30, 'path': 40,
               'sand': 40, 'foam': 45, 'glass': 50, 'window': 55,
               'leaf1': 60, 'leaf2': 60, 'leaf3': 60, 'leaf4': 60, 'flower': 60, 'pink': 60,
               'reed': 60, 'water': 90}
    block_of = {
        'terrain': P['minecraft:grass_block'], 'rock': None,  # rock -> stone variants
        'wood': P['minecraft:oak_planks'], 'lightwood': P['minecraft:birch_planks'],
        'timber': P['minecraft:spruce_log'], 'roof': P['minecraft:spruce_planks'],
        'roof2': P['minecraft:dark_oak_planks'], 'glass': P['minecraft:glass'],
        'window': P['minecraft:glowstone'], 'stone': P['minecraft:cobblestone'],
        'path': P['minecraft:dirt_path'], 'sand': P['minecraft:sand'],
        'water': P['minecraft:water'], 'waterlight': P['minecraft:water'],
        'foam': P['minecraft:snow_block'], 'trunk': P['minecraft:oak_log'],
        'leaf1': P['minecraft:spruce_leaves'], 'leaf2': P['minecraft:oak_leaves'],
        'leaf3': P['minecraft:birch_leaves'], 'leaf4': P['minecraft:dark_oak_leaves'],
        'flower': P['minecraft:flowering_azalea_leaves'], 'pink': P['minecraft:pink_terracotta'],
        'reed': P['minecraft:oak_leaves'],
    }
    STONE_IDS = np.array([P['minecraft:stone'], P['minecraft:andesite'], P['minecraft:cobblestone'], P['minecraft:andesite']], dtype=np.uint8)

    pos_chunks, rank_chunks, name_chunks = [], [], []
    terr_top = np.full((L, W), -1, dtype=np.int64)   # per-column natural terrain top (meadow/rock)
    terr_bot = np.full((L, W), 10**9, dtype=np.int64)
    STEP = 0.6
    for node, Pw in prims:
        key = mkey(node)
        n = len(Pw)
        e0 = Pw[:,1]-Pw[:,0]; e1 = Pw[:,2]-Pw[:,0]
        maxe = np.maximum(np.linalg.norm(e0,axis=1), np.maximum(np.linalg.norm(Pw[:,2]-Pw[:,1],axis=1), np.linalg.norm(e0-e1,axis=1))) * s
        k = np.maximum(1, np.ceil(maxe/STEP).astype(np.int64))
        counts = k*k
        ti = np.repeat(np.arange(n), counts)
        csum = np.concatenate([[0], np.cumsum(counts)[:-1]])
        ctr = np.arange(len(ti)) - csum[ti]
        kk = k[ti]
        ii = ctr % kk; jj = ctr // kk
        valid = (ii + jj) < kk
        ti, ii, jj = ti[valid], ii[valid], jj[valid]
        u = (ii + .5)/k[ti]; v = (jj + .5)/k[ti]
        pts = Pw[ti,0] + e0[ti]*u[:,None] + e1[ti]*v[:,None]
        bx = np.clip(((pts[:,0]-cx)*s + W/2).astype(np.int64), 0, W-1)
        bz = np.clip(((pts[:,2]-cz)*s + L/2).astype(np.int64), 0, L-1)
        by = np.clip((y0 + (pts[:,1]-lo[1])*s).astype(np.int64), 0, H-1)
        pos = (by.astype(np.int64)*L + bz)*W + bx
        rank = rank_of.get(key, 35)
        if key == 'rock':
            hsh = (pos * 2654435761) & 0xFFFFFFFF
            nid = STONE_IDS[(hsh >> 24) % 4].astype(np.uint8)
            nid = np.where(((hsh >> 12) & 0xFF) > 60, P['minecraft:andesite'], nid).astype(np.uint8)
        else:
            nid = np.full(len(pos), block_of[key], dtype=np.uint8)
        pos_chunks.append(pos); rank_chunks.append(np.full(len(pos), rank, dtype=np.int16)); name_chunks.append(nid)
        if key in ('terrain', 'rock'):
            col = (bz.astype(np.int64) * W + bx)
            np.maximum.at(terr_top.reshape(-1), col, by)
            np.minimum.at(terr_bot.reshape(-1), col, by)
        del pts, bx, bz, by, pos, nid

    pos = np.concatenate(pos_chunks); rank = np.concatenate(rank_chunks); nid = np.concatenate(name_chunks)
    print(f"samples: {len(pos):,}")
    packed = pos * 128 + rank
    order = np.argsort(packed, kind='stable')
    packed = packed[order]; nid = nid[order]
    del order, pos_chunks, rank_chunks, name_chunks
    first = np.empty(len(packed), dtype=bool); first[0] = True
    np.not_equal(packed[1:], packed[:-1], out=first[1:])
    packed = packed[first]; nid = nid[first]
    del first
    pos = packed // 128; rank = (packed % 128).astype(np.uint8)
    by = (pos // (L*W)); bz = ((pos // W) % L); bx = (pos % W)
    ok = rank < grid[by, bz, bx]
    grid[by[ok], bz[ok], bx[ok]] = nid[ok]
    print(f"main island blocks: {len(pos):,}")
    return terr_top, terr_bot

# ---------------- helper: noise ----------------
_rng = np.random.default_rng(24)
def hnoise(x, y, z):
    h = (x*374761393 + y*668265263 + z*2147483647) & 0xFFFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0

def vnoise2(x, z, seed=0):
    h = (np.asarray(x, dtype=np.int64)*374761393 + np.asarray(z, dtype=np.int64)*668265263 + seed*97) & 0xFFFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF).astype(np.float64) / 65535.0

# ---------------- themed islets ----------------

def make_islet(cx, cz, ytop, R, theme):
    """Dome-topped, cone-bottomed floating islet with themed surface."""
    xs = np.arange(W); zs = np.arange(L)
    dx = xs[None, :] - cx; dz = zs[:, None] - cz
    r = np.sqrt(dx*dx + dz*dz)
    inside = r <= R
    t = 1 - (r/np.maximum(R, 1))**2          # 1 center -> 0 rim
    # 2D positional noise (NOT radius-based; radius noise draws concentric rings)
    hgt = np.where(inside, (8 + 8*t + 2.2*vnoise2(dx*3 + dz*131, dz*3 - dx*17, theme)).astype(int), 0)
    # 3x3 box smoothing for gentle rolling terrain (2 passes)
    for _ in range(2):
        pad = np.pad(hgt, 1, mode='edge')
        sm = np.zeros_like(hgt, dtype=np.float64)
        for oz_ in (0,1,2):
            for ox_ in (0,1,2):
                sm += pad[oz_:oz_+L, ox_:ox_+W]
        hgt = (sm/9).astype(int)
    hgt = np.clip(hgt, 2, 30)
    depth = np.where(inside, (R*0.9*(1 - (r/np.maximum(R,1))**1.4) + 4).astype(int), 0)   # cone depth
    # fill column solids
    for z, x in zip(*np.nonzero(inside)):
        top = ytop + hgt[z, x]
        bot = top - depth[z, x]
        grid[max(bot,0):top+1, z, x] = P['minecraft:stone']
    # theme surface
    for z, x in zip(*np.nonzero(inside)):
        top = ytop + hgt[z, x]
        rr = r[z, x] / R
        if theme == 1:   # cherry grove
            grid[top, z, x] = P['minecraft:grass_block']
            if top >= 1: grid[top-1, z, x] = P['minecraft:dirt']
        elif theme == 2: # bamboo
            grid[top, z, x] = P['minecraft:grass_block']
        elif theme == 3: # desert
            grid[top, z, x] = P['minecraft:sand']
            grid[top-1, z, x] = P['minecraft:sand']; grid[top-2, z, x] = P['minecraft:sandstone']
        elif theme == 4: # snow
            grid[top, z, x] = P['minecraft:snow_block']
            if rr > .55 and hnoise(x, top, z) > .5: grid[top, z, x] = P['minecraft:packed_ice']
        elif theme == 5: # mushroom
            grid[top, z, x] = P['minecraft:mycelium']
        elif theme == 6: # flower meadow
            if hnoise(x, top, z) > .55: grid[top, z, x] = P['minecraft:flowering_azalea_leaves']
            elif hnoise(x, top, z) > .45: grid[top, z, x] = P['minecraft:pink_terracotta']
            else: grid[top, z, x] = P['minecraft:grass_block']
        # rocky rim sprinkles
        if rr > .8 and hnoise(x, z, 99) > .6: grid[top, z, x] = P['minecraft:andesite']

def tree_cherry(cx, cz, ytop):
    h = int(4 + hnoise(cx, cz, 1)*3)
    for i in range(h): grid[ytop+i, cz, cx] = P['minecraft:cherry_log']
    ty = ytop + h
    for dx in range(-3, 4):
        for dz in range(-3, 4):
            for dy in range(-2, 3):
                d2 = dx*dx + dz*dz*1.4 + dy*dy*1.6
                if d2 <= 8.5 - (dy+2)*.6 and hnoise(cx+dx, cz+dz, 5+dy) > .12:
                    y = ty + dy
                    if 0 <= y < H and grid[y, cz+dz, cx+dx] == AIR:
                        grid[y, cz+dz, cx+dx] = P['minecraft:cherry_leaves']

def cactus(x, z, ytop):
    h = int(2 + hnoise(x, z, 3)*3)
    for i in range(h): grid[ytop+i, z, x] = P['minecraft:cactus']

def mushroom(x, z, ytop, red=True):
    h = int(3 + hnoise(x, z, 4)*4)
    for i in range(h): grid[ytop+i, z, x] = P['minecraft:mushroom_stem']
    cap = P['minecraft:red_mushroom_block'] if red else P['minecraft:brown?'.replace('?','')] if False else P['minecraft:red_mushroom_block']
    for dx in range(-2, 3):
        for dz in range(-2, 3):
            if abs(dx) + abs(dz) <= 3 and grid[ytop+h, z+dz, x+dx] == AIR:
                grid[ytop+h, z+dz, x+dx] = cap
    if grid[ytop+h+1, z, x] == AIR: grid[ytop+h+1, z, x] = cap

def bamboo(x, z, ytop):
    h = int(5 + hnoise(x, z, 6)*7)
    for i in range(h):
        if grid[ytop+i, z, x] == AIR: grid[ytop+i, z, x] = P['minecraft:bamboo_block']

def make_islet_decor(cx, cz, ytop, R, theme):
    n = int(R*R/18)
    for i in range(n):
        a = hnoise(i, theme, 11) * 6.283
        rr = R * (0.15 + 0.75*hnoise(i*3, theme, 13))
        x, z = int(cx + np.cos(a)*rr), int(cz + np.sin(a)*rr)
        if not (0 <= x < W and 0 <= z < L): continue
        col = grid[:, z, x]
        ys = np.nonzero(col != AIR)[0]
        if not len(ys): continue
        top = ys[-1]
        blk = grid[top, z, x]
        grassy = blk in (P['minecraft:grass_block'], P['minecraft:mycelium'], P['minecraft:flowering_azalea_leaves'])
        if theme == 1 and grassy: tree_cherry(x, z, top+1)
        elif theme == 2 and grassy and hnoise(x, z, 21) > .3: bamboo(x, z, top+1)
        elif theme == 3 and blk == P['minecraft:sand'] and hnoise(x, z, 22) > .75: cactus(x, z, top+1)
        elif theme == 5 and grassy and hnoise(x, z, 23) > .55: mushroom(x, z, top+1, red=hnoise(x, z, 24) > .4)

# ---------------- main-island decorations ----------------

def surface_at(x, z):
    ys = np.nonzero(grid[:, z, x] != AIR)[0]
    return ys[-1] if len(ys) else -1

def decorate_main():
    cx = W//2
    # --- find dirt_path blocks (main roads) for lantern placement
    pathmask = (grid == P['minecraft:dirt_path'])
    print("path blocks:", int(pathmask.sum()))
    count = 0
    for x in range(cx+16, W-6, 9):
        zs_on_path = np.nonzero(pathmask[:, x])[0]
        if not len(zs_on_path): continue
        zm = int(zs_on_path.mean())
        for side in (-5, 5):
            z = zm + side
            if not (0 < z < L-1): continue
            y = surface_at(x, z)
            if y > 0 and grid[y, z, x] == P['minecraft:grass_block']:
                grid[y+1, z, x] = P['minecraft:stone_bricks']
                grid[y+2, z, x] = P['minecraft:stone_bricks']
                grid[y+3, z, x] = P['minecraft:glowstone']
                count += 1
    print("lanterns:", count)

    def find_flat(fw, fl, x_range, z_range):
        """scan for fw x fl area of uniform-height grass; returns (x0, z0, y) or None"""
        best = None
        for z0 in z_range:
            for x0 in x_range:
                if x0+fw >= W or z0+fl >= L: continue
                tops = []
                ok = True
                for z in range(z0, z0+fl, 2):
                    for x in range(x0, x0+fw, 2):
                        y = surface_at(x, z)
                        if y < 1 or grid[y, z, x] != P['minecraft:grass_block']:
                            ok = False; break
                        tops.append(y)
                    if not ok: break
                if ok and len(tops) > (fw//2)*(fl//2)*0.95:
                    var = max(tops) - min(tops)
                    if var <= 1:
                        return x0, z0, int(np.median(tops))
                    if best is None or var < best[0]: best = (var, x0, z0, int(np.median(tops)))
        return None if best is None else (best[1], best[2], best[3])

    # --- farm: south-east of village
    spot = find_flat(36, 26, range(cx+25, cx+95, 4), range(L//2+25, L//2+90, 4))
    if spot:
        fx0, fz0, ybase = spot
        print(f"farm at {fx0},{fz0} y={ybase}")
        for z in range(fz0, fz0+26):
            for x in range(fx0, fx0+36):
                if x == fx0 or x == fx0+35 or z == fz0 or z == fz0+25:
                    grid[ybase+1, z, x] = P['minecraft:oak_log']
                elif (x - fx0) % 4 == 2:
                    grid[ybase+1, z, x] = P['minecraft:water']
                else:
                    grid[ybase+1, z, x] = P['minecraft:dirt']
                    if (z - fz0) % 3 != 1 and hnoise(x, z, 61) > .25:
                        grid[ybase+2, z, x] = P['minecraft:hay_block']
        for hx, hz in [(fx0+4, fz0+3), (fx0+31, fz0+22)]:
            grid[ybase+1, hz, hx] = P['minecraft:hay_block']
            grid[ybase+2, hz, hx] = P['minecraft:hay_block']
    # --- cherry grove: north-east meadow
    spot = find_flat(40, 30, range(cx+30, cx+100, 4), range(max(L//2-110,4), L//2-55, 4))
    if spot:
        gx0, gz0, _ = spot
        print(f"cherry grove at {gx0},{gz0}")
        for i in range(30):
            x = gx0 + int(hnoise(i, 71, 81) * 38)
            z = gz0 + int(hnoise(i, 72, 82) * 28)
            y = surface_at(x, z)
            if y > 0 and grid[y, z, x] == P['minecraft:grass_block']:
                tree_cherry(x, z, y+1)
    # --- hot spring: north-west (search flat grass pocket)
    sx, sz = 195, 248          # surveyed: flat, building-free meadow near lake north shore
    y = surface_at(sx, sz)
    print(f"hot spring at {sx},{sz} y={y}")
    for dz in range(-4, 5):
        for dx in range(-5, 6):
            if dx*dx/25 + dz*dz/16 <= 1:
                rim = abs(dx) == 5 or abs(dz) == 4
                grid[y, sz+dz, sx+dx] = P['minecraft:stone_bricks'] if rim else P['minecraft:water']
    for i in range(5):
        grid[y+1, sz-4+i, sx+6] = P['minecraft:birch_planks']

# ---------------- assemble world ----------------

print("voxelizing main island...")
terr_top, terr_bot = voxelize_main()
decorate_main()

print("placing islets...")
# around main island (center 250,250; main radius ~127)
islets = [
    (250+176, 250-96, 120, 38, 1, "cherry"),
    (250+196, 250+40, 100, 30, 2, "bamboo"),
    (250-186, 250-70, 108, 34, 3, "desert"),
    (250-176, 250+92, 128, 36, 4, "snow"),
    (250-30, 250-196, 96, 28, 5, "mushroom"),
    (250+40, 250+186, 140, 32, 6, "flower"),
]
for cx_, cz_, ytop_, R_, theme_, name_ in islets:
    make_islet(cx_, cz_, ytop_, R_, theme_)
    make_islet_decor(cx_, cz_, ytop_, R_, theme_)
    print(" islet:", name_)

# small floating rock shards for depth
for i in range(24):
    a = hnoise(i, 42, 51) * 6.283
    rr = 168 + hnoise(i, 43, 52) * 82
    x, z = int(W/2 + np.cos(a)*rr), int(L/2 + np.sin(a)*rr)
    y = int(46 + hnoise(i, 44, 53) * 128)
    r = int(1 + hnoise(i, 45, 54) * 3)
    for dz in range(-r, r+1):
        for dx in range(-r, r+1):
            d = dx*dx + dz*dz
            if d <= r*r and 0 <= x+dx < W and 0 <= z+dz < L:
                t = int((1 - (d/(r*r))**.5) * r * .8) + 1
                grid[y:y+t, z+dz, x+dx] = P['minecraft:stone'] if hnoise(x+dx, y, z+dz) > .4 else P['minecraft:andesite']

# ---------------- fill hollow island interior (rock cone was a shell mesh) ----------------
print("filling island interior...")
has_terr = terr_top > 0
tt = np.where(has_terr, terr_top, 0)          # (L, W)
tb = np.where(has_terr, terr_bot, 0)
print(f" terrain columns: {int(has_terr.sum()):,}  avg thickness: {float((tt-tb)[has_terr].mean()):.1f}")
_xa = np.arange(W, dtype=np.int64)[None, :]; _za = np.arange(L, dtype=np.int64)[:, None]
patch = ((_xa*374761393 + _za*668265263) & 0xFFFFFFFF) % 100
for y0 in range(0, H, 40):
    y1 = min(y0 + 40, H)
    ys = np.arange(y0, y1)[:, None, None]
    slab = grid[y0:y1]
    m = (ys > (tb + 1)[None, :, :]) & (ys < tt[None, :, :]) & (slab == AIR)
    if not m.any(): continue
    stone = P['minecraft:stone']; ande = P['minecraft:andesite']
    fill = np.where(np.broadcast_to(patch[None], slab.shape) < 24, ande, stone).astype(np.uint8)
    slab[m] = fill[m]
    grid[y0:y1] = slab

# ---------------- grass->dirt under grass (thin shell) + water settle ----------------
solid = grid != AIR
top_idx = np.where(solid, np.arange(H)[:, None, None], -1)
top = top_idx.max(axis=0)                    # per (z,x)
has = top >= 0
ys = np.clip(top, 0, H-1)
topblock = grid[ys, np.arange(L)[:, None], np.arange(W)[None, :]]
grassish = (topblock == P['minecraft:grass_block']) & has
zs, xs = np.nonzero(grassish)
for d in range(1, 3):
    yy = ys[zs, xs] - d
    m = (yy >= 0) & (grid[yy, zs, xs] == AIR)
    grid[yy[m], zs[m], xs[m]] = P['minecraft:dirt'] if d == 1 else P['minecraft:stone']

# water settle down (3 iterations)
for _ in range(3):
    water = (grid == P['minecraft:water'])
    below_air = np.zeros_like(water)
    below_air[:-1] = water[:-1] & (grid[1:] == AIR)
    if not below_air.any(): break
    ys2, zs2, xs2 = np.nonzero(below_air)
    grid[ys2+1, zs2, xs2] = P['minecraft:water']

nonair = int((grid != AIR).sum())
print(f"world blocks: {nonair:,} / {grid.size:,}")

# ---------------- save npz + schem ----------------
np.savez_compressed('world_500.npz', grid=grid, palette=np.array(list(P.keys()), dtype=object))

def write_schem():
    # grid uses 255 as air sentinel; palette air is id 0 -> remap before export!
    g = grid.copy()
    g[g == 255] = 0
    vals = g.reshape(-1)                  # (H, L, W): index = (y*L + z)*W + x == spec order
    pal_names = list(P.keys())
    pal_ids = list(P.values())
    import nbtlib
    from nbtlib import Compound, String, Int, Short, ByteArray
    sch = Compound({
        'Version': Int(2), 'DataVersion': Int(4671),
        'Width': Short(W), 'Height': Short(H), 'Length': Short(L),
        'Offset': nbtlib.IntArray([0, 0, 0]),
        'PaletteMax': Int(len(pal_names)),
        'Palette': Compound({String(k): Int(v) for k, v in P.items()}),
        'BlockData': ByteArray(vals.astype(np.int8)),
        'Metadata': Compound({String('Name'): String('suifu-island-500'), String('Author'): String('ISOLA World Studio')}),
    })
    # Sponge/FAWE format: ROOT tag is NAMED 'Schematic', fields directly inside
    f = nbtlib.File()
    f.update(sch)
    f.root_name = 'Schematic'
    tmp = 'suifu-island_500.schem.tmp'
    f.save(tmp, gzipped=True)
    payload = gzip.decompress(open(tmp, 'rb').read())
    os.unlink(tmp)
    with open('suifu-island_500.schem', 'wb') as fh:
        fh.write(gzip.compress(payload, compresslevel=9, mtime=0))
    print("schem written:", os.path.getsize('suifu-island_500.schem'), "bytes")

write_schem()
print("done")
