#!/usr/bin/env python3
"""
convert_tif_to_jpg.py — Recursively convert .tif/.tiff images to .jpg next to originals.

- Keeps resolution and aspect ratio.
- Minimal compression loss (JPEG quality 95 by default).
- Leaves originals untouched.
- Drops new .jpg files alongside originals.

Usage:
  python convert_tif_to_jpg.py --input "/path/to/folder" --recursive
"""

import os, argparse, glob, cv2, numpy as np

def imread_any(path: str):
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:
        img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(f"Could not read: {path}")
    return img

def list_tifs(root: str, recursive: bool):
    patterns = ["*.tif", "*.tiff", "*.TIF", "*.TIFF"]
    files = []
    for pat in patterns:
        files.extend(glob.glob(os.path.join(root, "**" if recursive else "", pat), recursive=recursive))
    return sorted(files)

def convert_one(src: str, quality: int = 95):
    base, _ = os.path.splitext(src)
    dst = base + ".jpg"
    img = imread_any(src)

    # Handle multi-channel/alpha TIFFs
    if img.ndim == 2:
        bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif img.shape[2] == 4:
        bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    else:
        bgr = img

    ok = cv2.imwrite(dst, bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if ok:
        print(f"Converted: {src} -> {dst}")
    else:
        print(f"FAILED: {src}")

def main():
    ap = argparse.ArgumentParser(description="Convert .tif/.tiff to .jpg next to originals.")
    ap.add_argument("--input", required=True, help="Input file or directory")
    ap.add_argument("--recursive", action="store_true", help="Recurse into subfolders")
    ap.add_argument("--quality", type=int, default=95, help="JPEG quality (default 95)")
    args = ap.parse_args()

    if os.path.isfile(args.input):
        files = [args.input]
    else:
        files = list_tifs(args.input, args.recursive)

    if not files:
        print("No TIFF files found."); return

    print(f"Found {len(files)} TIFF files.")
    for i, f in enumerate(files, 1):
        print(f"[{i}/{len(files)}] {f}")
        try:
            convert_one(f, quality=args.quality)
        except Exception as e:
            print(f"  ! Error converting {f}: {e}")

    print("Done.")

if __name__ == "__main__":
    main()
