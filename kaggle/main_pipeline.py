"""
PNG Library - Kaggle Pipeline V3
=============================================================
Model   : FLUX.2 [klein] 4B
HF ID   : black-forest-labs/FLUX.2-klein-4B
License : Apache 2.0 - FREE for commercial use
VRAM    : ~4-6GB with sequential offload on T4 16GB
Steps   : 4 (distilled - fast + good quality)
CFG     : 0.0 (REQUIRED for distilled — any other value is ignored/wrong)
Batch   : 500 images/run ~ 3hrs (safe within 30hr/week)
=============================================================

V3 OOM FIXES:
  - enable_sequential_cpu_offload() replaces enable_model_cpu_offload()
    → moves each layer GPU<->CPU one-at-a-time
    → uses ~4-6GB VRAM instead of ~12GB  ← BIGGEST FIX
  - guidance_scale=0.0 everywhere (distilled model requirement — NOT 3.5, NOT 1.5)
  - max_sequence_length=256 (saves ~1GB text encoder VRAM)
  - VRAM flush before EVERY image (prevents fragmentation)
  - 3-tier OOM fallback: 1024 → 768 → 512
  - Checkpoint every 25 images (was 100)
=============================================================
"""

import os, sys, json, time, gc, subprocess

# Memory fragmentation fix (recommended by PyTorch)
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

from pathlib import Path

# ── Install dependencies ───────────────────────────────────────────────────
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

# ── Paths ──────────────────────────────────────────────────────────────────
WORKING_DIR     = Path("/kaggle/working")
GENERATED_DIR   = WORKING_DIR / "generated_images"
TRANSPARENT_DIR = WORKING_DIR / "transparent_pngs"
PROMPTS_DIR     = WORKING_DIR / "prompts_splits"
PROGRESS_DIR    = WORKING_DIR / "progress"
PROJECT_DIR     = WORKING_DIR / "project"
for d in [GENERATED_DIR, TRANSPARENT_DIR, PROGRESS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Credentials ────────────────────────────────────────────────────────────
GOOGLE_CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN", "")
GITHUB_REPO          = os.environ.get("GITHUB_REPO", "")
START_INDEX          = int(os.environ.get("START_INDEX", "0"))
END_INDEX            = int(os.environ.get("END_INDEX", "500"))

print("=" * 55)
print("  PNG LIBRARY V3 — FLUX.2 [klein] 4B")
print("  Apache 2.0 | Sequential CPU Offload | T4")
print("=" * 55)
print(f"  Batch  : {START_INDEX} -> {END_INDEX}  ({END_INDEX - START_INDEX} images)")
if torch.cuda.is_available():
    p = torch.cuda.get_device_properties(0)
    print(f"  GPU    : {p.name}  |  VRAM: {p.total_memory/1e9:.0f} GB")
print("=" * 55 + "\n")

# ── Clone repo ─────────────────────────────────────────────────────────────
if GITHUB_REPO and not PROJECT_DIR.exists():
    os.system(f"git clone https://github.com/{GITHUB_REPO} {PROJECT_DIR}")
    sys.path.insert(0, str(PROJECT_DIR))
    print(f"Cloned: {GITHUB_REPO}")

# ── Load prompts ───────────────────────────────────────────────────────────
def load_or_generate_prompts():
    repo_splits  = PROJECT_DIR / "prompts" / "splits"
    local_splits = PROMPTS_DIR

    for splits_dir in [repo_splits, local_splits]:
        if splits_dir.exists() and any(splits_dir.glob("*.json")):
            sys.path.insert(0, str(PROJECT_DIR))
            from prompts.prompt_engine import load_all_prompts
            prompts = load_all_prompts(str(splits_dir))
            print(f"Loaded {len(prompts)} prompts from {splits_dir}")
            return prompts

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

# ── Skip helper ────────────────────────────────────────────────────────────
def is_already_generated(item):
    path = GENERATED_DIR / item["category"] / item.get("subcategory", "general") / item["filename"]
    return path.exists()

# ── Drive helpers ──────────────────────────────────────────────────────────
def _drive_token():
    if all([GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN]):
        try:
            r = req.post("https://oauth2.googleapis.com/token", data={
                "client_id":     GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "refresh_token": GOOGLE_REFRESH_TOKEN,
                "grant_type":    "refresh_token",
            })
            if r.status_code == 200:
                return r.json()["access_token"]
        except Exception:
            pass
    return None

def _drive_find_file(token, name):
    h = {"Authorization": f"Bearer {token}"}
    r = req.get("https://www.googleapis.com/drive/v3/files", headers=h,
                params={"q": f"name='{name}' and trashed=false", "fields": "files(id)"})
    files = r.json().get("files", [])
    return files[0]["id"] if files else None

def _drive_upsert(token, name, content_bytes):
    h   = {"Authorization": f"Bearer {token}"}
    fid = _drive_find_file(token, name)
    if fid:
        req.patch(f"https://www.googleapis.com/upload/drive/v3/files/{fid}?uploadType=media",
                  headers={**h, "Content-Type": "application/json"}, data=content_bytes)
    else:
        req.post("https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
                 headers=h,
                 files=[("metadata", ("m", json.dumps({"name": name}), "application/json")),
                        ("file",     (name, content_bytes, "application/json"))])

def _drive_fetch(token, name):
    fid = _drive_find_file(token, name)
    if not fid: return None
    h = {"Authorization": f"Bearer {token}"}
    r = req.get(f"https://www.googleapis.com/drive/v3/files/{fid}?alt=media", headers=h)
    return r.json()

def save_progress_to_drive(data, start, end):
    token = _drive_token()
    if not token: return
    try:
        _drive_upsert(token, f"progress_{start}_{end}.json", json.dumps(data).encode())
        print(f"  [drive] Progress saved ({len(data['completed'])} done)")
    except Exception as e:
        print(f"  [drive] Progress save failed: {e}")

def load_progress_from_drive(start, end):
    token = _drive_token()
    if not token: return None
    try:
        data = _drive_fetch(token, f"progress_{start}_{end}.json")
        if data: print(f"  [drive] Loaded progress: {len(data.get('completed', []))} already done")
        return data
    except Exception as e:
        print(f"  [drive] Progress load failed: {e}")
        return None

def save_upload_progress_to_drive(data, start):
    token = _drive_token()
    if not token: return
    try:
        _drive_upsert(token, f"upload_progress_{start}.json", json.dumps(data).encode())
        print(f"  [drive] Upload progress saved ({len(data['uploaded'])} uploaded)")
    except Exception as e:
        print(f"  [drive] Upload progress save failed: {e}")

def load_upload_progress_from_drive(start):
    token = _drive_token()
    if not token: return None
    try:
        data = _drive_fetch(token, f"upload_progress_{start}.json")
        if data: print(f"  [drive] Loaded upload progress: {len(data.get('uploaded', []))} already uploaded")
        return data
    except Exception as e:
        print(f"  [drive] Upload progress load failed: {e}")
        return None

# ── Resume ─────────────────────────────────────────────────────────────────
pf = PROGRESS_DIR / f"progress_{START_INDEX}_{END_INDEX}.json"
if pf.exists():
    with open(pf) as f:
        progress = json.load(f)
    print(f"Resuming   : {len(progress['completed'])} already done (local)")
else:
    drive_prog = load_progress_from_drive(START_INDEX, END_INDEX)
    if drive_prog:
        progress = drive_prog
        with open(pf, "w") as f: json.dump(progress, f)
        print(f"Resuming   : {len(progress['completed'])} already done (from Drive)")
    else:
        progress = {"completed": [], "failed": [], "start_time": time.time()}
        print("Resuming   : fresh start")

done_set = set(progress["completed"])
pending  = [p for p in batch_prompts
            if not is_already_generated(p) and p["index"] not in done_set]
print(f"Pending    : {len(pending)} images\n")

# ── Category enhancers ─────────────────────────────────────────────────────
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
    if category in VECTOR_CATEGORIES:
        return raw_prompt
    for cat_key, enhancer in CATEGORY_ENHANCERS.items():
        if category.startswith(cat_key):
            return raw_prompt + enhancer
    return raw_prompt

# ── VRAM utilities ─────────────────────────────────────────────────────────
def vram_free_gb():
    if torch.cuda.is_available():
        return (torch.cuda.get_device_properties(0).total_memory
                - torch.cuda.memory_allocated(0)) / 1e9
    return 0.0

def flush_vram():
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()

def save_generated(img, item):
    folder = GENERATED_DIR / item["category"] / item.get("subcategory", "general")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / item["filename"]
    img.save(str(path), "PNG", compress_level=0)
    return str(path)

def is_good(img):
    arr = np.array(img)
    return arr.std() > 5 and (arr < 250).sum() > 1000

# ============================================================
# STEP 1: FLUX.2 [klein] 4B — Image Generation
# ============================================================
if pending:
    from diffusers import Flux2KleinPipeline

    print("=" * 55)
    print("STEP 1: FLUX.2 [klein] 4B Generation")
    print("=" * 55)
    print("Loading black-forest-labs/FLUX.2-klein-4B ...")
    print("(First run: downloads ~8GB — ~5 min)\n")

    pipe = Flux2KleinPipeline.from_pretrained(
        "black-forest-labs/FLUX.2-klein-4B",
        torch_dtype=torch.bfloat16,
    )

    # KEY FIX: sequential offload = ~4-6GB VRAM vs ~12GB with model offload
    pipe.enable_sequential_cpu_offload()
    pipe.enable_vae_tiling()          # saves ~1-2GB on VAE decode
    pipe.set_progress_bar_config(disable=True)

    print("Model loaded (bfloat16 | sequential_cpu_offload | vae_tiling)!")
    print(f"VRAM free after load: {vram_free_gb():.1f} GB\n")

    def _generate(prompt, seed, h=1024, w=1024):
        """
        guidance_scale MUST be 0.0 for distilled FLUX.2 klein.
        Any non-zero value is ignored by the model (causes the warning in logs).
        max_sequence_length=256 saves ~1GB vs default 512.
        """
        gen = torch.Generator(device="cpu").manual_seed(seed)
        return pipe(
            prompt              = prompt,
            num_inference_steps = 4,
            guidance_scale      = 0.0,   # distilled model — MUST be 0.0
            height              = h,
            width               = w,
            max_sequence_length = 256,   # 256 saves ~1GB VRAM vs 512
            generator           = gen,
        ).images[0]

    gen_count = 0
    t0        = time.time()
    print(f"Generating {len(pending)} images at 1024x1024...\n")

    for item in pending:
        flush_vram()  # flush before every image to prevent fragmentation

        prompt = enhance_prompt(item["prompt"], item.get("category", ""))
        cat    = item.get("category", "")
        mode   = "VEC" if cat in VECTOR_CATEGORIES else "PHO"

        try:
            # Primary: 1024x1024
            img = _generate(prompt, item["seed"], h=1024, w=1024)
            if not is_good(img):
                img = _generate(prompt, item["seed"] + 42, h=1024, w=1024)
            save_generated(img, item)
            progress["completed"].append(item["index"])
            gen_count += 1
            elapsed = time.time() - t0
            rate    = gen_count / elapsed
            eta     = (len(pending) - gen_count) / rate / 60 if rate > 0 else 0
            print(f"  OK [{gen_count}/{len(pending)}] {item['filename']} | {cat} [{mode}] | ETA {eta:.0f}min")

        except torch.cuda.OutOfMemoryError:
            # Fallback 1: 768x768
            flush_vram()
            print(f"  OOM -> retrying {item['filename']} at 768x768")
            try:
                img = _generate(prompt, item["seed"], h=768, w=768)
                save_generated(img, item)
                progress["completed"].append(item["index"])
                gen_count += 1
                print(f"  OK [{gen_count}/{len(pending)}] {item['filename']} [768px]")

            except torch.cuda.OutOfMemoryError:
                # Fallback 2: 512x512
                flush_vram()
                print(f"  OOM -> retrying {item['filename']} at 512x512")
                try:
                    img = _generate(prompt, item["seed"], h=512, w=512)
                    save_generated(img, item)
                    progress["completed"].append(item["index"])
                    gen_count += 1
                    print(f"  OK [{gen_count}/{len(pending)}] {item['filename']} [512px]")
                except Exception as e2:
                    print(f"  FAIL (all sizes): {e2}")
                    progress["failed"].append(item["index"])
            except Exception as e2:
                print(f"  FAIL: {e2}")
                progress["failed"].append(item["index"])

        except Exception as e:
            print(f"  FAIL {item['filename']}: {e}")
            progress["failed"].append(item["index"])

        # Checkpoint every 25 images (was 100 — too infrequent for OOM recovery)
        if gen_count % 25 == 0 and gen_count > 0:
            with open(pf, "w") as f: json.dump(progress, f)
            save_progress_to_drive(progress, START_INDEX, END_INDEX)
            flush_vram()
            print(f"  [checkpoint] {gen_count} done | VRAM free: {vram_free_gb():.1f} GB")

    with open(pf, "w") as f: json.dump(progress, f)
    save_progress_to_drive(progress, START_INDEX, END_INDEX)
    print(f"\nGeneration : {gen_count} images in {(time.time()-t0)/60:.0f} min")
    print(f"Failed     : {len(progress['failed'])}")
    del pipe
    flush_vram()
    print(f"Model freed | VRAM free: {vram_free_gb():.1f} GB\n")

# ============================================================
# STEP 2: Background Removal (rembg — birefnet-general)
# ============================================================
print("=" * 55)
print("STEP 2: Background Removal (rembg)")
print("=" * 55)

from rembg import remove as rembg_remove, new_session

_rembg_session = new_session(
    "birefnet-general",
    providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
)
print("rembg loaded (birefnet-general)\n")

gen_files = list(GENERATED_DIR.rglob("*.png"))
print(f"Processing {len(gen_files)} images...\n")
bg_ok = 0; bg_fail = 0; t1 = time.time()

for img_file in gen_files:
    rel = img_file.relative_to(GENERATED_DIR)
    out = TRANSPARENT_DIR / rel
    if out.exists(): continue
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        img    = Image.open(str(img_file)).convert("RGB")
        result = rembg_remove(img, session=_rembg_session)
        result.save(str(out), "PNG", compress_level=0)
        bg_ok += 1
        if bg_ok % 50 == 0:
            print(f"  BG done: {bg_ok} | {bg_ok/(time.time()-t1):.2f}/s")
            flush_vram()
    except Exception as e:
        print(f"  BG FAIL {img_file.name}: {e}")
        bg_fail += 1

print(f"\nBG removal : {bg_ok} OK, {bg_fail} failed in {(time.time()-t1)/60:.0f} min")
flush_vram()
print("BG done\n")

# ============================================================
# STEP 3: Google Drive Upload
# ============================================================
print("=" * 55)
print("STEP 3: Upload to Google Drive")
print("=" * 55)

def get_token():
    r = req.post("https://oauth2.googleapis.com/token", data={
        "client_id":     GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": GOOGLE_REFRESH_TOKEN,
        "grant_type":    "refresh_token"
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
    h = {"Authorization": f"Bearer {token}"}
    with open(path, "rb") as f: data = f.read()
    meta = json.dumps({"name": name, "parents": [folder_id]})
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

        if up_pf.exists():
            up_prog = json.load(open(up_pf))
        else:
            drive_up = load_upload_progress_from_drive(START_INDEX)
            up_prog  = drive_up if drive_up else {"uploaded": []}
            if drive_up:
                with open(up_pf, "w") as f: json.dump(up_prog, f)

        uploaded    = set(up_prog["uploaded"])
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
                    save_upload_progress_to_drive(up_prog, START_INDEX)
                    print(f"  Uploaded: {up_ok} | {up_ok/(time.time()-t2):.2f}/s")
            else:
                print(f"  Upload FAIL: {file_key}")
            time.sleep(0.05)

        with open(up_pf, "w") as f: json.dump(up_prog, f)
        save_upload_progress_to_drive(up_prog, START_INDEX)
        print(f"\nUpload done: {up_ok} files in {(time.time()-t2)/60:.0f} min")

    except Exception as e:
        print(f"Drive error: {e}")
else:
    print("WARNING: Google credentials missing — skipping upload.")

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
  Steps      : 4  |  CFG: 0.0  |  1024x1024 PNG
  Offload    : Sequential CPU offload (OOM-safe)
  BG Removal : rembg (birefnet-general)
  Generated  : {total_gen} images
  Transparent: {total_trn} PNGs
  Batch      : {START_INDEX} - {END_INDEX}
  Time       : {total_min:.0f} minutes
  Drive      : png_library_images/
{'='*55}
""")
