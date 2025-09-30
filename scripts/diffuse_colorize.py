import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
import torch
from diffusers import StableDiffusionControlNetImg2ImgPipeline, ControlNetModel


src = Path(sys.argv[1]).resolve()
outdir = Path(sys.argv[2] if len(sys.argv) > 2 else "outputs").resolve()
outdir.mkdir(parents=True, exist_ok=True)


def resize_to_multiple(im: Image.Image, max_side: int = 1024, factor: int = 8) -> Image.Image:
    width, height = im.size
    scale = min(max_side / max(width, height), 1.0)
    new_width = max(factor, int((width * scale) // factor * factor))
    new_height = max(factor, int((height * scale) // factor * factor))
    return im.resize((new_width, new_height), Image.LANCZOS)


def pil_to_cv(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def cv_to_pil(img: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))


def lock_luminance(orig_rgb_pil: Image.Image, colored_rgb_pil: Image.Image) -> Image.Image:
    orig_cv = pil_to_cv(orig_rgb_pil)
    colored_cv = pil_to_cv(colored_rgb_pil)

    orig_lab = cv2.cvtColor(orig_cv, cv2.COLOR_BGR2Lab)
    colored_lab = cv2.cvtColor(colored_cv, cv2.COLOR_BGR2Lab)

    colored_lab[..., 0] = orig_lab[..., 0]
    fused_bgr = cv2.cvtColor(colored_lab, cv2.COLOR_Lab2BGR)
    return cv_to_pil(fused_bgr)


device = "mps" if torch.backends.mps.is_available() else "cpu"

controlnet = ControlNetModel.from_pretrained(
    "lllyasviel/sd-controlnet-canny",
    torch_dtype=torch.float32,
)
pipe = StableDiffusionControlNetImg2ImgPipeline.from_pretrained(
    "runwayml/stable-diffusion-v1-5",
    controlnet=controlnet,
    safety_checker=None,
    torch_dtype=torch.float32,
).to(device)
pipe.enable_attention_slicing()
pipe.enable_vae_slicing()

base = Image.open(src).convert("RGB")
base = resize_to_multiple(base, max_side=1024, factor=8)

cv_base = pil_to_cv(base)
edges = cv2.Canny(cv_base, 100, 200)
edges_bgr = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
conditioning = cv_to_pil(edges_bgr)

prompt = (
    "natural, muted historical colorization, accurate skin tones, preserved film grain, realistic fabrics, "
    "no oversaturation, photo"
)
negative_prompt = (
    "blurry, extra limbs, deformed face, cartoon, painterly, plastic skin, makeup, artifacts, distortion, overprocessed"
)

seeds = [7, 21, 42]
for seed in seeds:
    generator = torch.Generator(device="cpu").manual_seed(seed)
    result = pipe(
        prompt=prompt,
        negative_prompt=negative_prompt,
        image=base,
        control_image=conditioning,
        controlnet_conditioning_scale=1.2,
        strength=0.22,
        guidance_scale=5.0,
        num_inference_steps=28,
        generator=generator,
    )
    colored = result.images[0].convert("RGB")
    fused = lock_luminance(base, colored)
    fused.save(outdir / f"10_sd_seed{seed}.png")

print(str(outdir))
