"""
PNG Library - Image Generator V2
═══════════════════════════════════════════════════════
Model   : FLUX.2 [klein] 4B  (Apache 2.0 — FREE)
Pipeline: Flux2KleinPipeline
GPU     : Kaggle T4 (16 GB VRAM)
Output  : 1024x1024 PNG
Steps   : 10  |  CFG : 1.5
═══════════════════════════════════════════════════════

V2 CHANGES:
  prompt_engine_v2 already produces CLEAN photorealistic prompts.
  NO MORE double keyword stuffing.
  
  OLD PROBLEM (3 layers of keywords):
    Layer 1: prompt_engine → "Canon EOS R5, photorealistic, 8k..."
    Layer 2: sanitize_prompt() → ADDED "Canon EOS R5, photorealistic..." AGAIN
    Layer 3: main_pipeline make_prompt() → ADDED same keywords THIRD TIME
    Result: "Canon EOS R5" appeared 3 times → model confused

  V2 FIX:
    - prompt_engine_v2 prompts are already perfect — pass through
    - Only offer_logos use VECTOR_SUFFIX (already in prompt)
    - Category-specific ENHANCERS add only UNIQUE photography tips
    - No duplicate keywords ever
"""

import torch, json, os, gc, re
from pathlib import Path
from PIL import Image
import numpy as np
import time

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
MODEL_ID      = "black-forest-labs/FLUX.2-klein-4B"
OUTPUT_DIR    = Path("/kaggle/working/generated_images")
PROMPTS_DIR   = "prompts/splits"
PROGRESS_FILE = "progress/progress.json"

GENERATION_CONFIG = {
    "num_inference_steps": 10,
    "guidance_scale":      1.5,
    "height":              1024,
    "width":               1024,
    "max_sequence_length": 512,
}

# ─────────────────────────────────────────────────────────────
# CATEGORIES THAT USE VECTOR STYLE (not photorealistic)
# ─────────────────────────────────────────────────────────────
VECTOR_CATEGORIES = {"offer_logos"}

# ─────────────────────────────────────────────────────────────
# CATEGORY-SPECIFIC ENHANCERS
# ─────────────────────────────────────────────────────────────
# Add ONLY unique detail hints not already in BASE_SUFFIX.
# BASE_SUFFIX already has: Canon EOS R5, 8k, photorealistic,
# sharp focus, studio strobe, light grey bg, etc.
CATEGORY_ENHANCERS = {
    "food/indian":    ", appetizing food styling, steam visible, glistening oil surface",
    "food/world":     ", appetizing food styling, steam visible, glistening sauce",
    "fruits":         ", natural skin texture, juice droplets visible",
    "vegetables":     ", natural surface texture, fresh harvest quality",
    "flowers":        ", petal vein detail visible, natural color saturation",
    "jewellery":      ", gem facet reflections, metal surface mirror finish",
    "vehicles/cars":  ", automotive paint reflection, chrome trim detail",
    "vehicles/bikes": ", engine component detail, chrome pipe reflection",
    "animals":        ", individual fur strand detail, catchlight in eyes",
    "birds_insects":  ", feather barb detail visible, catchlight in eyes",
    "furniture":      ", wood grain pattern visible, fabric weave texture",
    "nature/trees":   ", bark crack texture, leaf vein network visible",
    "sky_celestial":  ", atmospheric depth, volumetric light rays",
    "effects":        ", volumetric density, translucent edges, backlit",
    "pots_vessels":   ", surface patina detail, material authenticity",
    "tools":          ", metal grain texture, handle material detail",
    "festivals":      ", warm festive glow, cultural authenticity",
    "electronics":    ", screen reflection, anodized surface finish",
    "spices":         ", granular texture visible, aromatic powder detail",
    "beverages":      ", condensation droplets, liquid transparency",
    "shoes":          ", leather grain texture, stitching detail visible",
    "bags":           ", leather surface quality, hardware metal finish",
    "cosmetics":      ", product surface sheen, packaging detail",
    "sports":         ", material wear texture, grip pattern detail",
    "music":          ", wood lacquer finish, string detail visible",
    "pooja_items":    ", brass patina detail, devotional craftsmanship",
    "clothing":       ", fabric weave texture, thread count visible",
    "medical":        ", clinical precision detail, sterile surface",
    "stationery":     ", material surface texture, precision crafting",
}


def enhance_prompt(prompt: str, category: str) -> str:
    """
    Add category-specific photography enhancers.
    V2 prompts are already clean — only add unique detail hints.
    """
    if category in VECTOR_CATEGORIES:
        return prompt

    extra = ""
    for cat_key, enhancer in CATEGORY_ENHANCERS.items():
        if category.startswith(cat_key):
            extra = enhancer
            break

    return prompt + extra


# ─────────────────────────────────────────────────────────────
# QUALITY CHECK
# ─────────────────────────────────────────────────────────────
def is_quality_image(img: Image.Image) -> bool:
    arr = np.array(img.convert("RGB")).astype(np.float32)
    if arr.std() < 8:
        return False
    white_pixels = ((arr > 245).all(axis=-1)).sum()
    if white_pixels / (arr.shape[0] * arr.shape[1]) > 0.90:
        return False
    if arr.reshape(-1, 3).std(axis=0).max() < 10:
        return False
    return True


# ─────────────────────────────────────────────────────────────
# FLUX.2 KLEIN GENERATOR
# ─────────────────────────────────────────────────────────────
class Flux2KleinGenerator:

    def __init__(self):
        self.pipe   = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Device : {self.device}")
        if torch.cuda.is_available():
            p = torch.cuda.get_device_properties(0)
            print(f"GPU    : {p.name}  |  VRAM: {p.total_memory/1e9:.0f} GB")

    def load_model(self):
        from diffusers import Flux2KleinPipeline
        print(f"\nLoading {MODEL_ID} ...")
        print("(First run downloads ~8 GB — ~5 min)\n")
        self.pipe = Flux2KleinPipeline.from_pretrained(MODEL_ID, torch_dtype=torch.bfloat16)
        self.pipe.enable_model_cpu_offload()
        self.pipe.vae.enable_tiling()
        print(f"Model loaded!  VRAM: {torch.cuda.memory_allocated()/1e9:.1f} GB\n")
        return self

    def _run(self, prompt, seed, cfg=None, h=None, w=None):
        gen = torch.Generator(device="cpu").manual_seed(seed)
        return self.pipe(
            prompt              = prompt,
            generator           = gen,
            num_inference_steps = GENERATION_CONFIG["num_inference_steps"],
            guidance_scale      = cfg or GENERATION_CONFIG["guidance_scale"],
            height              = h   or GENERATION_CONFIG["height"],
            width               = w   or GENERATION_CONFIG["width"],
            max_sequence_length = GENERATION_CONFIG["max_sequence_length"],
        ).images[0]

    def generate(self, item: dict) -> Image.Image:
        category = item.get("category", "")
        prompt = enhance_prompt(item["prompt"], category)

        img = self._run(prompt, item["seed"])
        if is_quality_image(img):
            return img

        print(f"    Retry (new seed) : {item['filename']}")
        img = self._run(prompt, item["seed"] + 7777)
        if is_quality_image(img):
            return img

        print(f"    Retry (cfg=1.8)  : {item['filename']}")
        return self._run(prompt, item["seed"], cfg=1.8)

    def unload(self):
        del self.pipe; self.pipe = None
        gc.collect(); torch.cuda.empty_cache()
        print("Model unloaded, VRAM freed.")


# ─────────────────────────────────────────────────────────────
# PROGRESS MANAGER
# ─────────────────────────────────────────────────────────────
class ProgressManager:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()

    def _load(self):
        if self.path.exists():
            with open(self.path) as f: return json.load(f)
        return {"completed": [], "failed": [], "total": 0, "start_time": time.time()}

    def save(self):
        with open(self.path, "w") as f: json.dump(self.data, f)

    def mark_done(self, idx): self.data["completed"].append(idx); self.save()
    def mark_fail(self, idx): self.data["failed"].append(idx); self.save()

    def pending(self, all_prompts):
        done = set(self.data["completed"]) | set(self.data["failed"])
        p = [x for x in all_prompts if x["index"] not in done]
        print(f"Progress : {len(self.data['completed'])}/{len(all_prompts)} done | {len(p)} remaining")
        return p


# ─────────────────────────────────────────────────────────────
# SAVE
# ─────────────────────────────────────────────────────────────
def save_image(img, item, base_dir):
    folder = Path(base_dir) / item["category"] / item.get("subcategory", "general")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / item["filename"]
    img.save(str(path), "PNG", optimize=True)
    return str(path)


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def run_generation(prompts_dir=PROMPTS_DIR, output_dir=str(OUTPUT_DIR), max_images=None):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Load prompts from category-split files
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from prompts.prompt_engine import load_all_prompts
    all_prompts = load_all_prompts(prompts_dir)

    progress = ProgressManager(PROGRESS_FILE)
    progress.data["total"] = len(all_prompts)
    pending = progress.pending(all_prompts)
    if max_images: pending = pending[:max_images]
    if not pending: print("All done!"); return

    # Prompt preview
    print(f"\n{'='*60}")
    print("  PROMPT PREVIEW (first 3 examples)")
    print(f"{'='*60}")
    shown = 0
    for item in all_prompts[:200]:
        cat = item.get("category", "")
        final = enhance_prompt(item["prompt"], cat)
        mode = "VECTOR" if cat in VECTOR_CATEGORIES else "PHOTO"
        print(f"\n  [{mode}] {cat}/{item.get('subcategory','')}")
        print(f"  FINAL: {final[:150]}...")
        shown += 1
        if shown >= 3: break

    print(f"\n{'='*60}")
    print(f"  Steps={GENERATION_CONFIG['num_inference_steps']}  CFG={GENERATION_CONFIG['guidance_scale']}  Size=1024x1024")
    print(f"  Total to generate: {len(pending)}")
    print(f"{'='*60}\n")

    gen = Flux2KleinGenerator().load_model()
    total = 0
    t0 = time.time()

    for item in pending:
        try:
            img = gen.generate(item)
            save_image(img, item, output_dir)
            progress.mark_done(item["index"])
            total += 1
            elapsed = time.time() - t0
            rate    = total / elapsed
            eta     = (len(pending) - total) / rate / 60 if rate > 0 else 0
            cat     = item.get("category", "")
            mode    = "VEC" if cat in VECTOR_CATEGORIES else "PHO"
            print(f"  ✅ [{total:>4}/{len(pending)}] {item['filename']:<38} | {cat:<20} [{mode}] | ETA {eta:.0f}min")

        except torch.cuda.OutOfMemoryError:
            print(f"  ⚠️  OOM — retrying {item['filename']} at 768x768")
            torch.cuda.empty_cache(); gc.collect()
            try:
                cat = item.get("category", "")
                p = enhance_prompt(item["prompt"], cat)
                img = gen._run(p, item["seed"], h=768, w=768)
                save_image(img, item, output_dir)
                progress.mark_done(item["index"]); total += 1
            except Exception as e2:
                print(f"  ❌ FAIL: {e2}"); progress.mark_fail(item["index"])

        except Exception as e:
            print(f"  ❌ FAIL {item['filename']}: {e}"); progress.mark_fail(item["index"])

        if total % 50 == 0 and total > 0:
            gc.collect(); torch.cuda.empty_cache()
            print(f"  [VRAM cleanup] {torch.cuda.memory_allocated()/1e9:.1f} GB")

    t = time.time() - t0
    print(f"\nDone! {total} images in {t/3600:.1f}h | Failed: {len(progress.data['failed'])}")
    gen.unload()


if __name__ == "__main__":
    run_generation()
