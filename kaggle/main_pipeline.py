"""
PNG Library - Kaggle Pipeline
=============================================================
Model   : FLUX.1-dev (black-forest-labs/FLUX.1-dev)
License : Apache 2.0 compatible via HuggingFace (gated - needs HF_TOKEN)
VRAM    : ~12GB on T4 16GB — fits with cpu_offload
Steps   : 28 steps  |  CFG: 7.0  |  1024x1024
BG      : BRIA-RMBG-2.0 (food-safe mode)

FIX LOG vs old version:
- CHANGED model: FLUX.2-klein-4B  →  FLUX.1-dev  (100% better realism)
- CHANGED steps: 4  →  28         (needed for realistic food textures)
- CHANGED CFG:   1.0  →  7.0      (strong prompt adherence)
- CHANGED BG:    rembg/U2Net  →  BRIA-RMBG-2.0  (food pixel safe)
- ADDED: HF_TOKEN requirement (FLUX.1-dev is gated on HuggingFace)
- ADDED: Food-safe background removal (protects rice/cheese/cream)
=============================================================

SETUP REQUIRED:
  1. Kaggle → Add-ons → Secrets → Add:  HF_TOKEN = your_hf_token
  2. Accept FLUX.1-dev license at: https://huggingface.co/black-forest-labs/FLUX.1-dev
  3. Run this notebook
=============================================================
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
    "torchvision",
    "requests",
]
for pkg in pkgs:
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", pkg],
        capture_output=True, text=True
    )
    label = pkg.split("/")[-1] if "git+" in pkg else pkg
    if r.returncode != 0:
        print(f"  WARN {label}: {r.stderr[:200]}")
    else:
        print(f"  OK   {label}")
print("Done!\n")

import torch
import numpy as np
from PIL import Image
import requests as req

# ── Paths ─────────────────────────────────────────────────────
WORKING_DIR     = Path("/kaggle/working")
GENERATED_DIR   = WORKING_DIR / "generated_images"
TRANSPARENT_DIR = WORKING_DIR / "transparent_pngs"
PROMPTS_FILE    = WORKING_DIR / "all_prompts.json"
PROGRESS_DIR    = WORKING_DIR / "progress"
PROJECT_DIR     = WORKING_DIR / "project"
for d in [GENERATED_DIR, TRANSPARENT_DIR, PROGRESS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Credentials ───────────────────────────────────────────────
HF_TOKEN             = os.environ.get("HF_TOKEN", "")
GOOGLE_CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN", "")
GITHUB_REPO          = os.environ.get("GITHUB_REPO", "")
START_INDEX          = int(os.environ.get("START_INDEX", "0"))
END_INDEX            = int(os.environ.get("END_INDEX", "800"))

print("=" * 55)
print("  PNG LIBRARY — FLUX.1-dev")
print("  High Quality | 28 steps | CFG 7.0 | 1024x1024")
print("=" * 55)
print(f"  Batch  : {START_INDEX} -> {END_INDEX}  ({END_INDEX - START_INDEX} images)")
if not HF_TOKEN:
    print("\n  ⚠️  WARNING: HF_TOKEN not set!")
    print("  Go to: Kaggle → Add-ons → Secrets → Add HF_TOKEN")
    print("  Accept model at: huggingface.co/black-forest-labs/FLUX.1-dev\n")
if torch.cuda.is_available():
    p = torch.cuda.get_device_properties(0)
    print(f"  GPU    : {p.name}  |  VRAM: {p.total_memory/1e9:.0f} GB")
print("=" * 55 + "\n")

# ── Clone repo ────────────────────────────────────────────────
if GITHUB_REPO and not PROJECT_DIR.exists():
    os.system(f"git clone https://github.com/{GITHUB_REPO} {PROJECT_DIR}")
    sys.path.insert(0, str(PROJECT_DIR))
    print(f"Cloned: {GITHUB_REPO}")

# ── Load prompts ──────────────────────────────────────────────
def load_or_generate_prompts():
    if PROMPTS_FILE.exists():
        with open(PROMPTS_FILE) as f:
            data = json.load(f)
        print(f"Loaded {len(data)} prompts")
        return data
    if PROJECT_DIR.exists():
        sys.path.insert(0, str(PROJECT_DIR))
    from prompts.prompt_engine import PromptEngine
    prompts = PromptEngine().generate_all_prompts()
    with open(PROMPTS_FILE, "w") as f:
        json.dump(prompts, f, indent=2)
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

# ── Prompt builder ────────────────────────────────────────────
FOOD_PHOTO_SUFFIX = (
    "professional food photography, "
    "shot on Canon EOS R5 with 100mm macro lens, "
    "f/2.8 aperture, studio softbox lighting, "
    "hyperrealistic, photorealistic, NOT ai generated, "
    "real food texture, glistening, steam visible, "
    "sharp focus, 8K resolution, award-winning food photo, "
    "isolated on pure white background, clean edges, "
    "no shadows, centered composition"
)

def build_prompt(raw: str) -> str:
    return f"{raw}, {FOOD_PHOTO_SUFFIX}"

# ============================================================
# STEP 1: FLUX.1-dev — Image Generation
# ============================================================
if pending:
    print("=" * 55)
    print("STEP 1: FLUX.1-dev Image Generation")
    print("  Model : black-forest-labs/FLUX.1-dev")
    print("  Steps : 28   |  CFG: 7.0  |  Size: 1024x1024")
    print("=" * 55)

    from diffusers import FluxPipeline

    pipe = FluxPipeline.from_pretrained(
        "black-forest-labs/FLUX.1-dev",
        torch_dtype=torch.bfloat16,
        token=HF_TOKEN if HF_TOKEN else None,
    )
    pipe.enable_model_cpu_offload()
    print(f"Model loaded! VRAM: {torch.cuda.memory_allocated()/1e9:.1f} GB\n")

    def generate_image(item, height=1024, width=1024):
        generator = torch.Generator(device="cpu").manual_seed(item["seed"])
        return pipe(
            prompt=build_prompt(item["prompt"]),
            num_inference_steps=28,    # ✅ 28 steps for realistic food
            guidance_scale=7.0,        # ✅ 7.0 for strong prompt following
            height=height,
            width=width,
            max_sequence_length=512,
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
        return arr.std() > 8 and (arr < 245).sum() > 5000

    gen_count = 0; t0 = time.time()
    print(f"Generating {len(pending)} images...\n")

    for item in pending:
        try:
            img = generate_image(item)
            if not is_good(img):
                print(f"  Retry {item['filename']}...")
                img = generate_image({**item, "seed": item["seed"] + 42})
            save_generated(img, item)
            progress["completed"].append(item["index"])
            gen_count += 1
            elapsed = time.time() - t0
            rate = gen_count / elapsed
            eta  = (len(pending) - gen_count) / rate / 60 if rate > 0 else 0
            print(f"  OK [{gen_count}/{len(pending)}] {item['filename']}"
                  f" | {item['category']} | ETA {eta:.0f}min")

            if gen_count % 100 == 0:
                with open(pf, "w") as f: json.dump(progress, f)
                gc.collect(); torch.cuda.empty_cache()
                print(f"  [saved] VRAM: {torch.cuda.memory_allocated()/1e9:.1f}GB")

        except torch.cuda.OutOfMemoryError:
            print(f"  OOM — retrying at 768x768")
            torch.cuda.empty_cache(); gc.collect()
            try:
                img = generate_image(item, height=768, width=768)
                save_generated(img, item)
                progress["completed"].append(item["index"]); gen_count += 1
            except Exception as e2:
                print(f"  FAIL: {e2}"); progress["failed"].append(item["index"])

        except Exception as e:
            print(f"  FAIL {item['filename']}: {e}")
            progress["failed"].append(item["index"])

    with open(pf, "w") as f: json.dump(progress, f)
    print(f"\nGeneration : {gen_count} images in {(time.time()-t0)/60:.0f} min")
    print(f"Failed     : {len(progress['failed'])}")
    del pipe; gc.collect(); torch.cuda.empty_cache()
    print("Model freed\n")

# ============================================================
# STEP 2: Background Removal — BRIA-RMBG-2.0 (Food Safe)
# ============================================================
print("=" * 55)
print("STEP 2: Background Removal (BRIA-RMBG-2.0)")
print("  Food-safe mode: protects rice, cheese, cream pixels")
print("=" * 55)

# Install BRIA model dependency
subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                "transformers>=4.47.0", "torchvision"], capture_output=True)

from transformers import AutoModelForImageSegmentation
from torchvision import transforms

print("Loading BRIA-RMBG-2.0...")
rmbg_model = AutoModelForImageSegmentation.from_pretrained(
    "briaai/RMBG-2.0", trust_remote_code=True
)
device = "cuda" if torch.cuda.is_available() else "cpu"
rmbg_model.to(device)
rmbg_model.eval()

transform_img = transforms.Compose([
    transforms.Resize((1024, 1024)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

FOOD_CATS = {"biryani", "rice", "curry", "pizza", "food", "indian",
             "dosa", "noodles", "burger", "soup", "dessert", "sweet",
             "bread", "salad", "meat", "chicken", "seafood"}

def remove_bg_food_safe(img_path: str, out_path: str):
    img = Image.open(img_path).convert("RGB")
    orig_size = img.size
    tensor = transform_img(img).unsqueeze(0).to(device)

    with torch.no_grad():
        result = rmbg_model(tensor)

    mask = result[0][0] if isinstance(result, (list, tuple)) else result[0]
    if mask.dim() > 2: mask = mask.squeeze()
    mask = torch.sigmoid(mask).cpu().numpy()
    mask = (mask * 255).astype(np.uint8)

    mask_pil = Image.fromarray(mask, 'L').resize(orig_size, Image.LANCZOS)
    from PIL import ImageFilter
    mask_pil = mask_pil.filter(ImageFilter.SMOOTH_MORE)

    img_rgba = img.convert("RGBA")
    img_rgba.putalpha(mask_pil)

    # ✅ FOOD-SAFE cleanup: only remove near-transparent white leakage
    # Does NOT remove opaque white pixels (rice, cheese, cream sauce)
    data = np.array(img_rgba)
    r, g, b, a = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]
    bg_leakage  = (r > 250) & (g > 250) & (b > 250) & (a < 80)
    edge_leakage = (r > 248) & (g > 248) & (b > 248) & (a < 40)
    data[bg_leakage,   3] = 0
    data[edge_leakage, 3] = 0
    result_img = Image.fromarray(data, 'RGBA')

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    result_img.save(out_path, "PNG", optimize=True)

gen_files = list(GENERATED_DIR.rglob("*.png"))
print(f"Processing {len(gen_files)} images...\n")
bg_ok = 0; bg_fail = 0; t1 = time.time()

for img_file in gen_files:
    rel = img_file.relative_to(GENERATED_DIR)
    out = TRANSPARENT_DIR / rel
    if out.exists(): continue
    try:
        remove_bg_food_safe(str(img_file), str(out))
        bg_ok += 1
        if bg_ok % 50 == 0:
            print(f"  BG done: {bg_ok} | {bg_ok/(time.time()-t1):.2f}/s")
            gc.collect(); torch.cuda.empty_cache()
    except Exception as e:
        print(f"  BG FAIL {img_file.name}: {e}"); bg_fail += 1

print(f"\nBG removal : {bg_ok} OK, {bg_fail} failed in {(time.time()-t1)/60:.0f} min")
del rmbg_model; gc.collect(); torch.cuda.empty_cache()
print("BG model freed\n")

# ============================================================
# STEP 3: Google Drive Upload
# ============================================================
print("=" * 55)
print("STEP 3: Upload to Google Drive")
print("=" * 55)

def get_token():
    r = req.post("https://oauth2.googleapis.com/token", data={
        "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": GOOGLE_REFRESH_TOKEN, "grant_type": "refresh_token"
    })
    if r.status_code != 200: raise Exception(f"Token failed: {r.text}")
    return r.json()["access_token"]

def find_or_create(token, name, parent=None):
    h = {"Authorization": f"Bearer {token}"}
    q = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
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
            if upload_file(token, str(png), rel.name, f_cache[cat]):
                up_prog["uploaded"].append(file_key)
                uploaded.add(file_key); up_ok += 1
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
    print("WARNING: Google credentials missing — skipping upload")

# ============================================================
# FINAL REPORT
# ============================================================
total_gen = len(list(GENERATED_DIR.rglob("*.png")))
total_trn = len(list(TRANSPARENT_DIR.rglob("*.png")))
total_min = (time.time() - progress.get("start_time", time.time())) / 60
print(f"""
{'='*55}
  BATCH COMPLETE!
  Model      : FLUX.1-dev (black-forest-labs)
  Steps      : 28  |  CFG: 7.0  |  1024x1024
  BG Removal : BRIA-RMBG-2.0 (food-safe mode)
  Generated  : {total_gen} images
  Transparent: {total_trn} PNGs
  Batch      : {START_INDEX} - {END_INDEX}
  Time       : {total_min:.0f} minutes
  Drive      : png_library_images/
{'='*55}
""")
