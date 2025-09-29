#!/usr/bin/env python3
"""
box_split_ff0000.py — Crop strictly INSIDE solid red markers drawn on a page.

Good defaults baked in — most users just need:
    python box_split_ff0000.py --input "/path/to/marked.jpg" --out "/path/to/out" --overlay

What it does
- Detects red (#FF0000-like) regions (solids or thick outlines).
- For each region, scans inward from each side and stops once the red FRACTION
  in that row/column drops below 5%, then crops with a tiny safety margin.
- Optionally applies auto-correction (gray-world WB + per-channel auto-levels).

If you filled the photo entirely red, use the paired tool instead (album_split_from_marked.py),
because the pixels are gone in the marked file.

CLI (full)
----------
python box_split_ff0000.py \
  --input "/path/to/marked_or_folder" \
  --out "/path/to/out" \
  --overlay --autocorrect

Tweaks (rarely needed)
----------------------
--edge-thresh 0.05   # red fraction to consider a scan row/col 'part of the frame'
--margin 2           # extra inset after detecting inner edge
--rmin 220 --gmax 40 --bmax 40  # RGB tolerance for red
--dilate 6           # morphology to fuse frame segments
"""

import os, sys, glob, argparse, json
from typing import List, Tuple
import numpy as np
import cv2

# ---------------- IO helpers ----------------
def imread_color(path: str):
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Could not read: {path}")
    return img

def ensure_dir(p: str): os.makedirs(p, exist_ok=True)
def clamp(v, a, b): return max(a, min(b, v))

def list_images(p: str):
    if os.path.isdir(p):
        out = []
        for ext in ("*.jpg","*.jpeg","*.png","*.tif","*.tiff","*.bmp",
                    "*.JPG","*.JPEG","*.PNG","*.TIF","*.TIFF","*.BMP"):
            out.extend(glob.glob(os.path.join(p, ext)))
        return sorted(out)
    return [p]

# --------------- Auto-correct ---------------
def auto_levels_per_channel(img_bgr, low_q=0.01, high_q=0.99):
    out = img_bgr.astype(np.float32)
    for c in range(3):
        ch = out[:,:,c]
        lo = float(np.quantile(ch, low_q)); hi = float(np.quantile(ch, high_q))
        if hi <= lo + 1e-6: continue
        out[:,:,c] = np.clip((ch - lo) * (255.0/(hi - lo)), 0, 255)
    return out.astype(np.uint8)

def gray_world_wb(img_bgr):
    b,g,r = cv2.split(img_bgr.astype(np.float32))
    mb, mg, mr = [np.mean(x) + 1e-6 for x in (b,g,r)]
    avg = (mb + mg + mr)/3.0
    b *= (avg/mb); g *= (avg/mg); r *= (avg/mr)
    return np.clip(cv2.merge((b,g,r)), 0, 255).astype(np.uint8)

def auto_correct(img_bgr): return auto_levels_per_channel(gray_world_wb(img_bgr), 0.01, 0.99)

# --------------- Red mask -------------------
def red_mask(img_bgr, rmin=220, gmax=40, bmax=40, dilate=6):
    b,g,r = cv2.split(img_bgr)
    m = (r >= rmin) & (g <= gmax) & (b <= bmax)
    m = m.astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3,3), np.uint8), iterations=1)
    if dilate > 0:
        m = cv2.dilate(m, np.ones((dilate, dilate), np.uint8), iterations=1)
    return m

# --------------- Inner box estimation -------
def inner_bbox_from_mask(mask, bbox, edge_thresh=0.05, max_search_ratio=0.25):
    """Scan from each side; stop when red FRACTION < edge_thresh (default 5%)."""
    x1,y1,x2,y2 = bbox
    roi = mask[y1:y2, x1:x2]
    H,W = roi.shape[:2]
    max_top = max(1, int(H * max_search_ratio))
    max_left = max(1, int(W * max_search_ratio))

    def inner_offset(lines, along_rows=True, limit=None):
        lim = (max_top if along_rows else max_left) if limit is None else limit
        lim = min(lim, (lines.shape[0] if along_rows else lines.shape[1]) - 1)
        entered = False
        for i in range(lim):
            frac = np.mean(lines[i, :] > 0) if along_rows else np.mean(lines[:, i] > 0)
            if not entered:
                if frac >= edge_thresh:
                    entered = True   # on the red frame now
                # else: still outside; keep moving
            else:
                if frac < edge_thresh:
                    return i  # first interior row/col after leaving frame
        # Fallback if we never saw both enter+exit: be conservative
        return max(1, lim//4)

    top = inner_offset(roi, along_rows=True)
    bottom = inner_offset(np.flipud(roi), along_rows=True)
    left = inner_offset(roi, along_rows=False)
    right = inner_offset(np.fliplr(roi), along_rows=False)

    return x1 + left, y1 + top, x2 - right, y2 - bottom

# --------------- Per-image process ----------
def process_image(path, out_root, args):
    img = imread_color(path)
    H,W = img.shape[:2]
    base = os.path.splitext(os.path.basename(path))[0]
    out_dir = os.path.join(out_root, base)
    ensure_dir(out_dir)

    mask = red_mask(img, rmin=args.rmin, gmax=args.gmax, bmax=args.bmax, dilate=args.dilate)
    if args.dump_mask:
        cv2.imwrite(os.path.join(out_dir, f"{base}_mask.png"), mask)

    contours,_ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    min_w, min_h = int(W*args.min_size_w), int(H*args.min_size_h)
    for c in contours:
        x,y,wc,hc = cv2.boundingRect(c)
        if wc < min_w or hc < min_h: 
            continue
        boxes.append((x,y,x+wc,y+hc))
    boxes.sort(key=lambda b: (b[1]//100, b[0]))

    crops = []
    for i,b in enumerate(boxes,1):
        in_x1,in_y1,in_x2,in_y2 = inner_bbox_from_mask(mask, b, edge_thresh=args.edge_thresh, max_search_ratio=args.max_search)
        xi1 = clamp(in_x1 + args.margin, 0, W-1)
        yi1 = clamp(in_y1 + args.margin, 0, H-1)
        xi2 = clamp(in_x2 - args.margin, 0, W-1)
        yi2 = clamp(in_y2 - args.margin, 0, H-1)
        if xi2 <= xi1 or yi2 <= yi1: 
            continue
        crop = img[yi1:yi2, xi1:xi2].copy()
        if args.autocorrect:
            crop = auto_correct(crop)
        out_name = f"{base}_crop_{i:02d}.{args.format}"
        out_path = os.path.join(out_dir, out_name)
        if args.format.lower() in ("jpg","jpeg"):
            cv2.imwrite(out_path, crop, [int(cv2.IMWRITE_JPEG_QUALITY), int(args.quality)])
        else:
            cv2.imwrite(out_path, crop)
        crops.append(out_path)

    if args.overlay:
        ov = img.copy()
        for b in boxes:
            in_x1,in_y1,in_x2,in_y2 = inner_bbox_from_mask(mask, b, edge_thresh=args.edge_thresh, max_search_ratio=args.max_search)
            cv2.rectangle(ov,(in_x1,in_y1),(in_x2,in_y2),(0,255,255),6)
        cv2.imwrite(os.path.join(out_dir, f"{base}_overlay_boxes.jpg"), ov)

    return len(crops)

# --------------- CLI ------------------------
def main():
    ap = argparse.ArgumentParser(description="Crop strictly INSIDE red markers (solid or thick outlines).")
    ap.add_argument("--input", required=True, help="Marked image or directory")
    ap.add_argument("--out", required=True, help="Output directory")
    ap.add_argument("--overlay", action="store_true", help="Write inner-box overlay")
    ap.add_argument("--dump-mask", action="store_true", help="Write red mask")
    ap.add_argument("--autocorrect", action="store_true", help="Apply auto WB + levels to crops")
    # Good defaults
    ap.add_argument("--margin", type=int, default=2, help="Extra inset past inner edge (px)")
    ap.add_argument("--edge-thresh", type=float, default=0.05, help="Row/col counts as frame if red fraction >= this")
    ap.add_argument("--rmin", type=int, default=220); ap.add_argument("--gmax", type=int, default=40); ap.add_argument("--bmax", type=int, default=40)
    ap.add_argument("--dilate", type=int, default=6, help="Dilation to fuse frame segments (px)")
    ap.add_argument("--min-size-w", type=float, default=0.06, help="Min width fraction of page")
    ap.add_argument("--min-size-h", type=float, default=0.06, help="Min height fraction of page")
    ap.add_argument("--format", default="jpg", choices=["jpg","png","tiff"]); ap.add_argument("--quality", type=int, default=92)
    ap.add_argument("--max-search", type=float, default=0.25, help="Max fraction of the bbox to scan from each edge")
    args = ap.parse_args()

    ensure_dir(args.out)
    files = list_images(args.input)
    total_crops = 0
    for f in files:
        total_crops += process_image(f, args.out, args)

    print(f"[DONE] Crops written: {total_crops}")

if __name__ == "__main__":
    main()
