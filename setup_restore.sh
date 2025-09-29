#!/usr/bin/env bash
set -euo pipefail

ENV_DIR="venv-photofix-restore"
python3 -m venv "$ENV_DIR"
source "$ENV_DIR/bin/activate"
python -m pip install --upgrade pip

# Torch stack
pip install torch==2.1.2 torchvision==0.16.2

# Core utilities
pip install numpy==1.26.4 opencv-python==4.8.1.78 pillow tqdm

# Restoration libs
pip install basicsr==1.4.2 facexlib==0.3.0 realesrgan==0.3.0 gfpgan==1.3.8

# Download weights
mkdir -p weights
[ ! -f weights/realesr-general-x4v3.pth ] && curl -L -o weights/realesr-general-x4v3.pth https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth
[ ! -f weights/GFPGANv1.4.pth ] && curl -L -o weights/GFPGANv1.4.pth https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth
[ ! -f weights/codeformer.pth ] && curl -L -o weights/codeformer.pth https://github.com/sczhou/CodeFormer/releases/download/v0.1.0/codeformer.pth

# Inline ping test
python - <<'PY'
import torch, numpy as np
from realesrgan import RealESRGANer
from basicsr.archs.rrdbnet_arch import RRDBNet

print("torch:", torch.__version__, "MPS:", torch.backends.mps.is_available())

# Construct the expected RRDBNet for realesr-general-x4v3.pth
model = RRDBNet(
    num_in_ch=3,
    num_out_ch=3,
    num_feat=64,
    num_block=23,
    num_grow_ch=32,
    scale=4
)

# This will internally call load_state_dict with strict=False to handle minor mismatches
ups = RealESRGANer(
    scale=4,
    model_path="weights/realesr-general-x4v3.pth",
    model=model,
    tile=0,
    tile_pad=10,
    pre_pad=0,
    half=False
)

dummy = np.zeros((32,32,3), dtype=np.uint8)
out, _ = ups.enhance(dummy, outscale=2)
print("RealESRGAN OK:", out.shape)

import gfpgan
print("GFPGAN import OK")

sd = torch.load("weights/codeformer.pth", map_location="cpu")
print("CodeFormer weights OK:", isinstance(sd, (dict, torch.nn.modules.module.OrderedDict)))
PY

deactivate
echo "Setup complete."
