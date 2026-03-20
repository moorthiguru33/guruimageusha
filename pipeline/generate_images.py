"""
PNG Library - Image Generator
═══════════════════════════════════════════════════════
Model   : FLUX.2 [klein] 4B  (Apache 2.0 — FREE)
Pipeline: Flux2KleinPipeline
GPU     : Kaggle T4 (16 GB VRAM)
Output  : 1024x1024 PNG
Steps   : 10  |  CFG : 1.5
═══════════════════════════════════════════════════════

FIX LOG (v3 — REALISM FIX):
  ROOT CAUSE of cartoonish output found:
    → 9,746 prompts contain "3D rendered illustration",
      "vector style", "cartoon style", "digital art" etc.
    → These keywords directly tell FLUX to make cartoon output.

  FIXES APPLIED:
  1. sanitize_prompt() strips all cartoon/illustration keywords
  2. Replaces with photorealistic equivalents
  3. Adds strong realism anchors (RAW photo, Canon EOS R5, etc.)
  4. GRAPHIC categories (cliparts, frames_borders, offer_logos)
     are kept as-is — they are MEANT to be graphic/vector
  5. Flux2KleinPipeline (not FluxPipeline)
  6. steps=10, cfg=1.5 (klein distilled range)
  7. 1024x1024 (T4 safe, klein native resolution)
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
PROMPTS_FILE  = "prompts/all_prompts.json"
PROGRESS_FILE = "progress/progress.json"

GENERATION_CONFIG = {
    "num_inference_steps": 10,
    "guidance_scale":      1.5,
    "height":              1024,
    "width":               1024,
    "max_sequence_length": 512,
}

# ─────────────────────────────────────────────────────────────
# CATEGORIES
# ─────────────────────────────────────────────────────────────
# These are INTENTIONALLY graphic/vector — keep their prompts as-is
GRAPHIC_CATEGORIES = {"cliparts", "frames_borders", "offer_logos"}

# ─────────────────────────────────────────────────────────────
# PROMPT SANITIZER  ← ROOT CAUSE FIX
# ─────────────────────────────────────────────────────────────

CARTOON_PHRASES = [
    "3d rendered illustration",
    "3d rendered",
    "3d render",
    "rendered illustration",
    "detailed illustration",
    "illustration",
    "digital art",
    "digital painting",
    "cartoon style",
    "cartoon",
    "animated",
    "cgi render",
    "cgi",
    "vfx",
]

STYLE_REPLACEMENTS = {
    "vector style":   "studio product photography",
    "vector":         "sharp detail, product photography",
    "flat style":     "studio photography, clean background",
    "graphic design": "professional photography",
    "2d style":       "photography",
    "watercolor":     "photorealistic, fine art photography",
    "oil painting":   "photorealistic, fine art photography",
    "sketch":         "photorealistic, sharp detail",
}

REALISM_PREFIX = "RAW photo, DSLR photograph, "

REALISM_SUFFIX = (
    ", photorealistic, hyperrealistic, "
    "shot on Canon EOS R5 with 100mm macro lens, "
    "real life texture, sharp focus, "
    "professional studio product photography, "
    "natural lighting, 8k uhd"
)

CATEGORY_EXTRAS = {
    "food/indian":    ", food photography, steam rising, glistening surface, restaurant plating",
    "food/world":     ", food photography, steam rising, glistening surface, restaurant plating",
    "flowers":        ", macro photography, dewdrops on petals, vivid natural color, petal texture",
    "jewellery":      ", product photography, sparkling gems, reflective gold/silver, sharp facets",
    "vehicles/cars":  ", automotive photography, chrome reflections, showroom lighting",
    "vehicles/bikes": ", automotive photography, chrome reflections, showroom lighting",
    "animals":        ", wildlife photography, fur texture detail, catchlight in eyes",
    "birds_insects":  ", wildlife photography, feather detail, catchlight in eyes",
    "furniture":      ", interior design photography, wood grain visible, soft shadow",
    "nature/trees":   ", nature photography, bark texture, leaf veins, golden hour light",
    "sky_celestial":  ", astrophotography, volumetric clouds, atmospheric depth, star detail",
    "abstract":       ", fine art photography, crisp edges, vivid pigment",
    "effects/smoke":  ", volumetric smoke, translucent, ethereal, studio backlit",
    "pots_vessels":   ", product photography, ceramic glaze, studio soft box light",
    "tools":          ", product photography, metal texture, industrial studio light",
    "festivals":      ", cultural photography, vibrant celebration, editorial style",
}


def sanitize_prompt(prompt: str, category: str) -> str:
    """Strip cartoon keywords and add strong realism anchors."""
    p = prompt

    # Step 1: Replace style words with photographic equivalents
    for bad_phrase, replacement in STYLE_REPLACEMENTS.items():
        p = re.sub(re.escape(bad_phrase), replacement, p, flags=re.IGNORECASE)

    # Step 2: Remove cartoon/illustration/3D-render phrases (longest first)
    for phrase in sorted(CARTOON_PHRASES, key=len, reverse=True):
        p = re.sub(re.escape(phrase), "", p, flags=re.IGNORECASE)

    # Step 3: Clean up double commas and extra spaces
    p = re.sub(r",\s*,+", ",", p)
    p = re.sub(r"\s{2,}", " ", p)
    p = p.strip(" ,")

    # Step 4: Add realism prefix + category extras + suffix
    extra = CATEGORY_EXTRAS.get(category, "")
    return REALISM_PREFIX + p + extra + REALISM_SUFFIX


def build_graphic_prompt(prompt: str) -> str:
    """For graphic categories — keep style but boost quality."""
    return prompt + ", crisp sharp edges, high contrast, professional design, 8k resolution"


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
        from diffusers import Flux2KleinPipeline   # ✅ correct class for FLUX.2-klein
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
        if category in GRAPHIC_CATEGORIES:
            prompt = build_graphic_prompt(item["prompt"])
        else:
            prompt = sanitize_prompt(item["prompt"], category)

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
def run_generation(prompts_file=PROMPTS_FILE, output_dir=str(OUTPUT_DIR), max_images=None):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(prompts_file) as f:
        all_prompts = json.load(f)

    progress = ProgressManager(PROGRESS_FILE)
    progress.data["total"] = len(all_prompts)
    pending = progress.pending(all_prompts)
    if max_images: pending = pending[:max_images]
    if not pending: print("All done!"); return

    # Prompt preview
    print(f"\n{'='*60}")
    print("  PROMPT SANITIZER PREVIEW (first 2 examples)")
    print(f"{'='*60}")
    shown = 0
    for item in all_prompts[:100]:
        if item.get("category") in GRAPHIC_CATEGORIES: continue
        print(f"\n  ORIGINAL : {item['prompt'][:120]}")
        print(f"  CLEANED  : {sanitize_prompt(item['prompt'], item.get('category',''))[:120]}")
        shown += 1
        if shown >= 2: break

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
            mode    = "GRAPHIC" if cat in GRAPHIC_CATEGORIES else "REAL"
            print(f"  ✅ [{total:>4}/{len(pending)}] {item['filename']:<38} | {cat:<20} [{mode}] | ETA {eta:.0f}min")

        except torch.cuda.OutOfMemoryError:
            print(f"  ⚠️  OOM — retrying {item['filename']} at 768x768")
            torch.cuda.empty_cache(); gc.collect()
            try:
                cat = item.get("category", "")
                p = build_graphic_prompt(item["prompt"]) if cat in GRAPHIC_CATEGORIES else sanitize_prompt(item["prompt"], cat)
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
