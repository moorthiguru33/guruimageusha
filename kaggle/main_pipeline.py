"""
PNG Library - Kaggle Pipeline V2
=============================================================
Model   : FLUX.2 [klein] 4B
HF ID   : black-forest-labs/FLUX.2-klein-4B
License : Apache 2.0 - FREE for commercial use
VRAM    : ~8GB on T4 16GB - confirmed fits
Released: January 15, 2026 by Black Forest Labs
Steps   : 4 steps (distilled - fast + good quality)
Batch   : 800 images/run ~ 4hrs (safe within 30hr/week)
=============================================================

V2 CHANGES:
  - Removed duplicate make_prompt() — V2 prompts are already complete
  - Only adds category-specific texture hints (no duplicate keywords)
  - Updated for 43,082 total prompts (was 46,502)
  - offer_logos use vector style, everything else photorealistic
"""

import os, sys, json, time, gc, subprocess
from pathlib import Path

# ── Install dependencies ──────────────────────────────────────
print("=" * 55)
print("Installing dependencies...")
pkgs = [
    "git+https://github.com/huggingface/diffusers.git",
    "transformers>=4.47.0",
    "accelerate>=0.28.0",
    "sentencepiece",
    "huggingface_hub",
    "Pillow",
    "numpy",
    "rembg[gpu]",
    "requests",
]
for pkg in pkgs:
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", pkg],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        print(f"  WARN {pkg}: {r.stderr[:200]}")
    else:
        print(f"  OK   {pkg.split('/')[-1] if 'git+' in pkg else pkg}")
print("Done!\n")

import torch
import numpy as np
from PIL import Image
import requests as req

# ── Paths ─────────────────────────────────────────────────────
WORKING_DIR     = Path("/kaggle/working")
GENERATED_DIR   = WORKING_DIR / "generated_images"
TRANSPARENT_DIR = WORKING_DIR / "transparent_pngs"
PROMPTS_DIR     = WORKING_DIR / "prompts_splits"
PROGRESS_DIR    = WORKING_DIR / "progress"
PROJECT_DIR     = WORKING_DIR / "project"
for d in [GENERATED_DIR, TRANSPARENT_DIR, PROGRESS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Credentials ───────────────────────────────────────────────
GOOGLE_CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN", "")
GITHUB_REPO          = os.environ.get("GITHUB_REPO", "")
START_INDEX          = int(os.environ.get("START_INDEX", "0"))
END_INDEX            = int(os.environ.get("END_INDEX", "800"))

print("=" * 55)
print("  PNG LIBRARY V2 — FLUX.2 [klein] 4B")
print("  Apache 2.0 | ~8GB VRAM | T4 Confirmed")
print("  43,082 Ultra-Realistic Prompts")
print("=" * 55)
print(f"  Batch  : {START_INDEX} -> {END_INDEX}  ({END_INDEX - START_INDEX} images)")
if torch.cuda.is_available():
    p = torch.cuda.get_device_properties(0)
    print(f"  GPU    : {p.name}  |  VRAM: {p.total_mem/1e9:.0f} GB" if hasattr(p, 'total_mem') else f"  GPU    : {p.name}  |  VRAM: {p.total_memory/1e9:.0f} GB")
print("=" * 55 + "\n")

# ── Clone repo ────────────────────────────────────────────────
if GITHUB_REPO and not PROJECT_DIR.exists():
    os.system(f"git clone https://github.com/{GITHUB_REPO} {PROJECT_DIR}")
    sys.path.insert(0, str(PROJECT_DIR))
    print(f"Cloned: {GITHUB_REPO}")

# ── Load prompts ──────────────────────────────────────────────
def load_or_generate_prompts():
    # Try loading from split files in repo (fast path)
    repo_splits = PROJECT_DIR / "prompts" / "splits"
    local_splits = PROMPTS_DIR

    if repo_splits.exists() and any(repo_splits.glob("*.json")):
        sys.path.insert(0, str(PROJECT_DIR))
        from prompts.prompt_engine import load_all_prompts
        prompts = load_all_prompts(str(repo_splits))
        print(f"Loaded {len(prompts)} prompts from repo splits")
        return prompts

    if local_splits.exists() and any(local_splits.glob("*.json")):
        sys.path.insert(0, str(PROJECT_DIR))
        from prompts.prompt_engine import load_all_prompts
        prompts = load_all_prompts(str(local_splits))
        print(f"Loaded {len(prompts)} prompts from local splits")
        return prompts

    # Fallback: generate fresh and save as splits
    if PROJECT_DIR.exists():
        sys.path.insert(0, str(PROJECT_DIR))
    from prompts.prompt_engine import PromptEngine
    engine = PromptEngine()
    local_splits.mkdir(parents=True, exist_ok=True)
    engine.save_prompts(str(local_splits))
    from prompts.prompt_engine import load_all_prompts
    prompts = load_all_prompts(str(local_splits))
    print(f"Generated {len(prompts)} prompts")
    return prompts

all_prompts   = load_or_generate_prompts()
batch_prompts = all_prompts[START_INDEX:END_INDEX]
print(f"Batch size : {len(batch_prompts)}")

# ── Resume ────────────────────────────────────────────────────
pf = PROGRESS_DIR / f"progress_{START_INDEX}_{END_INDEX}.json"
if pf.exists():
    with open(pf) as f:
        progress = json.load(f)
    print(f"Resuming   : {len(progress['completed'])} already done")
else:
    progress = {"completed": [], "failed": [], "start_time": time.time()}

done_set = set(progress["completed"])
pending  = [p for p in batch_prompts if p["index"] not in done_set]
print(f"Pending    : {len(pending)} images\n")

# ─────────────────────────────────────────────────────────────
# CATEGORY ENHANCERS (unique detail hints only)
# ─────────────────────────────────────────────────────────────
# V2 prompts already have: Canon EOS R5, 8k, photorealistic,
# sharp focus, studio strobe, light grey bg.
# We ONLY add category-specific texture hints here.
VECTOR_CATEGORIES = {"offer_logos"}

CATEGORY_ENHANCERS = {
    "food/":         ", appetizing food styling, steam visible, glistening surface",
    "fruits":        ", natural skin texture, juice droplets",
    "vegetables":    ", natural surface texture, fresh harvest quality",
    "flowers":       ", petal vein detail, natural color saturation",
    "jewellery":     ", gem facet reflections, metal mirror finish",
    "vehicles/":     ", automotive paint reflection, chrome detail",
    "animals":       ", fur strand detail, catchlight in eyes",
    "birds_insects": ", feather barb detail, catchlight in eyes",
    "furniture":     ", wood grain visible, fabric weave texture",
    "nature/":       ", bark texture, leaf vein detail",
    "effects":       ", volumetric density, translucent edges",
    "electronics":   ", screen reflection, anodized finish",
    "spices":        ", granular texture, aromatic powder detail",
    "beverages":     ", condensation droplets, liquid transparency",
    "shoes":         ", leather grain, stitching detail",
    "bags":          ", leather surface, hardware metal finish",
    "cosmetics":     ", product sheen, packaging detail",
    "sports":        ", material texture, grip pattern",
    "music":         ", wood lacquer, string detail",
    "pooja_items":   ", brass patina, devotional craftsmanship",
    "clothing":      ", fabric weave, thread detail",
    "medical":       ", clinical precision, sterile surface",
    "stationery":    ", material texture, precision crafting",
}


def enhance_prompt(raw_prompt, category):
    """Add only unique category hints. No duplicate keywords."""
    if category in VECTOR_CATEGORIES:
        return raw_prompt

    extra = ""
    for cat_key, enhancer in CATEGORY_ENHANCERS.items():
        if category.startswith(cat_key):
            extra = enhancer
            break

    return raw_prompt + extra


# ============================================================
# STEP 1: FLUX.2 [klein] 4B — Image Generation
# ============================================================
if pending:
    print("=" * 55)
    print("STEP 1: FLUX.2 [klein] 4B Generation")
    print("=" * 55)
    print("Loading black-forest-labs/FLUX.2-klein-4B ...")
    print("(First run: downloads ~8GB — ~5 min)\n")

    from diffusers import Flux2KleinPipeline
    pipe = Flux2KleinPipeline.from_pretrained(
        "black-forest-labs/FLUX.2-klein-4B",
        torch_dtype=torch.bfloat16,
    )
    print("Loaded with Flux2KleinPipeline")

    pipe.enable_model_cpu_offload()
    print(f"Model loaded! VRAM: {torch.cuda.memory_allocated()/1e9:.1f} GB\n")

    def generate_image(item):
        prompt = enhance_prompt(item["prompt"], item.get("category", ""))
        generator = torch.Generator(device="cpu").manual_seed(item["seed"])
        return pipe(
            prompt=prompt,
            num_inference_steps=4,
            guidance_scale=1.0,
            height=1024,
            width=1024,
            generator=generator,
        ).images[0]

    def save_generated(img, item):
        folder = GENERATED_DIR / item["category"] / item.get("subcategory", "general")
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / item["filename"]
        img.save(str(path), "PNG")
        return str(path)

    def is_good(img):
        arr = np.array(img)
        return arr.std() > 5 and (arr < 250).sum() > 1000

    gen_count = 0
    t0 = time.time()
    print(f"Generating {len(pending)} images...\n")

    for item in pending:
        try:
            img = generate_image(item)

            if not is_good(img):
                print(f"  Retry {item['filename']}...")
                retry = dict(item); retry["seed"] += 42
                img = generate_image(retry)

            save_generated(img, item)
            progress["completed"].append(item["index"])
            gen_count += 1

            elapsed = time.time() - t0
            rate    = gen_count / elapsed
            eta     = (len(pending) - gen_count) / rate / 60 if rate > 0 else 0
            cat     = item.get("category", "")
            mode    = "VEC" if cat in VECTOR_CATEGORIES else "PHO"
            print(f"  ✅ [{gen_count}/{len(pending)}] {item['filename']}"
                  f" | {cat} [{mode}] | ETA {eta:.0f}min")

            if gen_count % 100 == 0:
                with open(pf, "w") as f: json.dump(progress, f)
                gc.collect(); torch.cuda.empty_cache()
                print(f"  [saved] VRAM: {torch.cuda.memory_allocated()/1e9:.1f}GB")

        except torch.cuda.OutOfMemoryError:
            print(f"  OOM — retrying {item['filename']} at 768x768")
            torch.cuda.empty_cache(); gc.collect()
            try:
                prompt = enhance_prompt(item["prompt"], item.get("category", ""))
                gen = torch.Generator(device="cpu").manual_seed(item["seed"])
                img = pipe(
                    prompt=prompt,
                    num_inference_steps=4,
                    guidance_scale=1.0,
                    height=768, width=768,
                    generator=gen,
                ).images[0]
                save_generated(img, item)
                progress["completed"].append(item["index"])
                gen_count += 1
            except Exception as e2:
                print(f"  FAIL: {e2}")
                progress["failed"].append(item["index"])

        except Exception as e:
            print(f"  FAIL {item['filename']}: {e}")
            progress["failed"].append(item["index"])

    with open(pf, "w") as f: json.dump(progress, f)
    print(f"\nGeneration : {gen_count} images in {(time.time()-t0)/60:.0f} min")
    print(f"Failed     : {len(progress['failed'])}")
    del pipe; gc.collect(); torch.cuda.empty_cache()
    print("Model freed\n")

# ============================================================
# STEP 2: Background Removal (rembg - U2Net)
# ============================================================
print("=" * 55)
print("STEP 2: Background Removal (rembg)")
print("=" * 55)

from rembg import remove as rembg_remove
print("rembg loaded successfully")

gen_files = list(GENERATED_DIR.rglob("*.png"))
print(f"Processing {len(gen_files)} images...\n")
bg_ok = 0; bg_fail = 0; t1 = time.time()

for img_file in gen_files:
    rel = img_file.relative_to(GENERATED_DIR)
    out = TRANSPARENT_DIR / rel
    if out.exists(): continue
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        img = Image.open(str(img_file)).convert("RGB")
        result = rembg_remove(img)
        result.save(str(out), "PNG", optimize=True)
        bg_ok += 1
        if bg_ok % 50 == 0:
            print(f"  BG done: {bg_ok} | {bg_ok/(time.time()-t1):.2f}/s")
            gc.collect(); torch.cuda.empty_cache()
    except Exception as e:
        print(f"  BG FAIL {img_file.name}: {e}"); bg_fail += 1

print(f"\nBG removal : {bg_ok} OK, {bg_fail} failed in {(time.time()-t1)/60:.0f} min")
gc.collect(); torch.cuda.empty_cache()
print("BG done\n")

# ============================================================
# STEP 3: Google Drive Upload
# ============================================================
print("=" * 55)
print("STEP 3: Upload to Google Drive")
print("=" * 55)

def get_token():
    r = req.post("https://oauth2.googleapis.com/token", data={
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": GOOGLE_REFRESH_TOKEN,
        "grant_type": "refresh_token"
    })
    if r.status_code != 200:
        raise Exception(f"Token failed: {r.text}")
    return r.json()["access_token"]

def find_or_create(token, name, parent=None):
    h = {"Authorization": f"Bearer {token}"}
    q = (f"name='{name}' and mimeType='application/vnd.google-apps.folder'"
         f" and trashed=false")
    if parent: q += f" and '{parent}' in parents"
    r = req.get("https://www.googleapis.com/drive/v3/files",
                headers=h, params={"q": q, "fields": "files(id)"})
    files = r.json().get("files", [])
    if files: return files[0]["id"]
    meta = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent: meta["parents"] = [parent]
    r2 = req.post("https://www.googleapis.com/drive/v3/files",
                  headers={**h, "Content-Type": "application/json"}, json=meta)
    print(f"  Folder created: {name}")
    return r2.json()["id"]

def upload_file(token, path, name, folder_id):
    import json as _j
    h = {"Authorization": f"Bearer {token}"}
    with open(path, "rb") as f: data = f.read()
    meta = _j.dumps({"name": name, "parents": [folder_id]})
    r = req.post(
        "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
        headers=h,
        files=[("metadata", ("m", meta, "application/json")),
               ("file",     (name, data, "image/png"))]
    )
    return r.status_code in [200, 201]

if all([GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN]):
    try:
        token   = get_token()
        f_cache = {}
        up_pf   = PROGRESS_DIR / f"upload_{START_INDEX}.json"
        up_prog = json.load(open(up_pf)) if up_pf.exists() else {"uploaded": []}
        uploaded = set(up_prog["uploaded"])

        f_cache[""] = find_or_create(token, "png_library_images")
        print(f"Root folder ready: png_library_images\n")

        png_files = list(TRANSPARENT_DIR.rglob("*.png"))
        up_ok = 0; t2 = time.time()
        print(f"Uploading {len(png_files)} PNGs...")

        for png in png_files:
            rel      = png.relative_to(TRANSPARENT_DIR)
            file_key = str(rel)
            if file_key in uploaded: continue

            cat    = str(rel.parent)
            parent = f_cache[""]
            for part in cat.split("/"):
                if not part: continue
                key = f"{parent}/{part}"
                if key not in f_cache:
                    f_cache[key] = find_or_create(token, part, parent)
                parent = f_cache[key]
            f_cache[cat] = parent

            if up_ok > 0 and up_ok % 500 == 0:
                token = get_token()
                print(f"  Token refreshed at {up_ok} uploads")

            if upload_file(token, str(png), rel.name, f_cache[cat]):
                up_prog["uploaded"].append(file_key)
                uploaded.add(file_key)
                up_ok += 1
                if up_ok % 50 == 0:
                    with open(up_pf, "w") as f: json.dump(up_prog, f)
                    print(f"  Uploaded: {up_ok} | {up_ok/(time.time()-t2):.2f}/s")
            else:
                print(f"  Upload FAIL: {file_key}")
            time.sleep(0.05)

        with open(up_pf, "w") as f: json.dump(up_prog, f)
        print(f"\nUpload done: {up_ok} files in {(time.time()-t2)/60:.0f} min")
    except Exception as e:
        print(f"Drive error: {e}")
else:
    print("WARNING: Google credentials missing!")

# ============================================================
# FINAL REPORT
# ============================================================
total_gen = len(list(GENERATED_DIR.rglob("*.png")))
total_trn = len(list(TRANSPARENT_DIR.rglob("*.png")))
total_min = (time.time() - progress.get("start_time", time.time())) / 60
print(f"""
{'='*55}
  BATCH COMPLETE!
  Model      : FLUX.2 [klein] 4B (Apache 2.0)
  Prompts    : V2 Ultra-Realistic (43,082 total)
  Steps      : 4  |  CFG: 1.0  |  1024x1024
  BG Removal : rembg (U2Net)
  Generated  : {total_gen} images
  Transparent: {total_trn} PNGs
  Batch      : {START_INDEX} - {END_INDEX}
  Time       : {total_min:.0f} minutes
  Drive      : png_library_images/
{'='*55}
""")
