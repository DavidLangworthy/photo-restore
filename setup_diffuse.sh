python3 -m venv venv-photofix-diffuse
source venv-photofix-diffuse/bin/activate
python -m pip install --upgrade pip
pip install torch==2.5.1 torchvision==0.20.1
pip install numpy==1.26.4 pillow tqdm safetensors
pip install transformers==4.44.2 accelerate==0.33.0 diffusers==0.30.0
python - <<'PY'
import torch, transformers, diffusers, accelerate
print("OK:", torch.__version__, transformers.__version__, diffusers.__version__, accelerate.__version__)
PY
deactivate
