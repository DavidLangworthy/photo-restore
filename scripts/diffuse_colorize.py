import sys
from pathlib import Path
from PIL import Image
import torch
from diffusers import StableDiffusionImg2ImgPipeline

src = Path(sys.argv[1]).resolve()
outdir = Path(sys.argv[2] if len(sys.argv)>2 else "outputs").resolve()
outdir.mkdir(parents=True, exist_ok=True)

device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
pipe = StableDiffusionImg2ImgPipeline.from_pretrained("runwayml/stable-diffusion-v1-5", safety_checker=None, torch_dtype=torch.float16 if device.type!="cpu" else torch.float32).to(device)

base = Image.open(src).convert("RGB")
prompt = "Natural, muted historical colorization, accurate skin tones, preserved film grain, realistic fabrics, no oversaturation"
seeds = [7, 21, 42]

for s in seeds:
    g = torch.Generator(device=device).manual_seed(s)
    out = pipe(prompt=prompt, image=base, strength=0.3, guidance_scale=6.5, generator=g)
    im = out.images[0]
    im.save(outdir/f"10_sd_seed{s}.png")

print(str(outdir))
