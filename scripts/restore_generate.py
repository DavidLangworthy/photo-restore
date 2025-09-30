import sys, os, cv2, numpy as np
from pathlib import Path

from realesrgan import RealESRGANer
from realesrgan.archs.srvgg_arch import SRVGGNetCompact
from gfpgan import GFPGANer

inp = Path(sys.argv[1]).resolve()
outdir = Path(sys.argv[2] if len(sys.argv)>2 else "outputs").resolve()
outdir.mkdir(parents=True, exist_ok=True)

img = cv2.imread(str(inp), cv2.IMREAD_COLOR)
if img is None:
    raise FileNotFoundError(f"Unable to read input image: {inp}")

realesr_model = SRVGGNetCompact(
    num_in_ch=3,
    num_out_ch=3,
    num_feat=64,
    num_conv=32,
    upscale=4,
    act_type='prelu'
)

ups = RealESRGANer(
    scale=4,
    model_path="weights/realesr-general-x4v3.pth",
    model=realesr_model,
    tile=0,
    tile_pad=10,
    pre_pad=0,
    half=False
)
upscaled, _ = ups.enhance(img, outscale=2)
cv2.imwrite(str(outdir/"01_upscaled.png"), upscaled)

restorer = GFPGANer(model_path="weights/GFPGANv1.4.pth", upscale=2, arch="clean", channel_multiplier=2, bg_upsampler=ups)
_, _, restored = restorer.enhance(img, has_aligned=False, only_center_face=False, paste_back=True)
cv2.imwrite(str(outdir/"02_gfpgan.png"), restored)

cv2.imwrite(str(outdir/"00_input.png"), img)
print(str(outdir))
