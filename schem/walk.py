#!/usr/bin/env python3
"""
First-person 'walk-around' renderer with real Minecraft 1.21.11 textures.
True voxel raycasting (Amanatides-Woo DDA), texture-mapped faces, face
lighting + distance fog. Usage inside script: edit the SHOTS list.
"""
import os
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
TEXDIR = 'textures'
OUTDIR = '../renders'
os.makedirs(OUTDIR, exist_ok=True)

# ---------------- world ----------------
d = np.load('world_big.npz', allow_pickle=True)
grid = d['grid'].copy()
grid[grid == 255] = 0
H, L, W = grid.shape
pal = list(d['palette'])
PID = {n: i for i, n in enumerate(pal)}

# ---------------- textures ----------------
TINT_GRASS = np.array([145, 189, 89], float) / 255
TINT_FOL = np.array([119, 171, 47], float) / 255
TINT_BIRCH = np.array([128, 167, 85], float) / 255
TINT_SPRUCE = np.array([97, 153, 97], float) / 255
TINT_MYC = np.array([111, 98, 101], float) / 255
TINT_WATER = np.array([63, 118, 228], float) / 255

def load(name):
    im = Image.open(f'{TEXDIR}/{name}.png')
    if im.mode == 'P':
        im = im.convert('RGBA')
    im = im.convert('RGBA')
    if im.size != (16, 16):
        im = im.crop((0, 0, 16, 16))
    return np.asarray(im, dtype=np.float64) / 255.0

def tint(a, rgb):
    out = a.copy(); out[..., :3] *= rgb; return out

def over(base, top):
    a = top[..., 3:4]
    out = base.copy()
    out[..., :3] = base[..., :3] * (1 - a) + top[..., :3] * a
    out[..., 3] = np.maximum(base[..., 3], top[..., 3])
    return out

_raw = {}
def tex(name):
    if name not in _raw: _raw[name] = load(name)
    return _raw[name]

# build texture bank: list of (16,16,4) float 0..1
BANK = []
def bank(t):
    BANK.append(t); return len(BANK) - 1

TX = {}
TX['grass_top'] = bank(tint(tex('grass_block_top'), TINT_GRASS))
TX['grass_side'] = bank(over(tex('grass_block_side'), tint(tex('grass_block_side_overlay'), TINT_GRASS)))
TX['dirt'] = bank(tex('dirt'))
TX['stone'] = bank(tex('stone'))
TX['andesite'] = bank(tex('andesite'))
TX['cobble'] = bank(tex('cobblestone'))
TX['stonebrick'] = bank(tex('stone_bricks'))
TX['smooth'] = bank(tex('smooth_stone'))
TX['sand'] = bank(tex('sand'))
TX['sandstone'] = bank(tex('sandstone_top'))
TX['oak_pl'] = bank(tex('oak_planks'))
TX['birch_pl'] = bank(tex('birch_planks'))
TX['spruce_pl'] = bank(tex('spruce_planks'))
TX['dark_pl'] = bank(tex('dark_oak_planks'))
TX['oak_log'] = bank(tex('oak_log'))
TX['oak_log_t'] = bank(tex('oak_log_top'))
TX['birch_log'] = bank(tex('birch_log'))
TX['birch_log_t'] = bank(tex('birch_log_top'))
TX['spruce_log'] = bank(tex('spruce_log'))
TX['spruce_log_t'] = bank(tex('spruce_log_top'))
TX['cherry_log'] = bank(tex('cherry_log'))
TX['cherry_log_t'] = bank(tex('cherry_log_top'))
TX['cherry_lv'] = bank(tex('cherry_leaves'))
TX['oak_lv'] = bank(tint(tex('oak_leaves'), TINT_FOL))
TX['birch_lv'] = bank(tint(tex('birch_leaves'), TINT_BIRCH))
TX['spruce_lv'] = bank(tint(tex('spruce_leaves'), TINT_SPRUCE))
TX['dark_lv'] = bank(tint(tex('oak_leaves'), np.array([90, 120, 90])/255))
TX['azalea_lv'] = bank(tex('flowering_azalea_leaves'))
TX['pinkter'] = bank(tex('pink_terracotta'))
TX['glass'] = bank(tex('glass'))
TX['glow'] = bank(tex('glowstone'))
TX['path_top'] = bank(tint(tex('dirt_path_top'), TINT_GRASS))
TX['path_side'] = bank(tex('dirt_path_side'))
TX['snow'] = bank(tex('snow'))
TX['water'] = bank(tint(tex('water_still'), TINT_WATER))
TX['hay_t'] = bank(tex('hay_block_top'))
TX['hay_s'] = bank(tex('hay_block_side'))
TX['bamboo'] = bank(tex('bamboo_stalk'))
TX['cactus'] = bank(tex('cactus_top'))
TX['cactus_s'] = bank(tex('cactus_side'))
TX['myc_top'] = bank(tint(tex('mycelium_top'), TINT_MYC))
TX['myc_s'] = bank(tex('mycelium_side'))
TX['mush_red'] = bank(tex('red_mushroom_block'))
TX['mush_stem'] = bank(tex('mushroom_stem'))
TX['white_w'] = bank(tex('white_wool'))
TX['red_w'] = bank(tex('red_wool'))
TX['packed_ice'] = bank(tex('snow'))  # placeholder; swap below if available
if os.path.exists(f'{TEXDIR}/packed_ice.png'):
    TX['packed_ice'] = bank(tex('packed_ice'))
TX['terracotta_myc'] = TX['myc_top']
TX['mud_bricks'] = bank(tex('mud_bricks'))
TX['packed_mud'] = bank(tex('packed_mud'))
TX['tuff'] = bank(tex('tuff'))
TX['tuff_bricks'] = bank(tex('tuff_bricks'))
TX['pol_tuff'] = bank(tex('polished_tuff'))
TX['chi_tuff'] = bank(tex('chiseled_tuff'))
TX['cut_sand'] = bank(tex('cut_sandstone'))
TX['smooth_sand'] = bank(tex('smooth_sandstone')) if os.path.exists(f'{TEXDIR}/smooth_sandstone.png') else bank(tex('sandstone_top'))
TX['chi_sand'] = bank(tex('chiseled_sandstone'))
TX['cracked_sb'] = bank(tex('cracked_stone_bricks'))
TX['mossy_sb'] = bank(tex('mossy_stone_bricks'))
TX['mossy_cob'] = bank(tex('mossy_cobblestone'))
TX['gravel'] = bank(tex('gravel'))
TX['pol_and'] = bank(tex('polished_andesite'))
TX['strip_spruce'] = bank(tex('stripped_spruce_log'))
TX['strip_spruce_t'] = bank(tex('spruce_log_top'))
TX['yellow_w'] = bank(tex('yellow_wool'))

TEXN = np.stack([np.clip(b * 255, 0, 255).astype(np.uint8) for b in BANK])  # (K,16,16,4)

# block name -> (top, side, bottom) texture indices
def T3(top, side=None, bottom=None):
    side = side if side is not None else top
    bottom = bottom if bottom is not None else side
    return (top, side, bottom)

BASE_M = {
    'minecraft:air': None,
    'minecraft:grass_block': T3(TX['grass_top'], TX['grass_side'], TX['dirt']),
    'minecraft:dirt': T3(TX['dirt']),
    'minecraft:stone': T3(TX['stone']),
    'minecraft:andesite': T3(TX['andesite']),
    'minecraft:cobblestone': T3(TX['cobble']),
    'minecraft:stone_bricks': T3(TX['stonebrick']),
    'minecraft:smooth_stone': T3(TX['smooth']),
    'minecraft:sand': T3(TX['sand']),
    'minecraft:sandstone': T3(TX['sandstone']),
    'minecraft:oak_planks': T3(TX['oak_pl']),
    'minecraft:birch_planks': T3(TX['birch_pl']),
    'minecraft:spruce_planks': T3(TX['spruce_pl']),
    'minecraft:dark_oak_planks': T3(TX['dark_pl']),
    'minecraft:oak_log': T3(TX['oak_log_t'], TX['oak_log']),
    'minecraft:birch_log': T3(TX['birch_log_t'], TX['birch_log']),
    'minecraft:spruce_log': T3(TX['spruce_log_t'], TX['spruce_log']),
    'minecraft:cherry_log': T3(TX['cherry_log_t'], TX['cherry_log']),
    'minecraft:oak_leaves': T3(TX['oak_lv']),
    'minecraft:birch_leaves': T3(TX['birch_lv']),
    'minecraft:spruce_leaves': T3(TX['spruce_lv']),
    'minecraft:dark_oak_leaves': T3(TX['dark_lv']),
    'minecraft:cherry_leaves': T3(TX['cherry_lv']),
    'minecraft:flowering_azalea_leaves': T3(TX['azalea_lv']),
    'minecraft:pink_terracotta': T3(TX['pinkter']),
    'minecraft:glass': T3(TX['glass']),
    'minecraft:glowstone': T3(TX['glow']),
    'minecraft:dirt_path': T3(TX['path_top'], TX['path_side'], TX['dirt']),
    'minecraft:snow_block': T3(TX['snow']),
    'minecraft:packed_ice': T3(TX['packed_ice']),
    'minecraft:water': T3(TX['water']),
    'minecraft:hay_block': T3(TX['hay_t'], TX['hay_s']),
    'minecraft:bamboo_block': T3(TX['bamboo']),
    'minecraft:cactus': T3(TX['cactus'], TX['cactus_s']),
    'minecraft:mycelium': T3(TX['myc_top'], TX['myc_s']),
    'minecraft:red_mushroom_block': T3(TX['mush_red']),
    'minecraft:mushroom_stem': T3(TX['mush_stem']),
    'minecraft:white_wool': T3(TX['white_w']),
    'minecraft:red_wool': T3(TX['red_w']),
    'minecraft:mud_bricks': T3(TX['mud_bricks']),
    'minecraft:packed_mud': T3(TX['packed_mud']),
    'minecraft:tuff': T3(TX['tuff']),
    'minecraft:tuff_bricks': T3(TX['tuff_bricks']),
    'minecraft:polished_tuff': T3(TX['pol_tuff']),
    'minecraft:chiseled_tuff': T3(TX['chi_tuff']),
    'minecraft:cut_sandstone': T3(TX['cut_sand']),
    'minecraft:smooth_sandstone': T3(TX['smooth_sand']),
    'minecraft:chiseled_sandstone': T3(TX['chi_sand']),
    'minecraft:cracked_stone_bricks': T3(TX['cracked_sb']),
    'minecraft:mossy_stone_bricks': T3(TX['mossy_sb']),
    'minecraft:mossy_cobblestone': T3(TX['mossy_cob']),
    'minecraft:gravel': T3(TX['gravel']),
    'minecraft:polished_andesite': T3(TX['pol_and']),
    'minecraft:stripped_spruce_log': T3(TX['strip_spruce_t'], TX['strip_spruce']),
    'minecraft:yellow_wool': T3(TX['yellow_w']),
}

# ---- generic fallback: any block without a mapping gets a texture by name ----
def _fallback_t3(block_name):
    base = block_name.replace('minecraft:', '')
    names = [f[:-4] for f in os.listdir(TEXDIR)]
    cand = None
    if base.endswith('_log') and f'{base}_top' in names:
        cand = (f'{base}_top', base, base)
    elif base in names:
        cand = (base, base, base)
    if cand is None:
        cand = ('stone', 'stone', 'stone')
    return T3(bank(tex(cand[0])), bank(tex(cand[1])), bank(tex(cand[2])))

grid = None; H = L = W = 0
NTOP = NSIDE = NBOT = None

def use_world(npz='world_big.npz'):
    """Load a world npz and (re)build the palette->texture maps for it."""
    global grid, H, L, W, PID, P, NTOP, NSIDE, NBOT
    d = np.load(npz, allow_pickle=True)
    grid = d['grid'].copy()
    grid[grid == 255] = 0
    H, L, W = grid.shape
    PID = {str(n): i for i, n in enumerate(d['palette'])}
    P = PID
    NTOP = np.zeros(256, np.int32); NSIDE = np.zeros_like(NTOP); NBOT = np.zeros_like(NTOP)
    for name, pid in PID.items():
        t3 = BASE_M.get(name) or _fallback_t3(name)
        if t3 is not None:
            NTOP[pid], NSIDE[pid], NBOT[pid] = t3

use_world()
# ---------------- raycast ----------------
SKY_TOP = np.array([120, 175, 235], float)
SKY_BOT = np.array([200, 224, 245], float)
FOG_D = 160.0

def look(camx, camy, camz, yaw, pitch=8, out='look.png', rw=520, rh=300, fov=72, sun=(0.5, 0.85, -0.35)):
    th = np.radians(yaw); ph = np.radians(pitch)
    fwd = np.array([np.cos(ph) * np.cos(th), np.sin(ph), np.cos(ph) * np.sin(th)])
    right = np.array([-np.sin(th), 0, np.cos(th)])
    up = np.cross(right, fwd)
    fl = 1.0 / np.tan(np.radians(fov) / 2)
    xs = (np.arange(rw) - rw / 2 + 0.5) / (rh / 2)   # keep square pixels
    ys = (rh / 2 - np.arange(rh) + 0.5) / (rh / 2)
    Pp, Qq = np.meshgrid(xs, ys)
    D = fwd * fl + right * Pp[..., None] + up * Qq[..., None]
    D = D.reshape(-1, 3)
    N = D.shape[0]
    D /= np.linalg.norm(D, axis=1, keepdims=True)

    ox = np.full(N, camx + 0.5); oy = np.full(N, camy + 0.5); oz = np.full(N, camz + 0.5)
    ix = np.floor(ox).astype(np.int64); iy = np.floor(oy).astype(np.int64); iz = np.floor(oz).astype(np.int64)
    stepx = np.where(D[:, 0] > 0, 1, -1); stepy = np.where(D[:, 1] > 0, 1, -1); stepz = np.where(D[:, 2] > 0, 1, -1)
    with np.errstate(divide='ignore'):
        tdx = np.abs(1 / D[:, 0]); tdy = np.abs(1 / D[:, 1]); tdz = np.abs(1 / D[:, 2])
        tmx = np.where(D[:, 0] > 0, (ix + 1 - ox), (ox - ix)) * tdx
        tmy = np.where(D[:, 1] > 0, (iy + 1 - oy), (oy - iy)) * tdy
        tmz = np.where(D[:, 2] > 0, (iz + 1 - oz), (oz - iz)) * tdz
    hit_id = np.zeros(N, dtype=np.int64)
    hit_t = np.full(N, 1e9)
    hit_face = np.full(N, -1, dtype=np.int64)   # 0=+y 1=-y 2=+x 3=-x 4=+z 5=-z
    alive = np.arange(N)
    steps = 0
    MAXS = 420
    while alive.size and steps < MAXS:
        steps += 1
        a = np.argmin(np.stack([tmx[alive], tmy[alive], tmz[alive]]), axis=0)
        al = alive
        tmx[al] += np.where(a == 0, tdx[al], 0)
        tmy[al] += np.where(a == 1, tdy[al], 0)
        tmz[al] += np.where(a == 2, tdz[al], 0)
        ix[al] += np.where(a == 0, stepx[al], 0)
        iy[al] += np.where(a == 1, stepy[al], 0)
        iz[al] += np.where(a == 2, stepz[al], 0)
        face = np.where(a == 0, np.where(stepx[al] > 0, 3, 2),
               np.where(a == 1, np.where(stepy[al] > 0, 1, 0),
                               np.where(stepz[al] > 0, 5, 4)))
        inside = (ix[al] >= 0) & (ix[al] < W) & (iy[al] >= 0) & (iy[al] < H) & (iz[al] >= 0) & (iz[al] < L)
        i2 = np.nonzero(inside)[0]
        al2 = al[i2]
        if al2.size == 0:
            alive = al2
            continue
        face2 = face[i2]
        bid = grid[iy[al2], iz[al2], ix[al2]]
        hitm = bid != 0
        hh = al2[hitm]
        if hh.size:
            t = np.minimum(np.minimum(tmx[hh], tmy[hh]), tmz[hh])
            hit_id[hh] = bid[hitm]
            hit_face[hh] = face2[hitm]
            hit_t[hh] = t
        # alive <- rays still alive (in-bounds and not yet hit)
        alive = al2[~hitm]
    # sky pixels
    img = np.zeros((N, 3))
    skyy = np.clip(0.5 + 0.5 * D[:, 1], 0, 1)
    sky = SKY_BOT * (1 - skyy)[:, None] + SKY_TOP * skyy[:, None]
    img[:] = sky
    did = hit_id > 0
    if did.any():
        t = hit_t[did]
        hx = ox[did] + D[did, 0] * t
        hy = oy[did] + D[did, 1] * t
        hz = oz[did] + D[did, 2] * t
        f = hit_face[did]; bid = hit_id[did]
        topm = f == 0; botm = f == 1; xm = (f == 2) | (f == 3)
        u = np.where(topm | botm, hx, np.where(xm, hz, hx))
        v = np.where(topm | botm, hz, hy)
        uf = np.clip(u - np.floor(u), 0, 0.99999)
        vf = np.clip(v - np.floor(v), 0, 0.99999)
        tu = (uf * 16).astype(np.int64)
        tv = (vf * 16).astype(np.int64)
        texi = np.where(f == 0, NTOP[bid], np.where(f == 1, NBOT[bid], NSIDE[bid]))
        col = TEXN[texi, tv, tu, :3].astype(np.float64)
        alpha = TEXN[texi, tv, tu, 3:4] / 255.0
        col = col * alpha + sky[did] * (1 - alpha)
        # lighting
        LIGHT = {0: 1.0, 1: 0.5, 2: 0.82, 3: 0.72, 4: 0.66, 5: 0.78}
        lam = np.array([LIGHT[int(x)] for x in f])
        col *= lam[:, None]
        # glowstone emissive
        g = bid == P.get('minecraft:glowstone', -1)
        if g.any(): col[g] = np.minimum(col[g] * 1.9 + 40, 255)
        # fog
        fogc = 0.55 * SKY_BOT + 0.45 * SKY_TOP
        fo = np.clip(t / FOG_D, 0, 1)[:, None] ** 1.4
        col = col * (1 - fo) + fogc * fo
        img[did] = col
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8).reshape(rh, rw, 3)).save(f'{OUTDIR}/{out}')
    print(f"saved {out}")

def surf_y(x, z):
    ys = np.nonzero(grid[:, z, x])[0]
    return int(ys[-1]) if len(ys) else 80

def walk(name, x, z, yaw, pitch=10, dy=1.7, **kw):
    y = surf_y(int(x), int(z)) + 1 + dy
    while 0 <= int(y) < H and grid[int(y), int(z), int(x)] != 0:
        y += 1
    print(f"{name}: eye at ({x},{y:.0f},{z}) yaw={yaw}")
    look(x, y, z, yaw, pitch=pitch, out=f'walk_{name}.png', **kw)

if __name__ == '__main__':
    SHOTS = [
        ("big_river3", 396, 340, 250, 6),
        ("big_beach",  384, 297, 250, 8),
        ("big_cherry", 120, 350, 60, 10),
        ("big_bay",    455, 240, 280, 8),
        ("big_peak",   221, 132, 200, 18),
        ("big_rimfall", 183, 44, 190, 4),
    ]
    for shot in SHOTS:
        name, x, z, yaw = shot[:4]
        pitch = shot[4] if len(shot) > 4 else 10
        walk(name, x, z, yaw, pitch=pitch)
    print("all walks done")
