#!/usr/bin/env python3
"""
auto_correct_smart.py — Heuristic photo fixer for mixed B&W/Color album photos.

What's new (anti-sepia gate)
----------------------------
We were keeping some nearly-monochrome yellow/sepia images as "color".
Now, after the color pipeline, we also require **multi-hue evidence**:
- Enough **different hue bins** are present among saturated pixels.
- No single hue bin dominates.
- Yellow/orange does not dominate.
- If the original Lab b* mean is high (yellow cast), we are even stricter.

Only if **all** color thresholds are met do we keep color; else we fall back to B&W.

Quick start
-----------
pip install opencv-python

python auto_correct_smart.py \
  --input "/path/to/folder" --out "/path/to/out" --recursive --preview
"""

import os, sys, argparse, glob, json
from typing import List, Dict, Tuple
import numpy as np
import cv2

# ---------------- IO ----------------
def imread_color(path: str):
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Could not read: {path}")
    return img

def ensure_dir(p: str): os.makedirs(p, exist_ok=True)

def list_images(root: str, exts: List[str], recursive: bool) -> List[str]:
    if os.path.isfile(root):
        return [root]
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

# --------------- Metrics / classification ---------------
def image_metrics(img_bgr: np.ndarray) -> Dict[str, float]:
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    mean_sat = float(np.mean(hsv[:,:,1]))/255.0

    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    L,a,b = cv2.split(lab)
    a_mean = float(np.mean(a - 128.0))
    b_mean = float(np.mean(b - 128.0))
    a_std  = float(np.std(a - 128.0))
    b_std  = float(np.std(b - 128.0))
    chroma = float(np.mean(np.sqrt((a-128.0)**2 + (b-128.0)**2)))

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)/255.0
    contrast = float(np.std(gray))

    return dict(mean_sat=mean_sat, a_mean=a_mean, b_mean=b_mean,
                a_std=a_std, b_std=b_std, chroma=chroma, contrast=contrast)

def classify_initial(m: Dict[str,float],
                     sat_bw=0.16, chroma_bw=16.0, yellow_b=6.0) -> str:
    if m['mean_sat'] < sat_bw and m['chroma'] < chroma_bw and m['a_std'] < 4.0 and m['b_std'] < 4.0:
        return 'bw_yellowed' if m['b_mean'] > yellow_b else 'bw_neutral'
    return 'maybe_color'

# --------------- Corrections ---------------
def levels_per_channel(img_bgr: np.ndarray, low_q=0.01, high_q=0.99) -> np.ndarray:
    out = img_bgr.astype(np.float32)
    for c in range(3):
        ch = out[:,:,c]
        lo = float(np.quantile(ch, low_q)); hi = float(np.quantile(ch, high_q))
        if hi <= lo + 1e-6: continue
        out[:,:,c] = np.clip((ch - lo) * (255.0/(hi - lo)), 0, 255)
    return out.astype(np.uint8)

def gray_world_wb(img_bgr: np.ndarray) -> np.ndarray:
    b,g,r = cv2.split(img_bgr.astype(np.float32))
    mb, mg, mr = [np.mean(x) + 1e-6 for x in (b,g,r)]
    avg = (mb + mg + mr) / 3.0
    b *= (avg/mb); g *= (avg/mg); r *= (avg/mr)
    return np.clip(cv2.merge((b,g,r)),0,255).astype(np.uint8)

def clahe_gray(img_gray: np.ndarray) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8,8))
    return clahe.apply(img_gray)

def de_yellow_lab(img_bgr: np.ndarray, strength=1.0) -> np.ndarray:
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    L,a,b = cv2.split(lab)
    shift = np.mean(b - 128.0) * strength
    b = b - shift
    out = cv2.cvtColor(np.clip(cv2.merge((L,a,b)),0,255).astype(np.uint8), cv2.COLOR_LAB2BGR)
    return out

def boost_saturation(img_bgr: np.ndarray, factor=1.10) -> np.ndarray:
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    h,s,v = cv2.split(hsv); s = np.clip(s * factor, 0, 255)
    return cv2.cvtColor(np.uint8(cv2.merge((h,s,v))), cv2.COLOR_HSV2BGR)

def to_grayscale_bgr(img_bgr: np.ndarray) -> np.ndarray:
    g = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    g = clahe_gray(g)
    return cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)

def color_pipeline(img_bgr: np.ndarray, low_q=0.01, high_q=0.99) -> np.ndarray:
    out = gray_world_wb(img_bgr)
    out = de_yellow_lab(out, 1.0)
    out = boost_saturation(out, 1.10)
    out = levels_per_channel(out, low_q, high_q)
    return out

# ---------- Hue dispersion stats (anti-sepia) ----------
def hue_dispersion_stats(img_bgr: np.ndarray, s_min=0.20, v_min=0.12, v_max=0.98, bins=36, bin_frac=0.02):
    """Return how spread the hues are among reasonably saturated & valid pixels."""
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    H = hsv[:,:,0]  # 0..180 in OpenCV
    S = hsv[:,:,1] / 255.0
    V = hsv[:,:,2] / 255.0
    mask = (S >= s_min) & (V >= v_min) & (V <= v_max)
    if np.count_nonzero(mask) < 50:
        return dict(num_sig_bins=0, max_bin_frac=0.0, frac_yellow=0.0, total=0)
    H_sel = H[mask].flatten()
    # Histogram on 0..180 with `bins`
    hist, edges = np.histogram(H_sel, bins=bins, range=(0,180))
    total = int(hist.sum())
    if total == 0:
        return dict(num_sig_bins=0, max_bin_frac=0.0, frac_yellow=0.0, total=0)
    frac = hist / total
    num_sig_bins = int(np.sum(frac >= bin_frac))
    max_bin_frac = float(np.max(frac))
    # Yellow/orange sector in HSV roughly ~ [10°, 35°] -> [10,35] in OpenCV units
    y0, y1 = 10, 35
    # Compute fraction in that sector
    # Map each bin center to see if within [y0,y1]
    centers = 0.5*(edges[:-1] + edges[1:])
    yellow_mask = (centers >= y0) & (centers <= y1)
    frac_yellow = float(np.sum(frac[yellow_mask]))
    return dict(num_sig_bins=num_sig_bins, max_bin_frac=max_bin_frac, frac_yellow=frac_yellow, total=total)

# ---------- Post-color decision: keep or fall back to B&W ----------
def color_stats(img_bgr: np.ndarray) -> Dict[str,float]:
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    S = hsv[:,:,1] / 255.0
    S_mean = float(np.mean(S))
    S_p95  = float(np.quantile(S, 0.95))
    S_frac_hi = float(np.mean(S > 0.25))

    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    L,a,b = cv2.split(lab)
    C = np.sqrt((a-128.0)**2 + (b-128.0)**2)
    C_mean = float(np.mean(C))
    C_p90  = float(np.quantile(C, 0.90))
    return dict(S_mean=S_mean, S_p95=S_p95, S_frac_hi=S_frac_hi, C_mean=C_mean, C_p90=C_p90)

def should_keep_color(stats: Dict[str,float], hue: Dict[str,float], initial_b_mean: float, args) -> bool:
    """Keep color only if BOTH global color and hue-dispersion tests pass."""
    global_ok = (stats['S_mean'] >= args.keep_color_sat_mean and
                 stats['S_p95']  >= args.keep_color_sat_p95 and
                 stats['S_frac_hi'] >= args.keep_color_frac and
                 stats['C_mean'] >= args.keep_color_chroma_mean and
                 stats['C_p90']  >= args.keep_color_chroma_p90)
    if not global_ok:
        return False

    # Hue spread gate (anti-sepia)
    #  - require enough significant bins and low dominance of a single bin
    #  - penalize yellow dominance, especially when original b* mean is high
    bins_ok = hue['num_sig_bins'] >= args.min_hue_bins and hue['max_bin_frac'] <= args.max_dominant_bin
    yellow_ok = hue['frac_yellow'] <= args.max_yellow_frac
    # If the original had a strong yellow cast, tighten the yellow limit
    if initial_b_mean >= args.b_sepia_cut:
        yellow_ok = hue['frac_yellow'] <= (args.max_yellow_frac * 0.6)  # stricter
        bins_ok = bins_ok and (hue['max_bin_frac'] <= min(args.max_dominant_bin, 0.45))
    return bins_ok and yellow_ok

# --------------- Pipeline ---------------
def process_one(path: str, out_path: str, args, log_fh):
    img = imread_color(path)
    if args.max_edge > 0: img = resize_max_edge(img, args.max_edge)

    # initial metrics & class
    m0 = image_metrics(img)
    if args.force_bw: label = 'bw_neutral'
    elif args.force_color: label = 'maybe_color'
    else: label = classify_initial(m0, args.sat_bw, args.chroma_bw, args.yellow_b)

    if label.startswith('bw'):
        fixed = to_grayscale_bgr(img)
        final_label = label
        kept_color = False
        stats = {}; hue = {}
    else:
        cand = color_pipeline(img, args.low_q, args.high_q)
        stats = color_stats(cand)
        hue = hue_dispersion_stats(cand, s_min=args.hue_s_min, v_min=0.12, v_max=0.98,
                                   bins=args.hue_bins, bin_frac=args.hue_bin_frac)
        if should_keep_color(stats, hue, m0['b_mean'], args):
            fixed = cand; final_label = 'color_faded'; kept_color = True
        else:
            fixed = to_grayscale_bgr(img); final_label = 'bw_from_color_fallback'; kept_color = False

        if args.save_both:
            base, ext = os.path.splitext(out_path)
            ext_out = (args.format.lower() if args.format else ext[1:].lower())
            params = []
            if ext_out in ('jpg','jpeg'): params=[int(cv2.IMWRITE_JPEG_QUALITY), int(args.quality)]
            elif ext_out=='png': params=[int(cv2.IMWRITE_PNG_COMPRESSION), 3]
            ensure_dir(os.path.dirname(out_path))
            cv2.imwrite(base + "_color." + ext_out, cand, params)
            cv2.imwrite(base + "_bw." + ext_out, to_grayscale_bgr(img), params)

    # write output
    ext_out = args.format.lower() if args.format else os.path.splitext(out_path)[1][1:].lower()
    params = []
    if ext_out in ('jpg','jpeg'): params=[int(cv2.IMWRITE_JPEG_QUALITY), int(args.quality)]
    elif ext_out=='png': params=[int(cv2.IMWRITE_PNG_COMPRESSION), 3]
    ensure_dir(os.path.dirname(out_path)); cv2.imwrite(out_path, fixed, params)

    # preview
    if args.preview:
        combo = side_by_side(img, fixed, max_h=800)
        pre_path = os.path.splitext(out_path)[0] + "_preview.jpg"
        cv2.imwrite(pre_path, combo, [int(cv2.IMWRITE_JPEG_QUALITY), 90])

    # log
    log_fh.write(json.dumps({
        "file": path, "out": out_path, "class": final_label,
        "initial": m0, "keep_color_stats": stats, "hue_dispersion": hue, "kept_color": kept_color
    }) + "\n")

def side_by_side(a: np.ndarray, b: np.ndarray, max_h=800) -> np.ndarray:
    def resize_h(x, h):
        s = h / x.shape[0]
        return cv2.resize(x, (int(x.shape[1]*s), h), interpolation=cv2.INTER_AREA)
    a2, b2 = resize_h(a, max_h), resize_h(b, max_h)
    pad = np.ones((max_h, 16, 3), np.uint8) * 255
    return np.hstack([a2, pad, b2])

def main():
    ap = argparse.ArgumentParser(description="Heuristic auto-correct for mixed B&W/Color album photos with anti-sepia gating.")
    ap.add_argument("--input", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--recursive", action="store_true"); ap.add_argument("--inplace", action="store_true")
    ap.add_argument("--extensions", default="jpg,jpeg,png,tif,tiff,bmp")
    ap.add_argument("--suffix", default="_fixed"); ap.add_argument("--format", default="")
    ap.add_argument("--quality", type=int, default=92); ap.add_argument("--preview", action="store_true")
    ap.add_argument("--max-edge", type=int, default=0)

    # initial classification thresholds (conservative)
    ap.add_argument("--sat-bw", type=float, default=0.16)
    ap.add_argument("--chroma-bw", type=float, default=16.0)
    ap.add_argument("--yellow-b", type=float, default=6.0)

    # post-color global thresholds
    ap.add_argument("--keep-color-sat-mean", type=float, default=0.20)
    ap.add_argument("--keep-color-sat-p95",  type=float, default=0.35)
    ap.add_argument("--keep-color-frac",     type=float, default=0.12)  # fraction of pixels with S>0.25
    ap.add_argument("--keep-color-chroma-mean", type=float, default=22.0)
    ap.add_argument("--keep-color-chroma-p90",  type=float, default=35.0)

    # hue-dispersion (anti-sepia) thresholds
    ap.add_argument("--hue-s-min", type=float, default=0.20, help="Saturation minimum to consider a pixel for hue stats")
    ap.add_argument("--hue-bins", type=int, default=36, help="Histogram bins across 0..180 OpenCV hue")
    ap.add_argument("--hue-bin-frac", type=float, default=0.02, help="Fraction threshold for a bin to count as 'significant'")
    ap.add_argument("--min-hue-bins", type=int, default=4, help="Minimum significant hue bins required to keep color")
    ap.add_argument("--max-dominant-bin", type=float, default=0.50, help="Reject if any single hue bin exceeds this fraction")
    ap.add_argument("--max-yellow-frac", type=float, default=0.65, help="Reject if yellow/orange fraction exceeds this")
    ap.add_argument("--b-sepia-cut", type=float, default=15.0, help="If initial Lab b* mean exceeds this, be stricter")

    # levels strength
    ap.add_argument("--low-q", type=float, default=0.01)
    ap.add_argument("--high-q", type=float, default=0.99)

    # ambiguity helpers
    ap.add_argument("--force-bw", action="store_true")
    ap.add_argument("--force-color", action="store_true")
    ap.add_argument("--save-both", action="store_true")

    args = ap.parse_args()

    exts = [e.strip().lower() for e in args.extensions.split(",") if e.strip()]
    files = list_images(args.input, exts, args.recursive)
    if not files: print("No input images found."); return

    in_root = os.path.abspath(args.input if os.path.isdir(args.input) else os.path.dirname(args.input))
    out_root = os.path.abspath(args.out); ensure_dir(out_root)
    log_path = os.path.join(out_root, "auto_correct_smart.log.jsonl")

    with open(log_path, "w") as log_fh:
        total = len(files)
        for idx, src in enumerate(files, 1):
            rel = os.path.relpath(src, in_root) if os.path.isdir(args.input) else os.path.basename(src)
            base, ext = os.path.splitext(rel)
            if args.inplace:
                dst_rel = rel if not args.format else base + "." + args.format.lower()
            else:
                dst_rel = base + args.suffix + "." + (args.format.lower() if args.format else ext[1:].lower())
            out_path = os.path.join(out_root, dst_rel)

            print(f"[{idx}/{total}] {src} -> {out_path}")
            try:
                process_one(src, out_path, args, log_fh)
            except Exception as e:
                print(f"  ! Error: {e}")

    print(f"Done. Outputs at: {out_root}\nLog: {log_path}")

if __name__ == "__main__":
    main()
