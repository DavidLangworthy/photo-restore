#!/usr/bin/env python3
# (see header in previous attempt) — Batch auto-correct photos
import os, sys, argparse, glob
from typing import List
import numpy as np
import cv2

def imread_color(path: str):
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Could not read: {path}")
    return img

def ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)

def list_images(root: str, exts: List[str], recursive: bool) -> List[str]:
    if os.path.isfile(root):
        return [root]
    pats = []
    for e in exts:
        pats.append(f"**/*.{e}" if recursive else f"*.{e}")
        pats.append(f"**/*.{e.upper()}" if recursive else f"*.{e.upper()}")
    files: List[str] = []
    for pat in pats:
        files.extend(glob.glob(os.path.join(root, pat), recursive=recursive))
    files = [f for f in files if os.path.isfile(f)]
    files.sort()
    return files

def auto_levels_per_channel(img_bgr: np.ndarray, low_q=0.01, high_q=0.99) -> np.ndarray:
    out = img_bgr.astype(np.float32)
    for c in range(3):
        ch = out[:, :, c]
        lo = float(np.quantile(ch, low_q))
        hi = float(np.quantile(ch, high_q))
        if hi <= lo + 1e-6:
            continue
        out[:, :, c] = np.clip((ch - lo) * (255.0 / (hi - lo)), 0, 255)
    return out.astype(np.uint8)

def gray_world_wb(img_bgr: np.ndarray) -> np.ndarray:
    b, g, r = cv2.split(img_bgr.astype(np.float32))
    mb, mg, mr = [np.mean(x) + 1e-6 for x in (b, g, r)]
    avg = (mb + mg + mr) / 3.0
    b *= (avg / mb); g *= (avg / mg); r *= (avg / mr)
    out = cv2.merge((b, g, r))
    return np.clip(out, 0, 255).astype(np.uint8)

def auto_correct(img_bgr: np.ndarray, low_q=0.01, high_q=0.99) -> np.ndarray:
    return auto_levels_per_channel(gray_world_wb(img_bgr), low_q, high_q)

def resize_max_edge(img: np.ndarray, max_edge: int) -> np.ndarray:
    h, w = img.shape[:2]
    m = max(h, w)
    if m <= max_edge or max_edge <= 0:
        return img
    scale = max_edge / float(m)
    nw, nh = int(round(w * scale)), int(round(h * scale))
    return cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)

def process_one(src_path: str, dst_path: str, args):
    img = imread_color(src_path)
    if args.max_edge > 0:
        img = resize_max_edge(img, args.max_edge)
    out = auto_correct(img, args.low_q, args.high_q)
    ext = args.format.lower() if args.format else os.path.splitext(dst_path)[1][1:].lower()
    params = []
    if ext in ("jpg", "jpeg"):
        params = [int(cv2.IMWRITE_JPEG_QUALITY), int(args.quality)]
    elif ext == "png":
        params = [int(cv2.IMWRITE_PNG_COMPRESSION), 3]
    ensure_dir(os.path.dirname(dst_path))
    cv2.imwrite(dst_path, out, params)

def main():
    ap = argparse.ArgumentParser(description="Batch auto-correct photos (no splitting).")
    ap.add_argument("--input", required=True, help="Image file or directory")
    ap.add_argument("--out", required=True, help="Output directory (can be same as input with --inplace)")
    ap.add_argument("--recursive", action="store_true", help="Recurse into subfolders")
    ap.add_argument("--inplace", action="store_true", help="Overwrite existing files (use carefully)")
    ap.add_argument("--extensions", default="jpg,jpeg,png,tif,tiff,bmp", help="Comma list of extensions to include")
    ap.add_argument("--suffix", default="_ac", help="Suffix to add before extension unless --inplace")
    ap.add_argument("--format", default="", help="Force output format (jpg/png/tiff). Default: keep input extension")
    ap.add_argument("--quality", type=int, default=92, help="JPEG quality when writing JPG")
    ap.add_argument("--low-q", type=float, default=0.01, help="Lower quantile for auto-levels")
    ap.add_argument("--high-q", type=float, default=0.99, help="Upper quantile for auto-levels")
    ap.add_argument("--max-edge", type=int, default=0, help="Optionally downscale so longest edge <= max-edge (0=off)")
    args = ap.parse_args()

    exts = [e.strip().lower() for e in args.extensions.split(",") if e.strip()]
    files = list_images(args.input, exts, args.recursive)
    if not files:
        print("No input images found."); return

    in_root = os.path.abspath(args.input if os.path.isdir(args.input) else os.path.dirname(args.input))
    out_root = os.path.abspath(args.out)
    ensure_dir(out_root)

    total = len(files)
    for idx, src in enumerate(files, 1):
        if os.path.isdir(args.input):
            rel = os.path.relpath(src, in_root)
        else:
            rel = os.path.basename(src)
        base, ext = os.path.splitext(rel)
        if args.inplace:
            dst_rel = rel if not args.format else base + "." + args.format.lower()
        else:
            dst_rel = base + args.suffix + "." + (args.format.lower() if args.format else ext[1:].lower())
        dst_path = os.path.join(out_root, dst_rel)

        print(f"[{idx}/{total}] {src} -> {dst_path}")
        try:
            process_one(src, dst_path, args)
        except Exception as e:
            print(f"  ! Error processing {src}: {e}")

    print(f"Done. Processed {total} file(s). Output: {out_root}")

if __name__ == "__main__":
    main()
