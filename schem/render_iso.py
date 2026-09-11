#!/usr/bin/env python3
"""
Textured isometric renderer for the 500x500 voxel world, using the real
Minecraft 1.21.11 block textures (from the official client jar).

Painter's algorithm over exposed blocks; per-block sprites are pre-rendered
per view (top/side/bottom parallelograms via PIL affine, NEAREST sampling).
"""
import os, sys
import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
TEXDIR = 'textures'
OUTDIR = '../renders'
os.makedirs(OUTDIR, exist_ok=True)

# ---------------- world ----------------
d = np.load('world_500.npz', allow_pickle=True)
grid = d['grid']                       # (H, L, W) ids, 255 = air
H, L, W = grid.shape
pal = list(d['palette'])
PID = {n: i for i, n in enumerate(pal)}
AIR = 255

# ---------------- textures: load, tint, compose ----------------
TINT_GRASS = (145, 189, 89)      # plains grass
TINT_FOLIAGE = (119, 171, 47)    # plains foliage
TINT_BIRCH = (128, 167, 85)
TINT_SPRUCE = (97, 153, 97)
TINT_MYCELIUM = (111, 98, 101)
TINT_WATER = (63, 118, 228)

def load_rgba(name):
    im = Image.open(f'{TEXDIR}/{name}.png').convert('RGBA')
    if im.size != (16, 16):
        im = im.crop((0, 0, 16, 16))   # animated strips: first frame
    a = np.asarray(im, dtype=np.float64)
    return a

def tinted(name, rgb):
    a = load_rgba(name)
    a[..., 0] *= rgb[0] / 255; a[..., 1] *= rgb[1] / 255; a[..., 2] *= rgb[2] / 255
    return a

def compose_over(base, over):
    a = over[..., 3:4] / 255
    out = base.copy()
    out[..., :3] = base[..., :3] * (1 - a) + over[..., :3] * a
    out[..., 3] = np.maximum(base[..., 3], over[..., 3])
    return out

T = {}
for f in os.listdir(TEXDIR):
    T[f[:-4]] = load_rgba(f[:-4])
T['grass_top'] = tinted('grass_block_top', TINT_GRASS)
T['grass_side'] = compose_over(load_rgba('grass_block_side'), tinted('grass_block_side_overlay', TINT_GRASS))
T['oak_leaves_t'] = tinted('oak_leaves', TINT_FOLIAGE)
T['birch_leaves_t'] = tinted('birch_leaves', TINT_BIRCH)
T['spruce_leaves_t'] = tinted('spruce_leaves', TINT_SPRUCE)
T['mycelium_top_t'] = tinted('mycelium_top', TINT_MYCELIUM)
T['mycelium_side_t'] = compose_over(load_rgba('mycelium_side'), tinted(load_rgba('mycelium_side')[..., 3].mean() < 250 and 'mycelium_side' or 'mycelium_side', TINT_MYCELIUM)) if False else load_rgba('mycelium_side')
T['water'] = tinted('water_still', TINT_WATER)
T['water'][..., 3] = 210

# block id -> (top, side, bottom) texture arrays
def tex3(top, side, bottom=None):
    return (top, side, bottom if bottom is not None else side)
FACES = {
    PID['minecraft:grass_block']: tex3(T['grass_top'], T['grass_side'], T['dirt']),
    PID['minecraft:dirt']: tex3(T['dirt'], T['dirt']),
    PID['minecraft:stone']: tex3(T['stone'], T['stone']),
    PID['minecraft:andesite']: tex3(T['andesite'], T['andesite']),
    PID['minecraft:cobblestone']: tex3(T['cobblestone'], T['cobblestone']),
    PID['minecraft:oak_planks']: tex3(T['oak_planks'], T['oak_planks']),
    PID['minecraft:birch_planks']: tex3(T['birch_planks'], T['birch_planks']),
    PID['minecraft:spruce_planks']: tex3(T['spruce_planks'], T['spruce_planks']),
    PID['minecraft:dark_oak_planks']: tex3(T['dark_oak_planks'], T['dark_oak_planks']),
    PID['minecraft:spruce_log']: tex3(T['spruce_log_top'], T['spruce_log']),
    PID['minecraft:oak_log']: tex3(T['oak_log_top'], T['oak_log']),
    PID['minecraft:birch_log']: tex3(T['birch_log_top'], T['birch_log']),
    PID['minecraft:oak_leaves']: tex3(T['oak_leaves_t'], T['oak_leaves_t']),
    PID['minecraft:birch_leaves']: tex3(T['birch_leaves_t'], T['birch_leaves_t']),
    PID['minecraft:spruce_leaves']: tex3(T['spruce_leaves_t'], T['spruce_leaves_t']),
    PID['minecraft:dark_oak_leaves']: tex3(T['oak_leaves_t'], T['oak_leaves_t']),
    PID['minecraft:flowering_azalea_leaves']: tex3(T['flowering_azalea_leaves'], T['flowering_azalea_leaves']),
    PID['minecraft:pink_terracotta']: tex3(T['pink_terracotta'], T['pink_terracotta']),
    PID['minecraft:glass']: tex3(T['glass'], T['glass']),
    PID['minecraft:glowstone']: tex3(T['glowstone'], T['glowstone']),
    PID['minecraft:dirt_path']: tex3(T['dirt_path_top'], T['dirt_path_side'], T['dirt']),
    PID['minecraft:sand']: tex3(T['sand'], T['sand']),
    PID['minecraft:snow_block']: tex3(T['snow'], T['snow']),
    PID['minecraft:water']: tex3(T['water'], T['water']),
    PID['minecraft:stone_bricks']: tex3(T['stone_bricks'], T['stone_bricks']),
    PID['minecraft:smooth_stone']: tex3(T['smooth_stone'], T['smooth_stone']),
    PID['minecraft:hay_block']: tex3(T['hay_block_top'], T['hay_block_side']),
    PID['minecraft:cherry_log']: tex3(T['cherry_log_top'], T['cherry_log']),
    PID['minecraft:cherry_leaves']: tex3(T['cherry_leaves'], T['cherry_leaves']),
    PID['minecraft:bamboo_block']: tex3(T['bamboo_stalk'], T['bamboo_stalk']),
    PID['minecraft:sandstone']: tex3(T['sandstone_top'], T['sandstone']),
    PID['minecraft:cactus']: tex3(T['cactus_top'], T['cactus_side']),
    PID['minecraft:mycelium']: tex3(T['mycelium_top_t'], T['mycelium_side']),
    PID['minecraft:red_mushroom_block']: tex3(T['red_mushroom_block'], T['red_mushroom_block']),
    PID['minecraft:mushroom_stem']: tex3(T['mushroom_stem'], T['mushroom_stem']),
    PID['minecraft:white_wool']: tex3(T['white_wool'], T['white_wool']),
    PID['minecraft:red_wool']: tex3(T['red_wool'], T['red_wool']),
    PID['minecraft:packed_ice']: tex3(T['packed_ice'] if 'packed_ice' in T else T['snow'], T['packed_ice'] if 'packed_ice' in T else T['snow']),
}

# ---------------- drawable blocks ----------------
print("computing exposure...")
solid = grid != AIR
airn = np.zeros_like(solid)
airn[1:, :, :] |= ~solid[:-1, :, :]      # -y (below) ... careful: neighbor below of (y) is (y-1)
exp = np.zeros_like(solid)
exp[:-1] |= solid[:-1] & ~solid[1:]       # top face: solid at y, air at y+1
exp[1:]  |= solid[1:] & ~solid[:-1]       # bottom face
for axis in (0, 2):
    e = np.zeros_like(solid)
    if axis == 0:
        e[:, :-1] |= solid[:, :-1] & ~solid[:, 1:]   # +x side
        e[:, 1:]  |= solid[:, 1:] & ~solid[:, :-1]   # -x side
    else:
        e[:, :, :-1] |= solid[:, :, :-1] & ~solid[:, :, 1:]  # +z
        e[:, :, 1:]  |= solid[:, :, 1:] & ~solid[:, :, :-1]  # -z
    exp |= e
ys, zs, xs = np.nonzero(exp)
byy = grid[ys, zs, xs]
keep = byy != AIR
ys, zs, xs, bid = ys[keep], zs[keep], xs[keep], byy[keep]
print(f"drawable blocks: {len(ys):,}")

# ---------------- sprite pre-render ----------------

def face_sprite(tex, o2, e1, e2, shade):
    """Parallelogram from integer corner o2 (screen, top-left origin) spanned by e1,e2 (per-full-block); returns patch"""
    w = int(abs(e1[0]) + abs(e2[0])) + 1
    h = int(abs(e1[1]) + abs(e2[1])) + 1
    # affine coeffs: input tex coords as function of output pixel
    A = [e1[0] / 16.0, e2[0] / 16.0, 0.0]
    B = [e1[1] / 16.0, e2[1] / 16.0, 0.0]
    ox = min(0, e1[0], e2[0], e1[0] + e2[0])
    oy = min(0, e1[1], e2[1], e1[1] + e2[1])
    A[2] = -ox; B[2] = -oy
    img = Image.fromarray(np.clip(tex, 0, 255).astype(np.uint8), 'RGBA')
    patch = img.transform((w, h), Image.AFFINE, (A[0], A[1], A[2], B[0], B[1], B[2]), resample=Image.NEAREST)
    p = np.asarray(patch, dtype=np.float64)
    rgb = p[..., :3] * (p[..., 3:4] / 255.0)      # premultiply
    rgb *= shade
    alpha = p[..., 3]
    patch_arr = np.zeros((h, w, 4))
    patch_arr[..., :3] = rgb
    patch_arr[..., 3] = alpha
    return patch_arr, (ox, oy)

def block_sprite(bid, e_x, e_y, e_z, side_axis):
    """Full block sprite for one view. side_axis: which of x/z faces camera (+x+z, +x-z, ...)."""
    top_t, side_t, bot_t = FACES[bid]
    pieces = []
    # top face at corner (x+1,z+1,y+1)?: top face corners: origin at block corner O=(x,y,z) screen pos p0.
    # top face spanned by e_x and e_z from corner O+e_y
    if True:
        p, off = face_sprite(top_t, None, e_x, e_z, 1.0)
        pieces.append((p, ('top', off)))
    # two visible side faces: from corner O, along e_x (face x, spanned e_x & e_y) etc.
    s1 = 0.80 if side_axis[0] > 0 else 0.66
    s2 = 0.80 if side_axis[1] > 0 else 0.66
    p, off = face_sprite(side_t, None, e_x, e_y, s1)
    pieces.append((p, ('sx', off)))
    p, off = face_sprite(side_t, None, e_z, e_y, s2)
    pieces.append((p, ('sz', off)))
    return pieces

def render_view(phi_deg, theta_deg, A=12, region=None, night=False, out='out.png'):
    phi = np.radians(phi_deg); th = np.radians(theta_deg)
    dirc = np.array([np.cos(phi) * np.cos(th), np.sin(th), np.sin(phi) * np.cos(th)])  # toward camera
    right = np.array([-np.sin(phi), 0, np.cos(phi)])
    up = np.cross(right, dirc)
    def proj(v):
        return np.array([np.dot(v, right), -np.dot(v, up)]) * A
    e_x = proj([1, 0, 0]); e_y = proj([0, 1, 0]); e_z = proj([0, 0, 1])
    e_x = np.round(e_x).astype(int); e_y = np.round(e_y).astype(int); e_z = np.round(e_z).astype(int)
    print(f"view phi={phi_deg} th={theta_deg}: e_x={e_x} e_y={e_y} e_z={e_z}")
    depth = xs * (-dirc[0]) + ys * (-dirc[1]) + zs * (-dirc[2])   # far (small dot toward cam) first: sort ascending by distance-to-cam? 
    dist = xs * dirc[0] + ys * dirc[1] + zs * dirc[2]
    order = np.argsort(dist)
    sxo = xs * e_x[0] + ys * e_y[0] + zs * e_z[0]
    syo = xs * e_x[1] + ys * e_y[1] + zs * e_z[1]
    if region:
        x0, x1, z0, z1 = region
        m = (xs >= x0) & (xs < x1) & (zs >= z0) & (zs < z1)
        idx = np.nonzero(m)[0]
        order = order[np.isin(order, idx)]
    sxo, syo, bidf, ysf = sxo[order], syo[order], bid[order], ys[order]
    minx, maxx = sxo.min(), sxo.max()
    miny, maxy = syo.min(), syo.max()
    CW, CH = maxx - minx + 80, maxy - miny + 80
    print(f"canvas {CW}x{CH}, blocks {len(sxo):,}")
    canvas = np.zeros((CH, CW, 3), dtype=np.uint8)
    fill = np.zeros((CH, CW), dtype=bool)
    emissive_pts = []
    sprite_cache = {}
    for i in range(len(sxo)):
        b = bidf[i]
        key = (b, side_axis := (1 if e_x[0] * 1 >= 0 else -1, 1))
        pieces = sprite_cache.get(key)
        if pieces is None:
            pieces = block_sprite(b, e_x, e_y, e_z, (1, 1))
            sprite_cache[key] = pieces
        px = sxo[i] - minx + 40
        py = syo[i] - miny + 40
        for p, (kind, off) in pieces:
            h, w = p.shape[:2]
            x0 = px + off[0]; y0 = py + off[1]
            if x0 < 0 or y0 < 0 or x0 + w > CW or y0 + h > CH: continue
            reg = canvas[y0:y0 + h, x0:x0 + w]
            msk = p[..., 3] > 8
            if night and b in (PID['minecraft:glowstone'],):
                continue
            alpha = p[..., 3:4] / 255.0
            m = msk & (p[..., 3] >= 250)
            if m.any():
                reg[m] = p[..., :3][m].astype(np.uint8)
            mm = msk & (p[..., 3] < 250) & (p[..., 3] > 8)
            if mm.any():
                reg[mm] = (reg[mm] * (1 - alpha[mm]) + p[..., :3][mm] * alpha[mm]).astype(np.uint8)
        if b == PID['minecraft:glowstone']:
            emissive_pts.append((px, py))
    img = Image.fromarray(canvas)
    img.save(out if night is False else out.replace('.png', '_day.png'))
    return img, emissive_pts, (minx, miny)

# ---------------- views ----------------
CX = W // 2
print("render day SE...")
img, em, org = render_view(135, 30, A=12, out=f'{OUTDIR}/island500_iso_se.png')
print("render day SW...")
render_view(225, 30, A=12, out=f'{OUTDIR}/island500_iso_sw.png')
print("render day NE...")
render_view(45, 30, A=12, out=f'{OUTDIR}/island500_iso_ne.png')
print("render low underside S...")
render_view(180, 14, A=12, out=f'{OUTDIR}/island500_low_south.png')
print("done base views")
