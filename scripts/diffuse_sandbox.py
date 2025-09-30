"""Quick iteration harness for stable diffusion colorization settings."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
from PIL import Image
import torch
from diffusers import StableDiffusionControlNetImg2ImgPipeline, ControlNetModel


@dataclass(frozen=True)
class RunSpec:
    tag: str
    strength: float
    guidance_scale: float
    control_scale: float = 1.2
    steps: int = 24


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="Path to the source image (RGB).")
    parser.add_argument("outdir", type=Path, help="Directory to place generated previews.")
    parser.add_argument(
        "--max-side",
        type=int,
        default=768,
        help="Resize the longer side to this value (multiple of 8).",
    )
    parser.add_argument(
        "--seeds",
        type=int,
        nargs="*",
        default=[21],
        help="Seeds to test (default: 21).",
    )
    return parser.parse_args()


def resize_to_multiple(im: Image.Image, max_side: int, factor: int = 8) -> Image.Image:
    width, height = im.size
    scale = min(max_side / max(width, height), 1.0)
    new_width = max(factor, int((width * scale) // factor * factor))
    new_height = max(factor, int((height * scale) // factor * factor))
    if (new_width, new_height) == im.size:
        return im
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


def build_pipeline(device: str) -> StableDiffusionControlNetImg2ImgPipeline:
    controlnet = ControlNetModel.from_pretrained(
        "lllyasviel/sd-controlnet-canny",
        torch_dtype=torch.float32,
    )
    pipe = StableDiffusionControlNetImg2ImgPipeline.from_pretrained(
        "runwayml/stable-diffusion-v1-5",
        controlnet=controlnet,
        safety_checker=None,
        torch_dtype=torch.float32,
    )
    pipe = pipe.to(device)
    pipe.enable_attention_slicing()
    pipe.enable_vae_slicing()
    pipe.set_progress_bar_config(disable=True)
    return pipe


def build_condition(image: Image.Image) -> Image.Image:
    cv_img = pil_to_cv(image)
    edges = cv2.Canny(cv_img, 80, 160)
    edges_bgr = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
    return cv_to_pil(edges_bgr)


def run_suite(
    pipe: StableDiffusionControlNetImg2ImgPipeline,
    source: Image.Image,
    condition: Image.Image,
    seeds: Iterable[int],
    specs: Iterable[RunSpec],
    outdir: Path,
) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    for seed in seeds:
        generator = torch.Generator(device="cpu").manual_seed(seed)
        for spec in specs:
            result = pipe(
                prompt=(
                    "natural, muted historical colorization, accurate skin tones, preserved film grain, "
                    "realistic fabrics, no oversaturation, photo"
                ),
                negative_prompt=(
                    "blurry, extra limbs, deformed face, cartoon, painterly, plastic skin, makeup, artifacts, "
                    "distortion, overprocessed"
                ),
                image=source,
                control_image=condition,
                controlnet_conditioning_scale=spec.control_scale,
                strength=spec.strength,
                guidance_scale=spec.guidance_scale,
                num_inference_steps=spec.steps,
                generator=generator,
            )
            colored = result.images[0].convert("RGB")
            fused = lock_luminance(source, colored)
            fused.save(outdir / f"seed{seed}_{spec.tag}.png")


def main() -> None:
    args = parse_args()
    device = "mps" if torch.backends.mps.is_available() else "cpu"

    base = Image.open(args.image).convert("RGB")
    base = resize_to_multiple(base, max_side=args.max_side, factor=8)
    condition = build_condition(base)

    pipe = build_pipeline(device)

    specs = [
        RunSpec(tag="s020_g50_c10", strength=0.20, guidance_scale=5.0, control_scale=1.0, steps=20),
        RunSpec(tag="s024_g50_c12", strength=0.24, guidance_scale=5.0, control_scale=1.2, steps=22),
    ]

    run_suite(pipe, base, condition, args.seeds, specs, args.outdir)


if __name__ == "__main__":
    main()
