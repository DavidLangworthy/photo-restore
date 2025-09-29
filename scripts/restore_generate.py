import sys, os, cv2, numpy as np
from pathlib import Path
from realesrgan import RealESRGANer
from gfpgan import GFPGANer

inp = Path(sys.argv[1]).resolve()
outdir = Path(sys.argv[2] if len(sys.argv)>2 else "outputs").resolve()
outdir.mkdir(parents=True, exist_ok=True)

img = cv2.imread(str(inp), cv2.IMREAD_COLOR)

ups = RealESRGANer(model_path="weights/realesr-general-x4v3.pth", netscale=4, model=None, half=False)
upscaled, _ = ups.enhance(img, outscale=2)
cv2.imwrite(str(outdir/"01_upscaled.png"), upscaled)

restorer = GFPGANer(model_path="weights/GFPGANv1.4.pth", upscale=2, arch="clean", channel_multiplier=2, bg_upsampler=ups)
_, _, restored = restorer.enhance(img, has_aligned=False, only_center_face=False, paste_back=True)
cv2.imwrite(str(outdir/"02_gfpgan.png"), restored)

cv2.imwrite(str(outdir/"00_input.png"), img)
print(str(outdir))
