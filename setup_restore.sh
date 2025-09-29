#!/usr/bin/env bash
set -euo pipefail

ENV_DIR="venv-photofix-restore"
PYTHON_BIN=${PYTHON_BIN:-python3.11}

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN=python3
fi

echo "Using Python interpreter: $PYTHON_BIN"

if [ -d "$ENV_DIR" ]; then
  echo "Removing existing virtual environment at $ENV_DIR"
  rm -rf "$ENV_DIR"
fi

"$PYTHON_BIN" -m venv "$ENV_DIR"
source "$ENV_DIR/bin/activate"
python -m pip install --upgrade pip

# Torch stack (macOS arm64 wheels ship with MPS support in 2.5.x)
pip install torch==2.5.1 torchvision==0.20.1

# Core utilities
pip install numpy==1.26.4 opencv-python pillow tqdm

# Restoration libs
pip install basicsr==1.4.2 facexlib==0.3.0 realesrgan==0.3.0 gfpgan==1.3.8

# TorchVision 0.20 dropped functional_tensor — provide a compatibility shim for basicsr
python - <<'PY'
from pathlib import Path
import importlib

torchvision = importlib.import_module("torchvision")
shim = Path(torchvision.__file__).resolve().parent / "transforms" / "functional_tensor.py"
if not shim.exists():
    shim.write_text(
        "from torchvision.transforms.functional import rgb_to_grayscale\n\n__all__ = ['rgb_to_grayscale']\n"
    )
PY

# Download weights
mkdir -p weights
[ ! -f weights/realesr-general-x4v3.pth ] && curl -L -o weights/realesr-general-x4v3.pth https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth
[ ! -f weights/GFPGANv1.4.pth ] && curl -L -o weights/GFPGANv1.4.pth https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth
[ ! -f weights/codeformer.pth ] && curl -L -o weights/codeformer.pth https://github.com/sczhou/CodeFormer/releases/download/v0.1.0/codeformer.pth

# Inline ping test
python - <<'PY'
import torch
import numpy as np
from realesrgan import RealESRGANer
from realesrgan.archs.srvgg_arch import SRVGGNetCompact

print("torch:", torch.__version__, "MPS:", torch.backends.mps.is_available())

model = SRVGGNetCompact(
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
    model=model,
    tile=0,
    tile_pad=10,
    pre_pad=0,
    half=False
)

dummy = np.zeros((32, 32, 3), dtype=np.uint8)
output, _ = ups.enhance(dummy, outscale=2)
print("RealESRGAN OK:", output.shape)

import gfpgan
print("GFPGAN import OK")

state = torch.load("weights/codeformer.pth", map_location="cpu")
print("CodeFormer weights OK:", isinstance(state, (dict, torch.nn.modules.module.OrderedDict)))
PY

deactivate
echo "Setup complete."
