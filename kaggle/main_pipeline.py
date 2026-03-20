"""
PNG Library - Kaggle Pipeline
Model  : FLUX.2 [klein] 4B  (Apache 2.0 - FREE)
Output : 2048x2048 native PNG (no upscaler)
BG     : BRIA-RMBG-2.0 (pixel-perfect transparency)
Drive  : Google OAuth2 -> png_library_images/
"""

# CELL 1: Install Dependencies (run once)
"""
!pip install -q diffusers transformers accelerate
!pip install -q torch torchvision Pillow requests numpy
!pip install -q huggingface_hub bitsandbytes
!pip install -q timm kornia
"""

import os, sys, json, time, gc
from pathlib import Path
import torch
import numpy as np
from PIL import Image
from diffusers import FluxPipeline
from transformers import AutoModelForImageSegmentation
from torchvision import transforms

# ─── Paths ────────────────────────────────────────────────
WORKING_DIR     = Path("/kaggle/working")
GENERATED_DIR   = WORKING_DIR / "generated_images"
TRANSPARENT_DIR = WORKING_DIR / "transparent_pngs"
PROMPTS_FILE    = WORKING_DIR / "all_prompts.json"
PROGRESS_DIR    = WORKING_DIR / "progress"
for d in [GENERATED_DIR, TRANSPARENT_DIR, PROGRESS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ─── Secrets ──────────────────────────────────────────────
GOOGLE_CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN", "")
GITHUB_REPO          = os.environ.get("GITHUB_REPO", "")
START_INDEX          = int(os.environ.get("START_INDEX", "0"))
END_INDEX            = int(os.environ.get("END_INDEX", "1500"))

print(f"Batch: {START_INDEX} -> {END_INDEX}")
if torch.cuda.is_available():
    props = torch.cuda.get_device_properties(0)
    print(f"GPU: {props.name} | VRAM: {props.total_memory/1e9:.0f} GB")

# ─── Clone repo ───────────────────────────────────────────
if GITHUB_REPO:
    os.system(f"git clone https://github.com/{GITHUB_REPO} /kaggle/working/project")
    sys.path.insert(0, "/kaggle/working/project")

# ─── Load prompts ─────────────────────────────────────────
def load_or_generate_prompts():
    if PROMPTS_FILE.exists():
        with open(PROMPTS_FILE) as f: return json.load(f)
    sys.path.insert(0, "/kaggle/working/project")
    from prompts.prompt_engine import PromptEngine
    prompts = PromptEngine().generate_all_prompts()
    with open(PROMPTS_FILE, "w") as f: json.dump(prompts, f, indent=2)
    return prompts

all_prompts   = load_or_generate_prompts()
batch_prompts = all_prompts[START_INDEX:END_INDEX]
print(f"Total prompts: {len(all_prompts)} | Batch: {len(batch_prompts)}")

# ─── Resume support ───────────────────────────────────────
pf = PROGRESS_DIR / f"progress_{START_INDEX}_{END_INDEX}.json"
progress = json.load(open(pf)) if pf.exists() else \
           {"completed": [], "failed": [], "start_time": time.time()}
done_set  = set(progress["completed"])
pending   = [p for p in batch_prompts if p["index"] not in done_set]
print(f"Pending: {len(pending)}")

# ============================================================
# STEP 1: FLUX.2 [klein] 4B — Generate 2048x2048
# ============================================================
print("\n--- STEP 1: Image Generation (FLUX.2 [klein] 4B) ---")

pipe = FluxPipeline.from_pretrained(
    "black-forest-labs/FLUX.2-klein-4B",
    torch_dtype=torch.bfloat16
)
pipe.enable_model_cpu_offload()
pipe.enable_attention_slicing(slice_size="auto")
pipe.vae.enable_tiling()
print(f"FLUX.2 loaded | VRAM: {torch.cuda.memory_allocated()/1e9:.1f} GB")

def generate(item):
    gen = torch.Generator(device="cpu").manual_seed(item["seed"])
    return pipe(
        prompt=item["prompt"],
        num_inference_steps=8,
        guidance_scale=3.5,
        height=2048, width=2048,
        max_sequence_length=512,
        generator=gen,
    ).images[0]

def save_gen(img, item):
    folder = GENERATED_DIR / item["category"] / item.get("subcategory", "general")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / item["filename"]
    img.save(str(path), "PNG")
    return str(path)

gen_count = 0
t0 = time.time()

for item in pending:
    try:
        img = generate(item)
        save_gen(img, item)
        progress["completed"].append(item["index"])
        gen_count += 1
        elapsed = time.time() - t0
        rate    = gen_count / elapsed
        eta     = (len(pending) - gen_count) / rate / 60 if rate > 0 else 0
        print(f"  OK [{gen_count}/{len(pending)}] {item['filename']} | 2048x2048 | ETA {eta:.0f}min")
        if gen_count % 50 == 0:
            with open(pf, "w") as f: json.dump(progress, f)
            gc.collect(); torch.cuda.empty_cache()
    except Exception as e:
        print(f"  FAIL {item['filename']}: {e}")
        progress["failed"].append(item["index"])

with open(pf, "w") as f: json.dump(progress, f)
print(f"\nGeneration done: {gen_count} images in {(time.time()-t0)/60:.0f} min")

# Free VRAM before BG removal
del pipe; gc.collect(); torch.cuda.empty_cache()
print("Generation model freed")

# ============================================================
# STEP 2: BRIA-RMBG-2.0 — Perfect Background Removal
# ============================================================
print("\n--- STEP 2: Background Removal (BRIA-RMBG-2.0) ---")

rmbg = AutoModelForImageSegmentation.from_pretrained(
    "briaai/RMBG-2.0", trust_remote_code=True
).to("cuda" if torch.cuda.is_available() else "cpu")
rmbg.eval()

tf = transforms.Compose([
    transforms.Resize((1024, 1024)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

def remove_bg(img, category=""):
    # Smoke/effects: luminosity-based removal (white -> transparent)
    if any(k in category.lower() for k in ["smoke", "effect"]):
        d   = np.array(img.convert("RGBA"))
        lum = (0.299*d[:,:,0] + 0.587*d[:,:,1] + 0.114*d[:,:,2]).astype(np.uint8)
        d[:,:,3] = 255 - lum
        d[d[:,:,3] < 10, 3] = 0
        return Image.fromarray(d, "RGBA")

    # Everything else: BRIA-RMBG-2.0
    dev  = next(rmbg.parameters()).device
    orig = img.size
    t    = tf(img.convert("RGB")).unsqueeze(0).to(dev)
    with torch.no_grad():
        result = rmbg(t)
    mask = result[0][0] if isinstance(result, (list, tuple)) else result[0]
    if mask.dim() > 2: mask = mask.squeeze()
    mask     = (torch.sigmoid(mask).cpu().numpy() * 255).astype(np.uint8)
    mask_pil = Image.fromarray(mask, "L").resize(orig, Image.LANCZOS)
    out      = img.convert("RGB").convert("RGBA")
    out.putalpha(mask_pil)
    # Clean near-white remnants
    d  = np.array(out)
    nw = (d[:,:,0]>240)&(d[:,:,1]>240)&(d[:,:,2]>240)&(d[:,:,3]>0)&(d[:,:,3]<200)
    d[nw, 3] = 0
    return Image.fromarray(d, "RGBA")

bg_count = 0
t1 = time.time()

for img_file in GENERATED_DIR.rglob("*.png"):
    rel = img_file.relative_to(GENERATED_DIR)
    out = TRANSPARENT_DIR / rel
    if out.exists(): continue
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        img = Image.open(str(img_file)).convert("RGB")
        res = remove_bg(img, category=str(rel.parent))
        res.save(str(out), "PNG", optimize=True)
        bg_count += 1
        if bg_count % 50 == 0:
            print(f"  BG done: {bg_count} | {bg_count/(time.time()-t1):.2f}/s")
            gc.collect(); torch.cuda.empty_cache()
    except Exception as e:
        print(f"  BG FAIL {img_file.name}: {e}")

print(f"BG removal done: {bg_count} images in {(time.time()-t1)/60:.0f} min")
del rmbg; gc.collect(); torch.cuda.empty_cache()

# ============================================================
# STEP 3: Upload to Google Drive
# ============================================================
print("\n--- STEP 3: Upload to Google Drive ---")

if all([GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN]):
    sys.path.insert(0, "/kaggle/working/project")
    from pipeline.drive_upload import OAuth2TokenManager, GoogleDriveUploader
    stats = GoogleDriveUploader(OAuth2TokenManager()).upload_folder(
        str(TRANSPARENT_DIR),
        progress_file=str(PROGRESS_DIR / f"upload_{START_INDEX}.json")
    )
    print(f"Upload: {stats}")
else:
    print("WARNING: Google creds missing -- skipping upload")

# ============================================================
# Final Report
# ============================================================
gen_total = len(list(GENERATED_DIR.rglob("*.png")))
trn_total = len(list(TRANSPARENT_DIR.rglob("*.png")))
elapsed   = (time.time() - float(progress.get("start_time", time.time()))) / 3600

print(f"""
================================================================
  BATCH COMPLETE!
  Model       : FLUX.2 [klein] 4B
  Resolution  : 2048 x 2048 (native)
  Generated   : {gen_total} images
  Transparent : {trn_total} PNGs
  Batch       : {START_INDEX} - {END_INDEX}
  Time        : {elapsed:.1f} hours
  Drive folder: png_library_images/
================================================================
""")
