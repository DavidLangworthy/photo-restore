#!/usr/bin/env python3
"""
auto_correct_bw.py — Convert photos to clean, high-contrast B&W (grayscale).

What it does
------------
- Accepts a single image or a folder (with --recursive).
- Converts to grayscale.
- Enhances with CLAHE (local contrast) + gentle auto-levels.
- Optional mild sharpening and denoise.
- Writes outputs to the target folder, mirroring subfolders.

Examples
--------
# Whole folder, recursive
python auto_correct_bw.py --input "/path/to/folder" --out "/path/to/out" --recursive

# Single file
python auto_correct_bw.py --input "/path/to/photo.tif" --out "/path/to/out"

# Overwrite in place (careful)
python auto_correct_bw.py --input "/path/to/folder" --out "/path/to/folder" --recursive --inplace

Options
-------
--low-q / --high-q : quantiles for auto-levels (default 0.01 / 0.99)
--clahe            : enable/disable CLAHE (on by default)
--clip-limit       : CLAHE clip limit (default 2.2)
--tile             : CLAHE tile grid size (default "8,8")
--sharpen          : unsharp mask amount (0 disables; default 0.5)
--denoise          : fast denoise strength (default 0; 0.0-15.0 reasonable)
--max-edge         : optionally downscale so the longest edge <= this many pixels (0=off)
--preview          : write a side-by-side preview of original and result
--format           : force output format (jpg/png/tiff). Default: keep input's
--quality          : JPEG quality (default 92)

Note: OpenCV writes 8-bit; if you need 16-bit TIFFs, say the word and I'll add it.
"""

import os, sys, argparse, glob
from typing import List, Tuple
import numpy as np
import cv2

def imread_color(path: str):
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Could not read: {path}")
    return img

def ensure_dir(p: str): os.makedirs(p, exist_ok=True)

def list_images(root: str, exts: List[str], recursive: bool) -> List[str]:
    if os.path.isfile(root): return [root]
    pats = []
    for e in exts:
        pats += [f"**/*.{e}", f"**/*.{e.upper()}"] if recursive else [f"*.{e}", f"*.{e.upper()}"]
    files: List[str] = []
    for pat in pats:
        files.extend(glob.glob(os.path.join(root, pat), recursive=recursive))
    files = [f for f in files if os.path.isfile(f)]
    files.sort()
    return files

def resize_max_edge(img: np.ndarray, max_edge: int) -> np.ndarray:
    if max_edge <= 0: return img
    h, w = img.shape[:2]; m = max(h, w)
    if m <= max_edge: return img
    s = max_edge / float(m)
    return cv2.resize(img, (int(round(w*s)), int(round(h*s))), interpolation=cv2.INTER_AREA)

# ---- Enhancements ----
def to_gray(img_bgr: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

def auto_levels_gray(gray: np.ndarray, low_q=0.01, high_q=0.99) -> np.ndarray:
    g = gray.astype(np.float32)
    lo = float(np.quantile(g, low_q)); hi = float(np.quantile(g, high_q))
    if hi > lo + 1e-6:
        g = np.clip((g - lo) * (255.0 / (hi - lo)), 0, 255)
    return g.astype(np.uint8)

def apply_clahe(gray: np.ndarray, clip=2.2, tile=(8,8)) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=float(clip), tileGridSize=tuple(map(int, tile)))
    return clahe.apply(gray)

def unsharp_mask(gray: np.ndarray, amount=0.5, radius=1.2) -> np.ndarray:
    if amount <= 0: return gray
    blur = cv2.GaussianBlur(gray, (0,0), radius)
    sharp = cv2.addWeighted(gray, 1.0 + amount, blur, -amount, 0)
    return np.clip(sharp, 0, 255).astype(np.uint8)

def fast_denoise(gray: np.ndarray, strength=0.0) -> np.ndarray:
    if strength <= 0: return gray
    h = float(strength)
    return cv2.fastNlMeansDenoising(gray, None, h, 7, 21)

def bw_fix(img_bgr: np.ndarray, args) -> np.ndarray:
    g = to_gray(img_bgr)
    if args.clahe:
        g = apply_clahe(g, clip=args.clip_limit, tile=args.tile)
    g = auto_levels_gray(g, args.low_q, args.high_q)
    if args.denoise > 0:
        g = fast_denoise(g, args.denoise)
    if args.sharpen > 0:
        g = unsharp_mask(g, amount=args.sharpen, radius=1.2)
    return g

def side_by_side(a: np.ndarray, b_gray: np.ndarray, max_h=800) -> np.ndarray:
    def resize_h(x, h):
        s = h / x.shape[0]
        return cv2.resize(x, (int(x.shape[1]*s), h), interpolation=cv2.INTER_AREA)
    a2 = resize_h(a, max_h)
    b3 = cv2.cvtColor(resize_h(b_gray, max_h), cv2.COLOR_GRAY2BGR)
    pad = np.ones((max_h, 16, 3), np.uint8) * 255
    return np.hstack([a2, pad, b3])

def process_one(src: str, dst: str, args):
    img = imread_color(src)
    if args.max_edge > 0:
        img = resize_max_edge(img, args.max_edge)
    out = bw_fix(img, args)

    ext = args.format.lower() if args.format else os.path.splitext(dst)[1][1:].lower()
    params = []
    if ext in ("jpg", "jpeg"):
        params = [int(cv2.IMWRITE_JPEG_QUALITY), int(args.quality)]
    elif ext == "png":
        params = [int(cv2.IMWRITE_PNG_COMPRESSION), 3]

    ensure_dir(os.path.dirname(dst))
    cv2.imwrite(dst, out, params)

    if args.preview:
        pre = os.path.splitext(dst)[0] + "_preview.jpg"
        combo = side_by_side(img, out, 800)
        cv2.imwrite(pre, combo, [int(cv2.IMWRITE_JPEG_QUALITY), 90])

def main():
    ap = argparse.ArgumentParser(description="Convert photos to clean B&W (grayscale) with gentle enhancement.")
    ap.add_argument("--input", required=True, help="Image file or directory")
    ap.add_argument("--out", required=True, help="Output directory")
    ap.add_argument("--recursive", action="store_true", help="Recurse into subfolders")
    ap.add_argument("--inplace", action="store_true", help="Overwrite existing files (use carefully)")
    ap.add_argument("--extensions", default="jpg,jpeg,png,tif,tiff,bmp", help="Comma-separated list of extensions to include")
    ap.add_argument("--suffix", default="_bw", help="Suffix to add before extension unless --inplace")
    ap.add_argument("--format", default="", help="Force output format (jpg/png/tiff). Default: keep input extension")
    ap.add_argument("--quality", type=int, default=92, help="JPEG quality if writing JPG")
    ap.add_argument("--max-edge", type=int, default=0, help="Optionally downscale so longest edge <= this (0=off)")
    ap.add_argument("--preview", action="store_true", help="Write side-by-side (original|B&W) preview images")

    # Enhancement knobs (good defaults)
    ap.add_argument("--low-q", type=float, default=0.01)
    ap.add_argument("--high-q", type=float, default=0.99)
    ap.add_argument("--clahe", action="store_true", default=True)
    ap.add_argument("--clip-limit", type=float, default=2.2)
    ap.add_argument("--tile", default="8,8", help="CLAHE tile grid, e.g., '8,8'")
    ap.add_argument("--sharpen", type=float, default=0.5, help="Unsharp mask amount (0 disables)")
    ap.add_argument("--denoise", type=float, default=0.0, help="Fast denoise strength (0 disables)")

    args = ap.parse_args()
    tile_parts = [int(x) for x in args.tile.split(",")]
    args.tile = (tile_parts[0], tile_parts[1])

    exts = [e.strip().lower() for e in args.extensions.split(",") if e.strip()]
    # Gather files
    if os.path.isfile(args.input):
        files = [args.input]
        in_root = os.path.dirname(os.path.abspath(args.input))
    else:
        files = list_images(args.input, exts, args.recursive)
        in_root = os.path.abspath(args.input)
    if not files:
        print("No input images found."); return

    out_root = os.path.abspath(args.out)
    ensure_dir(out_root)

    total = len(files)
    for idx, src in enumerate(files, 1):
        rel = os.path.relpath(src, in_root) if os.path.isdir(args.input) else os.path.basename(src)
        base, ext = os.path.splitext(rel)
        if args.inplace:
            dst_rel = rel if not args.format else base + "." + args.format.lower()
        else:
            dst_rel = base + args.suffix + "." + (args.format.lower() if args.format else ext[1:].lower())
        dst = os.path.join(out_root, dst_rel)

        print(f"[{idx}/{total}] {src} -> {dst}")
        try:
            process_one(src, dst, args)
        except Exception as e:
            print(f"  ! Error: {e}")

    print(f"Done. Processed {total} file(s). Output root: {out_root}")

if __name__ == "__main__":
    main()
