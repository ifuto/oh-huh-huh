#!/usr/bin/env python3
"""
Thorough lossless-integrity verification for Sponge v2 .schem files.

Layers checked:
  A. gzip container: header fields, single member, trailing bytes, CRC32, ISIZE,
     independent decompression (zlib raw / gzip module / system gunzip)
  B. NBT payload: independent hand-rolled parser (all 13 tag types, big-endian),
     exact byte consumption, Sponge v2 field/type validation, cross-check vs nbtlib
  C. BlockData varint: full decode == W*H*L, indices < PaletteMax, palette hygiene,
     byte-identical re-encode (round trip)
  D. Reproducibility: fresh conversion run must produce identical uncompressed payload
  E. Visual proof: render map/slice from the DECODED file and pixel-compare with
     the committed previews

Usage: python3 verify_schem.py <file.schem> <glb> [converter_script]
"""
import sys, os, gzip, struct, zlib, hashlib, subprocess, tempfile
import numpy as np

FAIL = 0
def check(name, ok, detail=""):
    global FAIL
    tag = "PASS" if ok else "FAIL"
    if not ok: FAIL += 1
    print(f"  [{tag}] {name}" + (f"  ({detail})" if detail else ""))
    return ok

# ---------------- A. gzip container ----------------

def gzip_audit(path):
    print("\n== A. gzip container ==")
    raw = open(path, 'rb').read()
    check("gzip magic 1f 8b", raw[:2] == b'\x1f\x8b')
    cm = raw[2]; flg = raw[3]
    mtime, xfl, osb = struct.unpack('<IBB', raw[4:10])
    check("CM=8 (DEFLATE)", cm == 8, f"cm={cm}")
    check("FLG reserved bits clear", (flg & 0xE0) == 0, f"flg=0x{flg:02x}")
    # FLG bits: FTEXT=1 FHCRC=2 FEXTRA=4 FNAME=8 FCOMMENT=16
    off = 10
    if flg & 4:
        xlen = struct.unpack('<H', raw[off:off+2])[0]; off += 2 + xlen
    if flg & 8:
        end = raw.index(b'\0', off); fname = raw[off:end]; off = end + 1
        print(f"    FNAME: {fname.decode('utf-8', 'replace')!r}")
    if flg & 16:
        end = raw.index(b'\0', off); off = end + 1
    if flg & 2:
        off += 2
    print(f"    header: mtime={mtime} xfl={xfl} os={osb} flags=0x{flg:02x} data@{off}")
    payload = gzip.decompress(raw)
    d = zlib.decompressobj(wbits=-zlib.MAX_WBITS)
    p1 = d.decompress(raw[off:])
    p1 += d.flush()
    check("deflate stream self-terminated (d.eof)", d.eof)
    trailer = d.unused_data
    check("exactly 8 trailer bytes follow (CRC32+ISIZE), no 2nd member",
          d.eof and len(trailer) == 8,
          f"trailer={len(trailer)}B (trailer at file offset {len(raw)-8})")
    check("zlib-raw == gzip-module payload", p1 == payload)
    crc_stored, isize_stored = struct.unpack('<II', trailer)
    crc_calc = zlib.crc32(payload) & 0xFFFFFFFF
    check("CRC32 matches", crc_stored == crc_calc, f"stored={crc_stored:08x} calc={crc_calc:08x}")
    check("ISIZE matches (len mod 2^32)", isize_stored == len(payload) % 2**32,
          f"stored={isize_stored} actual={len(payload)}")
    # independent decompressor: system gunzip
    try:
        out = subprocess.run(['gunzip', '-c', path], capture_output=True, timeout=120)
        check("system gunzip exit 0", out.returncode == 0, out.stderr.decode()[:80])
        check("system gunzip payload identical", hashlib.sha256(out.stdout).digest() == hashlib.sha256(payload).digest())
    except FileNotFoundError:
        print("  [skip] system gunzip not available")
    print(f"    compressed={len(raw):,} B  uncompressed={len(payload):,} B  ratio={len(raw)/len(payload)*100:.1f}%")
    print(f"    payload sha256 = {hashlib.sha256(payload).hexdigest()}")
    return payload

# ---------------- B. NBT (hand parser) ----------------

class NBTParser:
    def __init__(self, buf): self.b = buf; self.i = 0
    def u8(self): v = self.b[self.i]; self.i += 1; return v
    def i8(self): v = struct.unpack_from('>b', self.b, self.i)[0]; self.i += 1; return v
    def i16(self): v = struct.unpack_from('>h', self.b, self.i)[0]; self.i += 2; return v
    def i32(self): v = struct.unpack_from('>i', self.b, self.i)[0]; self.i += 4; return v
    def i64(self): v = struct.unpack_from('>q', self.b, self.i)[0]; self.i += 8; return v
    def f32(self): v = struct.unpack_from('>f', self.b, self.i)[0]; self.i += 4; return v
    def f64(self): v = struct.unpack_from('>d', self.b, self.i)[0]; self.i += 8; return v
    def string(self):
        n = struct.unpack_from('>H', self.b, self.i)[0]; self.i += 2
        s = self.b[self.i:self.i+n].decode('utf-8'); self.i += n; return s
    def payload(self, t):
        if t == 1: return self.i8()
        if t == 2: return self.i16()
        if t == 3: return self.i32()
        if t == 4: return self.i64()
        if t == 5: return self.f32()
        if t == 6: return self.f64()
        if t == 7:
            n = self.i32(); v = self.b[self.i:self.i+n]; self.i += n; return v
        if t == 8: return self.string()
        if t == 9:
            et = self.u8(); n = self.i32()
            return [self.payload(et) for _ in range(n)]
        if t == 10:
            out = {}
            while True:
                tt = self.u8()
                if tt == 0: return out
                name = self.string()
                out[name] = self.payload(tt)
        if t == 11:
            n = self.i32(); v = list(struct.unpack_from(f'>{n}i', self.b, self.i)); self.i += 4*n; return v
        if t == 12:
            n = self.i32(); v = list(struct.unpack_from(f'>{n}q', self.b, self.i)); self.i += 8*n; return v
        raise ValueError(f"unknown NBT tag {t}")
    def named(self):
        t = self.u8()
        name = self.string()
        return name, self.payload(t)

def nbt_audit(payload):
    print("\n== B. NBT structure (independent parser) ==")
    p = NBTParser(payload)
    root_name, root = p.named()
    check("root TAG_Compound named 'Schematic' (Sponge/FAWE spec)",
          root_name == 'Schematic' and isinstance(root, dict))
    s = root
    # exact consumption
    check("parser consumed payload exactly (no trailing)", p.i == len(payload), f"parsed {p.i}/{len(payload)} B")
    # spec fields & types (Sponge v2)
    check("Version Int == 2", isinstance(s.get('Version'), int) and s['Version'] == 2)
    check("DataVersion Int == 4671 (MC 1.21.11)", s.get('DataVersion') == 4671, f"got {s.get('DataVersion')}")
    W, H, L = s.get('Width'), s.get('Height'), s.get('Length')
    for k, v, lim in (('Width', W, 32767), ('Height', H, 32767), ('Length', L, 32767)):
        check(f"{k} TAG_Short in range", isinstance(v, int) and 1 <= v <= lim, f"{k}={v}")
    check("Offset TAG_IntArray len 3", isinstance(s.get('Offset'), list) and len(s['Offset']) == 3)
    pal = s.get('Palette'); pm = s.get('PaletteMax'); bd = s.get('BlockData')
    check("Palette TAG_Compound of Int", isinstance(pal, dict) and all(isinstance(x, int) for x in pal.values()))
    check("PaletteMax Int == len(Palette)", isinstance(pm, int) and pm == len(pal), f"max={pm} len={len(pal)}")
    check("palette ids are 0..N-1 (dense)", sorted(pal.values()) == list(range(len(pal))))
    check("palette ids < PaletteMax", all(0 <= x < pm for x in pal.values()))
    check("BlockData TAG_ByteArray", isinstance(bd, (bytes, bytearray)))
    check("'minecraft:air' in palette", 'minecraft:air' in pal)
    if isinstance(bd, (bytes, bytearray)):
        bd = bytes(bd)
    # cross-check with nbtlib
    import nbtlib
    f = nbtlib.load(sys.argv[1])
    s2 = f  # nbtlib File: root fields are top-level when root_name == 'Schematic'
    check("nbtlib sees same dims", (int(s2['Width']), int(s2['Height']), int(s2['Length'])) == (W, H, L))
    check("nbtlib sees same BlockData bytes", bytes(np.asarray(s2['BlockData']).astype(np.uint8)) == bd)
    check("nbtlib sees same Palette", {str(k): int(v) for k, v in s2['Palette'].items()} == pal)
    return s, W, H, L, pal, bd

# ---------------- C. varint round trip ----------------

def varint_audit(s, W, H, L, pal, bd):
    print("\n== C. BlockData varint stream ==")
    vals = []
    i = 0
    need = W * H * L
    ok = True
    while len(vals) < need:
        if i >= len(bd): ok = False; break
        b = bd[i]; idx = b & 0x7F; shift = 7
        i += 1
        while b & 0x80:
            if i >= len(bd): ok = False; break
            b = bd[i]; idx |= (b & 0x7F) << shift; shift += 7; i += 1
        if not ok: break
        vals.append(idx)
        if idx >= len(pal): ok = False; break
    check("decoded exactly W*H*L blocks", len(vals) == need and ok, f"{len(vals):,}/{need:,}")
    check("varint stream consumed byte-exact", i == len(bd), f"stream end {i} vs {len(bd)}")
    # re-encode and compare
    enc = bytearray()
    for v in vals:
        while True:
            b7 = v & 0x7F; v >>= 7
            enc.append(b7 | 0x80 if v else b7)
            if not v: break
    check("re-encode is byte-identical (lossless round trip)", bytes(enc) == bd)
    inv = {v: k for k, v in pal.items()}
    from collections import Counter
    c = Counter(inv[v] for v in vals)
    unused = [k for k in pal if k not in c]
    check("no unused palette entries (clean palette)", not unused, f"unused={unused[:5]}" if unused else "")
    print(f"    blocks: {need:,}  non-air: {need - c.get('minecraft:air', 0):,}")
    for n, k in c.most_common(6):
        print(f"      {n}: {k:,}")
    return vals, inv

# ---------------- D. reproducibility ----------------

def repro_audit(path, glb, conv):
    print("\n== D. reproducibility (fresh conversion) ==")
    outs = []
    for tag in ('a', 'b'):
        tmp = tempfile.NamedTemporaryFile(suffix='.schem', delete=False).name
        subprocess.run(['python3', conv, glb, tmp], check=True, capture_output=True)
        outs.append(open(tmp, 'rb').read())
        os.unlink(tmp)
    p0 = gzip.decompress(open(path, 'rb').read())
    same_payload = all(hashlib.sha256(gzip.decompress(o)).digest() == hashlib.sha256(p0).digest() for o in outs)
    check("fresh runs decompress to identical payload", same_payload)
    check("fresh runs are byte-identical files", outs[0] == outs[1],
          "gzip stream fully deterministic" if outs[0] == outs[1] else "only payload deterministic (gzip header mtime varies)")

# ---------------- E. render from decoded data ----------------

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
    'minecraft:sand': (219,207,163), 'minecraft:air': (222,238,245),
}

def render_audit(s, W, H, L, pal, vals, inv, base):
    print("\n== E. render from decoded file vs committed previews ==")
    from PIL import Image, ImageChops
    g = np.array(vals, dtype=np.int32).reshape(H, L, W)
    names = np.empty((H, L, W), dtype=object)
    for k, v in pal.items():
        names[g == v] = k
    names[names == 'minecraft:air'] = None
    img = np.zeros((L, W, 3), dtype=np.uint8)
    for z in range(L):
        for x in range(W):
            col = names[:, z, x]
            nz = col[col != None]
            img[z, x] = BLOCK_RGB.get(nz[-1], (255, 0, 255)) if len(nz) else (0, 0, 0)
    Image.fromarray(img).resize((W*6, L*6), Image.NEAREST).save(base + '_map_dec.png')
    a = Image.open(base + '_map_dec.png'); b = Image.open(base + '_map.png')
    check("top-down map identical to committed PNG", ImageChops.difference(a, b).getbbox() is None)
    cy = L // 2
    img2 = np.zeros((H, W, 3), dtype=np.uint8)
    for y in range(H):
        for x in range(W):
            n = None
            for dz in range(3):
                v = names[y, min(cy+dz, L-1), x]
                if v is not None: n = v; break
            img2[H-1-y, x] = BLOCK_RGB.get(n, (222,238,245))
    Image.fromarray(img2).resize((W*6, H*6), Image.NEAREST).save(base + '_slice_dec.png')
    a = Image.open(base + '_slice_dec.png'); b = Image.open(base + '_slice.png')
    check("cross-section identical to committed PNG", ImageChops.difference(a, b).getbbox() is None)

def main():
    path, glb = sys.argv[1], sys.argv[2]
    conv = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(path) or '.', 'convert.py')
    base = path[:-6] if path.endswith('.schem') else path
    payload = gzip_audit(path)
    s, W, H, L, pal, bd = nbt_audit(payload)
    vals, inv = varint_audit(s, W, H, L, pal, bd)
    repro_audit(path, glb, conv)
    render_audit(s, W, H, L, pal, vals, inv, base)
    print("\n" + ("=" * 50))
    print(("ALL CHECKS PASSED - lossless & spec-valid" if FAIL == 0 else f"{FAIL} CHECK(S) FAILED"))
    sys.exit(0 if FAIL == 0 else 1)

if __name__ == '__main__':
    main()
