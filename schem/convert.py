#!/usr/bin/env python3
"""
suifu island GLB -> Sponge v2 .schem converter.

Pipeline (mirrors ObjToSchematic conceptually):
  1. Parse GLB (JSON + BIN chunks), build world-space triangle soup per primitive
     with material identity taken from node names ("architecture_stone" -> "stone").
  2. Voxelize by dense barycentric sampling into a W x H x L grid.
  3. Natural Minecraft block mapping (grass/dirt/stone ground, logs/planks/leaves,
     glowstone windows, water, dirt paths) + solid island fill under terrain.
  4. Export gzipped NBT Sponge v2 (Width/Height/Length, Palette, varint BlockData).

Usage: python3 convert.py <in.glb> <out.schem>
"""
import struct, json, sys, gzip, hashlib
import numpy as np

# ---------------- GLB parsing ----------------

def load_primitives(path):
    data = open(path, 'rb').read()
    magic, version, total = struct.unpack('<III', data[:12])
    assert magic == 0x46546c67, 'not a GLB'
    clen, ctype = struct.unpack('<II', data[12:20])
    obj = json.loads(data[20:20+clen].decode('utf-8'))
    off = 20 + clen
    blen, btype = struct.unpack('<II', data[off:off+8])
    binchunk = data[off+8:off+8+blen]

    # node matrix (single root transform in our files)
    M = np.array(obj['nodes'][0].get('matrix', [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]), dtype=np.float64).reshape(4,4).T
    node_of_mesh = {}
    for nd in obj['nodes']:
        if 'mesh' in nd:
            node_of_mesh[nd['mesh']] = nd.get('name', f"mesh{nd['mesh']}")

    prims = []
    for mi, mesh in enumerate(obj['meshes']):
        node_name = node_of_mesh.get(mi, f'mesh{mi}')
        for prim in mesh['primitives']:
            acc = obj['accessors'][prim['attributes']['POSITION']]
            bv = obj['bufferViews'][acc['bufferView']]
            pts = np.frombuffer(binchunk, dtype='<f4', count=acc['count']*3,
                                offset=bv.get('byteOffset',0)+acc.get('byteOffset',0)).reshape(-1,3).astype(np.float64)
            P = (M @ np.hstack([pts, np.ones((len(pts),1))]).T).T[:, :3].reshape(-1, 3, 3)

            cols = None
            if 'COLOR_0' in prim['attributes']:
                cacc = obj['accessors'][prim['attributes']['COLOR_0']]
                cbv = obj['bufferViews'][cacc['bufferView']]
                cols = np.frombuffer(binchunk, dtype='<f4', count=cacc['count']*3,
                                     offset=cbv.get('byteOffset',0)+cacc.get('byteOffset',0)).reshape(-1,3)
            prims.append({'node': node_name, 'P': P, 'cols': cols})
    return prims

# ---------------- block mapping ----------------

# material key (from node name suffix) -> (block, rank) ; lower rank wins a voxel tie
MAT_BLOCK = {
    'wood':       ('minecraft:oak_planks', 30),
    'lightwood':  ('minecraft:birch_planks', 30),
    'timber':     ('minecraft:spruce_log', 25),
    'roof':       ('minecraft:spruce_planks', 30),
    'roof2':      ('minecraft:dark_oak_planks', 30),
    'glass':      ('minecraft:glass', 50),
    'window':     ('minecraft:glowstone', 55),
    'stone':      ('minecraft:cobblestone', 20),
    'path':       ('minecraft:dirt_path', 40),
    'sand':       ('minecraft:sand', 40),
    'trunk':      ('minecraft:oak_log', 25),
    'leaf1':      ('minecraft:spruce_leaves', 60),
    'leaf2':      ('minecraft:oak_leaves', 60),
    'leaf3':      ('minecraft:birch_leaves', 60),
    'leaf4':      ('minecraft:dark_oak_leaves', 60),
    'flower':     ('minecraft:flowering_azalea_leaves', 60),
    'pink':       ('minecraft:pink_terracotta', 60),
    'reed':       ('minecraft:oak_leaves', 60),
    'water':      ('minecraft:water', 90),
    'waterlight': ('minecraft:water', 90),
    'foam':       ('minecraft:snow_block', 45),
}
STONE_VARIANTS = ['minecraft:stone', 'minecraft:andesite', 'minecraft:cobblestone', 'minecraft:stone']
BLOCK_RGB = {
    'minecraft:grass_block': (124,168,82), 'minecraft:dirt': (134,96,67),
    'minecraft:stone': (125,125,125), 'minecraft:andesite': (136,136,137),
    'minecraft:cobblestone': (110,110,110), 'minecraft:oak_planks': (162,130,78),
    'minecraft:birch_planks': (192,175,121), 'minecraft:spruce_planks': (114,84,48),
    'minecraft:dark_oak_planks': (66,43,20), 'minecraft:spruce_log': (58,37,16),
    'minecraft:oak_log': (109,85,50), 'minecraft:glass': (200,230,240),
    'minecraft:glowstone': (252,217,137), 'minecraft:dirt_path': (148,122,65),
    'minecraft:water': (63,118,228), 'minecraft:snow_block': (249,255,254),
    'minecraft:spruce_leaves': (52,90,60), 'minecraft:oak_leaves': (90,128,54),
    'minecraft:birch_leaves': (129,164,90), 'minecraft:dark_oak_leaves': (72,116,74),
    'minecraft:flowering_azalea_leaves': (150,120,150), 'minecraft:pink_terracotta': (161,102,94),
    'minecraft:sand': (219,207,163),
}

def material_key(node_name):
    if node_name == 'Meadow_surface': return 'terrain'
    if node_name == 'Floating_rock_base': return 'rock'
    if '_' in node_name: return node_name.split('_', 1)[1]
    return node_name

def stable_noise(ix, iy, iz):
    h = hashlib.sha1(f"{ix},{iy},{iz}".encode()).digest()
    return h[0] / 255.0

# ---------------- voxelize ----------------

def voxelize(prims, pad=2):
    allP = np.concatenate([p['P'].reshape(-1,3) for p in prims])
    lo = allP.min(axis=0); hi = allP.max(axis=0)
    W = int(np.ceil(hi[0]-lo[0])) + pad*2
    L = int(np.ceil(hi[2]-lo[2])) + pad*2
    H = int(np.ceil(hi[1]-lo[1])) + pad
    ox, oy, oz = lo[0]-pad, lo[1]-pad, lo[2]-pad
    grid = np.full((H, L, W), 255, dtype=np.uint8)     # 255 = air, else rank
    names = {}                                          # rank -> block name (fixed per rank? no, store per-voxel name idx)
    namegrid = np.empty((H, L, W), dtype=object)

    STEP = 0.4
    for p in prims:
        key = material_key(p['node'])
        P = p['P']; n = len(P)
        e0 = P[:,1]-P[:,0]; e1 = P[:,2]-P[:,0]
        maxedge = np.maximum(np.linalg.norm(e0,axis=1), np.maximum(np.linalg.norm(P[:,2]-P[:,1],axis=1), np.linalg.norm(e0-e1,axis=1)))
        k = np.maximum(1, np.ceil(maxedge/STEP).astype(int))
        kmax = int(k.max())
        counts = k * k
        ti = np.repeat(np.arange(n), counts)
        csum = np.concatenate([[0], np.cumsum(counts)[:-1]])
        ctr = np.arange(len(ti)) - csum[ti]
        kk = k[ti]
        ii = ctr % kk; jj = ctr // kk
        valid = (ii + jj) < kk
        ti, ii, jj = ti[valid], ii[valid], jj[valid]
        u = (ii + 0.5) / k[ti]; v = (jj + 0.5) / k[ti]
        pts = P[ti,0] + e0[ti]*u[:,None] + e1[ti]*v[:,None]
        ix = np.clip(((pts[:,0]-ox)).astype(int), 0, W-1)
        iy = np.clip(((pts[:,1]-oy)).astype(int), 0, H-1)
        iz = np.clip(((pts[:,2]-oz)).astype(int), 0, L-1)

        if key == 'terrain':
            rank, blk = 10, 'minecraft:grass_block'
        elif key == 'rock':
            rank, blk = 20, None   # per-voxel stone variant
        else:
            blk, rank = MAT_BLOCK.get(key, ('minecraft:stone', 35))

        for x, y, z in zip(ix, iy, iz):
            if grid[y,z,x] == 255 or rank < grid[y,z,x]:
                grid[y,z,x] = rank
                if blk is None:  # rock: pick natural stone variant deterministically
                    r = stable_noise(x,y,z)
                    namegrid[y,z,x] = STONE_VARIANTS[int(r*3.999) % 4] if r > 0.35 else 'minecraft:andesite'
                else:
                    namegrid[y,z,x] = blk
    return grid, namegrid, (W, H, L), (ox, oy, oz)

# ---------------- natural fill passes ----------------

def natural_fill(grid, namegrid):
    H, L, W = grid.shape
    AIR = 255
    GRASS = 'minecraft:grass_block'; DIRT = 'minecraft:dirt'; STONE = 'minecraft:stone'
    solid = grid != AIR
    watermask = np.zeros_like(solid)
    for y in range(H):
        watermask[y] |= (namegrid[y] == 'minecraft:water')

    # 1) solid columns where the top block is terrain (grass) or bare rock
    for z in range(L):
        for x in range(W):
            col = solid[:, z, x] & ~watermask[:, z, x]
            if not col.any(): continue
            ys = np.nonzero(col)[0]
            top, bot = ys[-1], ys[0]
            topblk = namegrid[top, z, x]
            if topblk == GRASS:
                namegrid[top, z, x] = GRASS
                for d in range(1, 4):
                    y = top - d
                    if y < bot: break
                    namegrid[y, z, x] = DIRT if d < 3 else STONE
                    grid[y, z, x] = 21
                for y in range(top-4, bot-1, -1):
                    if y < 0: break
                    namegrid[y, z, x] = STONE; grid[y, z, x] = 21
            elif topblk in ('minecraft:stone', 'minecraft:andesite', 'minecraft:cobblestone'):
                for y in range(top-1, bot, -1):
                    if namegrid[y, z, x] in (None,) or grid[y, z, x] == AIR:
                        namegrid[y, z, x] = STONE; grid[y, z, x] = 21

    # 2) water: pour down up to 3 blocks from each water voxel
    for _ in range(3):
        moved = False
        for y in range(H-1):
            wm = (namegrid[y] == 'minecraft:water')
            below_air = (grid[y+1] == AIR)
            add = wm & below_air
            if add.any():
                zs, xs = np.nonzero(add)
                namegrid[y+1, zs, xs] = 'minecraft:water'
                grid[y+1, zs, xs] = 90
                moved = True
        if not moved: break

    # 3) grass dies under blocks: if grass has solid right above -> dirt
    for y in range(H-1):
        covered = (namegrid[y] == GRASS) & (grid[y+1] != AIR) & (namegrid[y+1] != 'minecraft:water')
        if covered.any():
            zs, xs = np.nonzero(covered)
            namegrid[y, zs, xs] = DIRT

# ---------------- sponge v2 export ----------------

def write_schem(namegrid, dims, out_path, dataversion=3465):
    W, H, L = dims
    used = sorted({n for n in namegrid.ravel() if n is not None})
    if 'minecraft:air' not in used:
        used.append('minecraft:air')
    palette = {n: i for i, n in enumerate(used)}
    blockdata = bytearray()
    for y in range(H):
        for z in range(L):
            for x in range(W):
                n = namegrid[y, z, x]
                idx = palette[n] if n is not None else palette['minecraft:air']
                while True:
                    b = idx & 0x7F
                    idx >>= 7
                    if idx:
                        blockdata.append(b | 0x80)
                    else:
                        blockdata.append(b)
                        break

    import nbtlib
    from nbtlib import Compound, String, Int, Short, ByteArray
    sch = Compound({
        'Version': Int(2),
        'DataVersion': Int(dataversion),
        'Width': Short(W), 'Height': Short(H), 'Length': Short(L),
        'Offset': nbtlib.IntArray([0, 0, 0]),
        'PaletteMax': Int(len(palette)),
        'Palette': Compound({String(k): Int(v) for k, v in palette.items()}),
        'BlockData': ByteArray(np.frombuffer(bytes(blockdata), dtype=np.int8)),
        'Metadata': Compound({
            String('Name'): String('suifu-island'),
            String('Author'): String('ISOLA World Studio'),
        }),
    })
    f = nbtlib.File({'Schematic': sch})
    f.save(out_path, gzipped=True)
    return palette

# ---------------- previews & stats ----------------

def previews(namegrid, dims, png_map, png_slice):
    from PIL import Image
    W, H, L = dims
    img = np.zeros((L, W, 3), dtype=np.uint8)
    for z in range(L):
        for x in range(W):
            for y in range(H-1, -1, -1):
                n = namegrid[y, z, x]
                if n is not None:
                    img[z, x] = BLOCK_RGB.get(n, (255,0,255))
                    break
    Image.fromarray(img).resize((W*6, L*6), Image.NEAREST).save(png_map)

    cy = L // 2
    img2 = np.zeros((H, W, 3), dtype=np.uint8)
    for y in range(H):
        for x in range(W):
            n = None
            for dz in range(0, 3):
                if namegrid[y, min(cy+dz, L-1), x] is not None:
                    n = namegrid[y, min(cy+dz, L-1), x]; break
            img2[H-1-y, x] = BLOCK_RGB.get(n, (255,255,255)) if n else (222,238,245)
    Image.fromarray(img2).resize((W*6, H*6), Image.NEAREST).save(png_slice)

def block_stats(namegrid):
    vals, counts = np.unique(np.array([n for n in namegrid.ravel() if n is not None], dtype=object), return_counts=True)
    pairs = sorted(zip(counts, vals), reverse=True)
    return pairs

def main():
    inp, outp = sys.argv[1], sys.argv[2]
    base = outp.rsplit('.', 1)[0]
    prims = load_primitives(inp)
    print(f"loaded {len(prims)} primitives")
    grid, namegrid, dims, origin = voxelize(prims)
    W, H, L = dims
    print(f"voxel grid: {W} x {H} x {L}")
    natural_fill(grid, namegrid)
    palette = write_schem(namegrid, dims, outp)
    previews(namegrid, dims, base + '_map.png', base + '_slice.png')
    total = int((namegrid != None).sum())
    print(f"blocks: {total:,}")
    for c, n in block_stats(namegrid)[:12]:
        print(f"  {n}: {c:,}")
    print(f"wrote {outp}")

if __name__ == '__main__':
    main()
