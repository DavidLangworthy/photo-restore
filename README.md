# Photo Restoration & Colorization Pipeline

This project provides a reproducible workflow to **restore** and **colorize** old photos using state-of-the-art models.  
It separates the stack into two virtual environments to avoid dependency conflicts:
- **Restore** (`venv-photofix-restore`): Real-ESRGAN, GFPGAN, CodeFormer
- **Diffuse** (`venv-photofix-diffuse`): Stable Diffusion (diffusers/transformers)

An orchestrator script ties everything together and produces a **contact sheet** with multiple restoration/colorization variants so you can quickly pick the best-looking output.

---

## For Users

### Prerequisites
- Python 3.11
- `virtualenv` installed (`python3 -m pip install virtualenv`)
- macOS with Apple Silicon (M1/M2/M3) preferred, uses PyTorch MPS acceleration

### Setup
1. Clone this repo and `cd` into it.
2. Create the two virtual environments:

```bash
# Restore env
python3 -m venv venv-photofix-restore
source venv-photofix-restore/bin/activate
pip install --upgrade pip
pip install torch==2.5.1 torchvision==0.20.1
pip install numpy==1.26.4 opencv-python==4.8.1.78 pillow tqdm
pip install basicsr==1.4.2 facexlib==0.3.0 realesrgan==0.3.0 gfpgan==1.3.8
deactivate

# Diffuse env
python3 -m venv venv-photofix-diffuse
source venv-photofix-diffuse/bin/activate
pip install --upgrade pip
pip install torch==2.5.1 torchvision==0.20.1
pip install numpy==1.26.4 pillow tqdm safetensors
pip install transformers==4.44.2 accelerate==0.33.0 diffusers==0.30.0
deactivate
```

3. Ensure `weights/` contains:
   - `realesr-general-x4v3.pth`
   - `GFPGANv1.4.pth`
   - `codeformer.pth`

### Usage
Run the orchestrator with an input photo:

```bash
./orchestrate.sh path/to/photo.jpg outputs
```

This will generate:
- `00_input.png` (original)
- `01_upscaled.png` (Real-ESRGAN)
- `02_gfpgan.png` (GFPGAN face-restored)
- `10_sd_seed*.png` (Stable Diffusion colorizations with different seeds)
- `contact_sheet.jpg` (grid of all results for easy comparison)

---

## For Maintainers

### Structure
- `scripts/restore_generate.py`  
  Runs in `venv-photofix-restore`. Upscales with Real-ESRGAN and restores with GFPGAN.
- `scripts/diffuse_colorize.py`  
  Runs in `venv-photofix-diffuse`. Uses Stable Diffusion (img2img) for colorization.
- `scripts/contact_sheet.py`  
  Assembles all generated variants into one grid.
- `orchestrate.sh`  
  Shell wrapper that switches envs and runs the above in sequence.

### Notes
- **Environment split** is deliberate to prevent `torchvision/transformers` incompatibilities.
- `weights/` is not committed; users must download required `.pth` files separately.
- Add new models by extending `restore_generate.py` or `diffuse_colorize.py`.
- Keep package pins strict to avoid breakage (`torch==2.5.1`, `torchvision==0.20.1`, `numpy==1.26.4`, etc.).

### Roadmap
- Optional integration of CodeFormer (face fidelity control).
- Support for LaMa (inpainting scratches/tears).
- GUI wrapper (e.g., streamlit) for non-technical users.

---

## License
MIT (or adjust if you prefer another).
