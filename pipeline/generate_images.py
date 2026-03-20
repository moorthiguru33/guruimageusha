"""
PNG Library - Image Generator
Model : FLUX.2 [klein] 4B  (Apache 2.0 - 100% FREE)
GPU   : Kaggle T4 (16 GB VRAM)
Output: 2048x2048 PNG  (FLUX.2 native - no upscaler needed)
BG    : BRIA-RMBG-2.0
"""

import torch, json, os, gc
from pathlib import Path
from diffusers import FluxPipeline
from PIL import Image
import time

MODEL_ID      = "black-forest-labs/FLUX.2-klein-4B"
OUTPUT_DIR    = Path("/kaggle/working/generated_images")
PROMPTS_FILE  = "prompts/all_prompts.json"
PROGRESS_FILE = "progress/progress.json"

GENERATION_CONFIG = {
    "num_inference_steps": 8,
    "guidance_scale": 3.5,
    "height": 2048,
    "width":  2048,
    "max_sequence_length": 512,
}

def is_quality_image(img):
    import numpy as np
    arr = np.array(img)
    if arr.std() < 5: return False
    if (arr < 250).sum() < 1000: return False
    return True

class Flux2Generator:
    def __init__(self):
        self.pipe   = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Device: {self.device}")

    def load_model(self):
        print(f"Loading FLUX.2 [klein] 4B...")
        self.pipe = FluxPipeline.from_pretrained(MODEL_ID, torch_dtype=torch.bfloat16)
        self.pipe.enable_model_cpu_offload()
        self.pipe.enable_attention_slicing(slice_size="auto")
        self.pipe.vae.enable_tiling()
        print(f"Model loaded! VRAM: {torch.cuda.memory_allocated()/1e9:.1f} GB")
        return self

    def generate(self, prompt, seed):
        gen = torch.Generator(device="cpu").manual_seed(seed)
        return self.pipe(prompt=prompt, generator=gen, **GENERATION_CONFIG).images[0]

    def unload(self):
        del self.pipe; self.pipe = None
        gc.collect(); torch.cuda.empty_cache()
        print("Model unloaded")

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
    def mark_fail(self, idx): self.data["failed"].append(idx);    self.save()

    def pending(self, all_prompts):
        done = set(self.data["completed"]) | set(self.data["failed"])
        p = [x for x in all_prompts if x["index"] not in done]
        print(f"Progress: {len(self.data['completed'])}/{len(all_prompts)} done, {len(p)} remaining")
        return p

def save_image(img, item, base_dir):
    folder = Path(base_dir) / item["category"] / item.get("subcategory", "general")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / item["filename"]
    img.save(str(path), "PNG", optimize=True)
    return str(path)

def run_generation(prompts_file=PROMPTS_FILE, output_dir=str(OUTPUT_DIR), max_images=None):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(prompts_file) as f:
        all_prompts = json.load(f)

    progress = ProgressManager(PROGRESS_FILE)
    progress.data["total"] = len(all_prompts)
    pending  = progress.pending(all_prompts)
    if max_images: pending = pending[:max_images]
    if not pending: print("All done!"); return

    gen = Flux2Generator().load_model()
    total = 0
    t0    = time.time()

    for item in pending:
        try:
            img = gen.generate(item["prompt"], item["seed"])
            if not is_quality_image(img):
                img = gen.generate(item["prompt"], item["seed"] + 7777)
            save_image(img, item, output_dir)
            progress.mark_done(item["index"])
            total += 1
            elapsed = time.time() - t0
            rate    = total / elapsed
            eta     = (len(pending) - total) / rate / 60 if rate > 0 else 0
            print(f"  OK [{total}/{len(pending)}] {item['filename']} "
                  f"| 2048x2048 | {rate:.2f}/s | ETA {eta:.0f}min")

        except torch.cuda.OutOfMemoryError:
            print(f"  OOM -- retrying at 1024x1024")
            torch.cuda.empty_cache(); gc.collect()
            try:
                GENERATION_CONFIG["height"] = 1024; GENERATION_CONFIG["width"] = 1024
                img = gen.generate(item["prompt"], item["seed"])
                GENERATION_CONFIG["height"] = 2048; GENERATION_CONFIG["width"] = 2048
                save_image(img, item, output_dir)
                progress.mark_done(item["index"]); total += 1
            except Exception as e2:
                print(f"  FAIL: {e2}"); progress.mark_fail(item["index"])
        except Exception as e:
            print(f"  FAIL {item['filename']}: {e}"); progress.mark_fail(item["index"])

        if total % 50 == 0:
            gc.collect(); torch.cuda.empty_cache()

    print(f"\nDone! {total} images in {(time.time()-t0)/3600:.1f} hours")
    gen.unload()

if __name__ == "__main__":
    run_generation()
