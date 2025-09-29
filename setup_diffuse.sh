#!/usr/bin/env bash
set -euo pipefail

ENV_DIR="venv-photofix-diffuse"
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

# Core torch stack for diffusion workflows
pip install torch==2.5.1 torchvision==0.20.1

# Base utilities and tensor helpers
pip install numpy==1.26.4 pillow tqdm safetensors

# Diffusion toolkit
pip install transformers==4.44.2 accelerate==0.33.0 diffusers==0.30.0

# Inline smoke test
python - <<'PY'
import torch
import transformers
import diffusers
import accelerate

print(
    "torch", torch.__version__,
    "cuda", torch.cuda.is_available(),
    "mps", getattr(torch.backends, "mps", None) and torch.backends.mps.is_available(),
)
print(
    "transformers", transformers.__version__,
    "diffusers", diffusers.__version__,
    "accelerate", accelerate.__version__,
)
PY

deactivate
echo "Diffuse setup complete."
