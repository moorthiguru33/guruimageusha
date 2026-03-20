"""
PNG Library - Kaggle Pipeline
=============================================================
Model   : FLUX.1 [dev]
HF ID   : black-forest-labs/FLUX.1-dev
License : Non-commercial (Black Forest Labs)
VRAM    : ~16GB on T4 16GB - fits with cpu offload
Steps   : 28 steps (full model - high quality)
Output  : 1536x1536 (direct) | OOM fallback: 1024 + 1.5x upscale
Batch   : 400-600 images/run (slower but higher quality)
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
    "requests",
    "basicsr",
    "facexlib",
    "gfpgan",
    "realesrgan",
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
PROMPTS_FILE    = WORKING_DIR / "all_prompts.json"
PROGRESS_DIR    = WORKING_DIR / "progress"
PROJECT_DIR     = WORKING_DIR / "project"
for d in [GENERATED_DIR, PROGRESS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Credentials ───────────────────────────────────────────────
GOOGLE_CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN", "")
GITHUB_REPO          = os.environ.get("GITHUB_REPO", "")
START_INDEX          = int(os.environ.get("START_INDEX", "0"))
END_INDEX            = int(os.environ.get("END_INDEX", "800"))

print("=" * 55)
print("  PNG LIBRARY — FLUX.1 [dev]")
print("  Non-commercial | ~16GB VRAM w/ offload | T4")
print("=" * 55)
print(f"  Batch  : {START_INDEX} -> {END_INDEX}  ({END_INDEX - START_INDEX} images)")
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

# ============================================================
# STEP 1: FLUX.2 [klein] 4B — Image Generation
# ============================================================
if pending:
    print("=" * 55)
    print("STEP 1: FLUX.1 [dev] Generation")
    print("=" * 55)
    print("Loading black-forest-labs/FLUX.1-dev ...")
    print("(First run: downloads ~24GB — ~10 min)\n")

    # ── HuggingFace login (FLUX.1-dev is gated) ──────────────
    from huggingface_hub import login
    try:
        from kaggle_secrets import UserSecretsClient
        hf_token = UserSecretsClient().get_secret("HF_TOKEN")
        login(token=hf_token, add_to_git_credential=False)
        print("✅ HuggingFace login: OK")
    except Exception as e:
        print(f"❌ HF login failed: {e}")
        raise SystemExit("Add HF_TOKEN to Kaggle Secrets (Add-ons → Secrets)")

    from diffusers import FluxPipeline
    pipe = FluxPipeline.from_pretrained(
        "black-forest-labs/FLUX.1-dev",
        torch_dtype=torch.bfloat16,
    )
    print("Loaded with FluxPipeline")

    pipe.enable_model_cpu_offload()
    pipe.enable_attention_slicing(slice_size="auto")
    pipe.vae.enable_tiling()
    print(f"Model loaded! VRAM: {torch.cuda.memory_allocated()/1e9:.1f} GB\n")

    def make_prompt(raw):
        """Add realism boosters for PNG library quality"""
        return (
            raw +
            ", hyperrealistic photography, shot on Canon EOS R5, "
            "photorealistic, sharp focus, real life texture, "
            "professional studio lighting, high resolution"
        )

    def generate_image(item):
        generator = torch.Generator(device="cpu").manual_seed(item["seed"])
        return pipe(
            prompt=make_prompt(item["prompt"]),
            num_inference_steps=28,
            guidance_scale=3.5,
            height=1536,
            width=1536,
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
            print(f"  OK [{gen_count}/{len(pending)}] {item['filename']}"
                  f" | {item['category']} | ETA {eta:.0f}min")

            if gen_count % 100 == 0:
                with open(pf, "w") as f: json.dump(progress, f)
                gc.collect(); torch.cuda.empty_cache()
                print(f"  [saved] VRAM: {torch.cuda.memory_allocated()/1e9:.1f}GB")

        except torch.cuda.OutOfMemoryError:
            print(f"  OOM — retrying {item['filename']} at 1024x1024")
            torch.cuda.empty_cache(); gc.collect()
            try:
                gen = torch.Generator(device="cpu").manual_seed(item["seed"])
                img = pipe(
                    prompt=make_prompt(item["prompt"]),
                    num_inference_steps=28,
                    guidance_scale=3.5,
                    height=1024, width=1024,
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
# STEP 2: Google Drive Upload
# ============================================================
print("=" * 55)
print("STEP 2: Upload to Google Drive")
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

        png_files = list(GENERATED_DIR.rglob("*.png"))
        up_ok = 0; t2 = time.time()
        print(f"Uploading {len(png_files)} PNGs...")

        for png in png_files:
            rel      = png.relative_to(GENERATED_DIR)
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
total_min = (time.time() - progress.get("start_time", time.time())) / 60
print(f"""
{'='*55}
  BATCH COMPLETE!
  Model      : FLUX.1 [dev] (Non-commercial)
  Steps      : 28  |  CFG: 3.5  |  1536x1536
  Generated  : {total_gen} images
  Batch      : {START_INDEX} - {END_INDEX}
  Time       : {total_min:.0f} minutes
  Drive      : png_library_images/
{'='*55}
""")
