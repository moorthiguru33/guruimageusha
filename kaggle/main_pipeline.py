"""
╔══════════════════════════════════════════════════════════════╗
║   UltraPNG.com — PNG Library Pipeline V9.0                  ║
╠══════════════════════════════════════════════════════════════╣
║  PHASE 1 → FLUX.2-Klein-4B   Generate 1024×1024 images      ║
║  PHASE 2 → Qwen2.5-VL-7B    Filter + SEO (V9 8-bit)         ║
║  PHASE 3 → BiRefNet_HR      Background removal (GPU FP16)    ║
║  PHASE 4 → Google Drive      Upload PNG + WebP (parallel)    ║
║  PHASE 5 → JSON-Only Git Push → REPO2 (sparse checkout)     ║
║  PHASE 6 → Save Run Logs → REPO1                            ║
╠══════════════════════════════════════════════════════════════╣
║  V9.0 CHANGES (from V8.0):                                  ║
║  • UPGRADE: Qwen 3B → 7B-Instruct (better quality)          ║
║  • UPGRADE: Qwen float16 → 8-bit BitsAndBytes quantization  ║
║  • UPGRADE: Batch 800 → 200 per day (Kaggle safe)           ║
║  • UPGRADE: SEO description 300-400w structured template     ║
║  • UPGRADE: 8 unique title patterns (no duplicate titles)    ║
║  • UPGRADE: Better meta_desc with LSI keywords              ║
║  • FIX: Memory efficient — 7B 8-bit uses ~7GB VRAM          ║
║  • FIX: Sequential model loading (FLUX→Qwen→RMBG) safe      ║
╚══════════════════════════════════════════════════════════════╝

inject_creds.py prepends os.environ[] lines before this file.
"""

import os, sys, json, time, gc, re, io, shutil, base64, subprocess
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

# ── HuggingFace cache dir ────────────────────────
HF_CACHE = Path("/kaggle/working/hf_cache")
HF_CACHE.mkdir(parents=True, exist_ok=True)
os.environ["HF_HOME"]               = str(HF_CACHE)
os.environ["HUGGINGFACE_HUB_CACHE"] = str(HF_CACHE)
os.environ["TRANSFORMERS_CACHE"]    = str(HF_CACHE)
_hf_token = os.environ.get("HF_TOKEN", "")
if _hf_token:
    os.environ["HUGGINGFACE_HUB_TOKEN"] = _hf_token

# ══════════════════════════════════════════════════
# Model IDs — V9.0
# ══════════════════════════════════════════════════
FLUX_HF_ID = "black-forest-labs/FLUX.2-klein-4B"
QWEN_HF_ID = "Qwen/Qwen2.5-VL-7B-Instruct"   # V9: 3B → 7B
RMBG_HF_ID = "ZhengPeng7/BiRefNet_HR"

# ══════════════════════════════════════════════════
# LOG
# ══════════════════════════════════════════════════
_LOG_LINES = []

def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    _LOG_LINES.append(line)

# ── Install ALL deps in ONE command ──────────────
print("=" * 56)
print("Installing dependencies...")
PKGS = [
    "git+https://github.com/huggingface/diffusers.git",
    "transformers>=4.47.0", "accelerate>=0.28.0", "sentencepiece",
    "huggingface_hub>=0.23.0", "Pillow>=10.0", "numpy", "requests",
    "onnxruntime-gpu", "torchvision", "qwen-vl-utils",
    "bitsandbytes>=0.43.0",   # V9: required for 8-bit quantization
    "opencv-python-headless", "piexif",
]
r = subprocess.run(
    [sys.executable, "-m", "pip", "install", "-q", "--no-warn-conflicts"] + PKGS,
    capture_output=True, text=True)
print(f"  pip: {'OK' if r.returncode == 0 else 'WARN'}")
print("Done!\n")

import torch
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import requests as req

# ══════════════════════════════════════════════════
# PATHS
# ══════════════════════════════════════════════════
WORKING_DIR     = Path("/kaggle/working")
GENERATED_DIR   = WORKING_DIR / "generated"
APPROVED_DIR    = WORKING_DIR / "approved"
TRANSPARENT_DIR = WORKING_DIR / "transparent"
PROJECT_DIR     = WORKING_DIR / "project"
REPO2_DIR       = WORKING_DIR / "repo2"
REPO1_DIR       = WORKING_DIR / "repo1"
CHECKPOINT_DIR  = WORKING_DIR / "checkpoints"

for d in [GENERATED_DIR, APPROVED_DIR, TRANSPARENT_DIR, CHECKPOINT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ══════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════
GOOGLE_CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN", "")
GITHUB_TOKEN         = os.environ.get("GITHUB_TOKEN_REPO2", "")
GITHUB_REPO2         = os.environ.get("GITHUB_REPO2", "")
GITHUB_REPO1         = os.environ.get("GITHUB_REPO", "")
GITHUB_TOKEN_REPO1   = os.environ.get("GITHUB_TOKEN_REPO1", "")
START_INDEX          = int(float(os.environ.get("START_INDEX", "0").strip()))
END_INDEX            = int(float(os.environ.get("END_INDEX", "200").strip()))

SITE_URL       = "https://www.ultrapng.com"
SITE_NAME      = "UltraPNG"
WATERMARK_TEXT = "www.ultrapng.com"

# ══════════════════════════════════════════════════
# CATEGORY ENHANCERS (FLUX-style descriptive suffixes)
# ══════════════════════════════════════════════════
CATEGORY_ENHANCERS = {
    "indian_foods": ", steaming hot presentation, glistening sauce, appetizing food styling",
    "food_indian":  ", steaming hot presentation, glistening sauce, appetizing food styling",
    "world_foods":  ", restaurant quality plating, glistening sauce, steam rising",
    "food_world":   ", restaurant quality plating, glistening sauce, steam rising",
    "fruits":       ", natural skin texture with visible pores, fresh juice droplets on surface",
    "vegetables":   ", fresh harvest quality, natural surface texture and color",
    "flowers":      ", visible petal vein detail, rich natural color saturation",
    "jewellery":    ", gem facet reflections, mirror-polished gold metal finish",
    "vehicles":     ", automotive paint reflection, chrome detail highlights",
    "animals":      ", fur and feather strand detail, natural catchlight in eyes",
    "poultry":      ", feather strand detail, natural catchlight in eyes",
    "raw_meat":     ", fresh moist texture, glistening surface detail",
    "cool_drinks":  ", condensation droplets on glass, liquid transparency",
    "beverages":    ", condensation droplets on glass, liquid transparency",
    "footwear":     ", leather grain texture, fine stitching detail",
    "shoes":        ", leather grain texture, fine stitching detail",
    "indian_dress": ", fabric weave texture, embroidery thread detail",
    "clothing":     ", fabric weave texture, embroidery thread detail",
    "office_models": ", professional portrait lighting, sharp clothing detail",
}

def enhance_prompt(raw_prompt, category):
    cat = (category or "").lower()
    for key, extra in CATEGORY_ENHANCERS.items():
        if key in cat:
            return raw_prompt + extra
    return raw_prompt

# ══════════════════════════════════════════════════
# UTILITIES
# ══════════════════════════════════════════════════
def free_memory():
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()

def slugify(s, max_len=60):
    s = re.sub(r'[^a-z0-9]+', '-', str(s).lower()).strip('-')
    if len(s) > max_len:
        cut = s[:max_len]
        idx = cut.rfind('-')
        s   = cut[:idx] if idx > max_len // 2 else cut
    return s or 'untitled'

def preview_url(fid, size=800):
    return f"https://lh3.googleusercontent.com/d/{fid}=s{size}"

def download_url(fid):
    return f"https://drive.usercontent.google.com/download?id={fid}&export=download&authuser=0"

# ══════════════════════════════════════════════════
# UNIQUE TITLE PATTERNS — V9.0
# No duplicate title warnings from Google
# ══════════════════════════════════════════════════
_TITLE_PATTERNS = [
    "{subject} Transparent PNG - Free HD Download | UltraPNG",
    "Download {subject} PNG HD - No Background Free | UltraPNG",
    "Free {subject} PNG Transparent Background HD | UltraPNG",
    "{subject} PNG Image Free Download - Transparent HD | UltraPNG",
    "High Quality {subject} Transparent PNG Free | UltraPNG",
    "{subject} PNG Cut Out HD - Transparent Free Download | UltraPNG",
    "Free Download {subject} PNG HD Transparent Background | UltraPNG",
    "{subject} No Background PNG - Free HD Image | UltraPNG",
]

def _make_unique_title(subject, slug):
    """Deterministic title selection — same image always gets same title."""
    idx = abs(hash(slug)) % len(_TITLE_PATTERNS)
    return _TITLE_PATTERNS[idx].replace("{subject}", subject)

# ══════════════════════════════════════════════════
# CHECKPOINT
# ══════════════════════════════════════════════════
def save_checkpoint(name, data):
    path = CHECKPOINT_DIR / f"{name}.json"
    tmp  = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, str(path))
    log(f"  Checkpoint: {name} ({len(data)} items)")

def load_checkpoint(name):
    path = CHECKPOINT_DIR / f"{name}.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        log(f"  Loaded checkpoint: {name} ({len(data)} items)")
        return data
    return None

# ══════════════════════════════════════════════════
# GOOGLE DRIVE API
# ══════════════════════════════════════════════════
_token_cache = {"value": None, "expires": 0}

def get_drive_token():
    if _token_cache["value"] and time.time() < _token_cache["expires"]:
        return _token_cache["value"]
    r = req.post("https://oauth2.googleapis.com/token", data={
        "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": GOOGLE_REFRESH_TOKEN, "grant_type": "refresh_token",
    }, timeout=30)
    d = r.json()
    if "access_token" not in d:
        raise Exception(f"Token error: {d}")
    _token_cache.update({"value": d["access_token"], "expires": time.time() + 3200})
    return _token_cache["value"]

def drive_folder(token, name, parent=None):
    h = {"Authorization": f"Bearer {token}"}
    q = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent:
        q += f" and '{parent}' in parents"
    r = req.get("https://www.googleapis.com/drive/v3/files",
                headers=h, params={"q": q, "fields": "files(id)"}, timeout=30)
    files = r.json().get("files", [])
    if files:
        return files[0]["id"]
    meta = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent:
        meta["parents"] = [parent]
    return req.post("https://www.googleapis.com/drive/v3/files",
        headers={**h, "Content-Type": "application/json"}, json=meta, timeout=30).json()["id"]

def drive_upload(token, folder_id, name, data, mime="image/png", retries=3):
    for attempt in range(1, retries + 1):
        try:
            h = {"Authorization": f"Bearer {token}"}
            metadata = json.dumps({"name": name, "parents": [folder_id]})
            b = "----UltraPNGPipe"
            body = (f"--{b}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
                    f"{metadata}\r\n--{b}\r\nContent-Type: {mime}\r\n\r\n").encode() + \
                   data + f"\r\n--{b}--".encode()
            r = req.post(
                "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,name",
                headers={**h, "Content-Type": f'multipart/related; boundary="{b}"'},
                data=body, timeout=120)
            if r.ok:
                return r.json()
            raise Exception(f"HTTP {r.status_code}: {r.text[:150]}")
        except Exception as e:
            if attempt < retries:
                time.sleep(5 * attempt)
            else:
                raise

def drive_share(token, fid):
    try:
        req.post(f"https://www.googleapis.com/drive/v3/files/{fid}/permissions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"role": "reader", "type": "anyone"}, timeout=30)
    except Exception:
        pass

# ══════════════════════════════════════════════════
# WATERMARK + WEBP PREVIEW (cached watermark layer)
# ══════════════════════════════════════════════════
_wm_cache = {}

def _get_watermark_layer(w, h):
    key = (w, h)
    if key in _wm_cache:
        return _wm_cache[key]
    try:
        fnt = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 13)
    except Exception:
        fnt = ImageFont.load_default()
    wm = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d  = ImageDraw.Draw(wm)
    for ry in range(-h, h + 110, 110):
        for cx in range(-w, w + 110, 110):
            d.text((cx, ry), WATERMARK_TEXT, fill=(0, 0, 0, 42), font=fnt)
    wm = wm.rotate(-30, expand=False)
    _wm_cache[key] = wm
    return wm

def make_preview_webp(png_path):
    """Watermarked WebP preview. Returns (webp_bytes, w, h)."""
    with Image.open(png_path).convert("RGBA") as img:
        w, h = img.size
        if max(w, h) > 800:
            r   = 800 / max(w, h)
            img = img.resize((int(w * r), int(h * r)), Image.LANCZOS)
        w, h = img.size
        bg = Image.new("RGB", (w, h), (255, 255, 255))
        drw = ImageDraw.Draw(bg)
        for ry in range(0, h, 20):
            for cx in range(0, w, 20):
                if (ry // 20 + cx // 20) % 2 == 1:
                    drw.rectangle([cx, ry, cx + 20, ry + 20], fill=(232, 232, 232))
        bg.paste(img.convert("RGB"), mask=img.split()[3])
        bg_rgba = bg.convert("RGBA")
        bg_rgba.alpha_composite(_get_watermark_layer(w, h))
        bg = bg_rgba.convert("RGB")
        drw2 = ImageDraw.Draw(bg)
        drw2.rectangle([0, h - 36, w, h], fill=(13, 13, 20))
        try:
            fnt2 = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 15)
        except Exception:
            fnt2 = ImageFont.load_default()
        drw2.text((w // 2 - 72, h - 26), WATERMARK_TEXT, fill=(245, 166, 35), font=fnt2)
        buf = io.BytesIO()
        bg.save(buf, "WEBP", quality=82, method=4)
    return buf.getvalue(), w, h

# ══════════════════════════════════════════════════
# SKIP SET + PROMPTS
# ══════════════════════════════════════════════════
def load_skip_set_from_json():
    log("Building skip-set...")
    skip = set()
    if not REPO2_DIR.exists():
        try:
            url = f"https://x-access-token:{GITHUB_TOKEN}@github.com/{GITHUB_REPO2}.git"
            subprocess.run(["git", "clone", "--depth", "1", "--filter=blob:none",
                "--sparse", url, str(REPO2_DIR)], capture_output=True, check=True)
            subprocess.run(["git", "sparse-checkout", "init", "--cone"],
                cwd=str(REPO2_DIR), capture_output=True, check=True)
            subprocess.run(["git", "sparse-checkout", "set", "data"],
                cwd=str(REPO2_DIR), capture_output=True, check=True)
        except Exception:
            log("  Skip-set: REPO2 empty — starting fresh")
            return skip
    data_dir = REPO2_DIR / "data"
    if not data_dir.exists():
        return skip
    for jf in data_dir.glob("*.json"):
        if jf.name.startswith("_"):
            continue
        try:
            for e in json.loads(jf.read_text("utf-8")):
                fn = e.get("filename", "")
                if fn:
                    skip.add(fn)
        except Exception:
            pass
    log(f"  Skip-set: {len(skip)} filenames")
    return skip

def load_prompts():
    log("Loading prompts...")
    if GITHUB_REPO1 and not PROJECT_DIR.exists():
        result = subprocess.run(
            ["git", "clone", "--depth", "1", f"https://github.com/{GITHUB_REPO1}", str(PROJECT_DIR)],
            capture_output=True, text=True)
        if result.returncode != 0:
            log(f"  Clone failed: {result.stderr[:200]}")
    if PROJECT_DIR.exists():
        sys.path.insert(0, str(PROJECT_DIR))
        try:
            from prompts.prompt_engine import load_all_prompts
            prompts = load_all_prompts(str(PROJECT_DIR / "prompts" / "splits"))
            log(f"Loaded {len(prompts)} prompts")
            return prompts
        except Exception as e:
            log(f"Prompt error: {e}")
    log("FATAL: No prompts!")
    return []

# ══════════════════════════════════════════════════
# PHASE 1 — FLUX.2-Klein-4B Image Generation
# ══════════════════════════════════════════════════
def phase1_generate(batch, skip_set):
    ckpt = load_checkpoint("phase1_generated")
    if ckpt:
        return ckpt

    log("=" * 56)
    log(f"PHASE 1: FLUX.2-Klein-4B — {FLUX_HF_ID}")
    log("=" * 56)

    from diffusers import Flux2KleinPipeline

    # FLUX.2-Klein-4B requires Flux2KleinPipeline — NOT FluxPipeline.
    # FluxPipeline expects text_encoder_2, tokenizer_2, image_encoder,
    # feature_extractor which Klein does not have → ValueError.
    pipe = Flux2KleinPipeline.from_pretrained(
        FLUX_HF_ID,
        torch_dtype=torch.bfloat16,
    )
    pipe.enable_model_cpu_offload(gpu_id=0)
    pipe.set_progress_bar_config(disable=True)
    log(f"FLUX loaded | Batch: {len(batch)} | Skip: {len(skip_set)}\n")

    generated, skipped, t0 = [], 0, time.time()

    for i, item in enumerate(batch):
        fname = item["filename"]
        if fname in skip_set:
            skipped += 1
            if skipped <= 3 or skipped % 50 == 0:
                log(f"  SKIP [{i+1}/{len(batch)}] {fname}")
            continue
        try:
            out_dir = GENERATED_DIR / item["category"] / item.get("subcategory", "general")
            out_dir.mkdir(parents=True, exist_ok=True)
            out = out_dir / fname
            if out.exists():
                generated.append({"path": str(out), "item": item})
                continue

            gen    = torch.Generator("cpu").manual_seed(item["seed"])
            prompt = enhance_prompt(item["prompt"], item.get("category", ""))
            img = pipe(prompt=prompt, num_inference_steps=4, guidance_scale=1.0,
                       height=1024, width=1024, generator=gen).images[0]

            arr = np.array(img)
            if arr.std() < 5 or (arr < 250).sum() < int(arr.shape[0]*arr.shape[1]*0.003):
                log(f"  Retry (blank): {fname}")
                gen2 = torch.Generator("cpu").manual_seed(item["seed"] + 99)
                img  = pipe(prompt=prompt, num_inference_steps=4, guidance_scale=1.0,
                            height=1024, width=1024, generator=gen2).images[0]

            img.save(str(out), "PNG", compress_level=0)
            generated.append({"path": str(out), "item": item})

            done = len(generated)
            rate = done / max(time.time() - t0, 1)
            eta  = (len(batch) - i - 1) / max(rate, 0.01) / 60
            log(f"  [{i+1}/{len(batch)}] OK {fname} | ETA {eta:.0f}min")

        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            log(f"  OOM: {fname}")
        except Exception as e:
            log(f"  FAIL {fname}: {e}")

    del pipe
    free_memory()
    for c in HF_CACHE.iterdir():
        if c.is_dir() and ("flux" in c.name.lower() or "black-forest" in c.name.lower()):
            shutil.rmtree(str(c), ignore_errors=True)

    save_checkpoint("phase1_generated", generated)
    log(f"PHASE 1 DONE — Generated: {len(generated)} | Skipped: {skipped}\n")
    return generated


# ══════════════════════════════════════════════════
# PHASE 2 — Qwen V9.0: 7B 8-bit Filter + SEO
# ══════════════════════════════════════════════════
CATEGORY_GROUP_MAP = [
    (["animal","bird","insect","fish","seafood","poultry","chicken","hen","goat","cow",
      "buffalo","dog","cat","elephant","tiger","lion","deer","rabbit","horse","camel",
      "bear","monkey","snake","crab","prawn","shrimp","lobster","squid"], "animals"),
    (["food","dish","curry","rice","biryani","dosa","idli","vada","pizza","burger",
      "pasta","noodle","soup","fry","roast","kebab","tikka","masala","bakery","snack",
      "cake","bread","sweet","halwa","ladoo","barfi","dairy","egg","raw_meat",
      "cool_drink","beverage"], "food"),
    (["fruit","vegetable","herb","spice","nut","dry_fruit","ayurvedic","herbal"], "produce"),
    (["flower","plant","tree","nature","sky","celestial"], "nature"),
    (["tool","hardware","kitchen","vessel","pot","pan","utensil"], "tools"),
    (["jewel","necklace","ring","bangle","watch","bag","shoe","footwear","cloth",
      "dress","saree","clothing"], "fashion"),
    (["electronic","mobile","phone","laptop","computer","tablet","accessory"], "electronics"),
    (["clipart","icon","logo","frame","border","offer","effect","festival","pooja",
      "music","stationery","office","sport","vehicle","car","bike","medical","furniture"], "design"),
]

def _get_category_group(category):
    cat = category.lower()
    for keywords, group in CATEGORY_GROUP_MAP:
        if any(kw in cat for kw in keywords):
            return group
    return "general"

GROUP_CHECK_RULES = {
    "animals": """ULTRA-STRICT ANIMAL CHECK — COUNT EVERY BODY PART:
✗ WRONG LEG COUNT (Dogs=4, Birds=2, Insects=6, Fish=0 legs + fins) → DELETE
✗ EXTRA/MISSING HEADS (must be exactly 1) → DELETE
✗ FUSED BODY PARTS (legs merged into blob, wings melted) → DELETE
✗ MELTED/DISTORTED body (shapeless wax-like mass) → DELETE
✗ EXTRA LIMBS from wrong places → DELETE
✗ FLOATING disconnected body parts → DELETE
✗ WRONG EYE/EAR COUNT for species → DELETE
✗ Face is unrecognizable blob → DELETE
✗ Different species than expected → DELETE
✗ Dead/cooked when live expected → DELETE
KEEP if: correct anatomy even in cartoon/illustrated style""",

    "food": """STRICT FOOD CHECK:
✗ Rotten/moldy/decomposed look → DELETE
✗ Completely unrecognizable as food → DELETE
✗ Wrong food type entirely → DELETE
✗ Unnatural impossible colors → DELETE
✗ Shapeless blob with no food texture → DELETE
✗ Plate/bowl with impossible melted shape → DELETE
✗ Plastic/rubber/artificial texture → DELETE""",

    "produce": """STRICT PRODUCE CHECK:
✗ Severely rotten/decomposed → DELETE
✗ Impossible melted/blobby shape → DELETE
✗ Wrong produce entirely → DELETE
✗ Fused hybrid of different items → DELETE""",

    "nature": """STRICT NATURE CHECK:
✗ Petals are shapeless blobs → DELETE
✗ Wrong plant type → DELETE
✗ Fused melted mass → DELETE""",

    "tools": """STRICT TOOLS CHECK:
✗ Tool is unrecognizable blob → DELETE
✗ Wrong tool entirely → DELETE
✗ Impossible melted geometry → DELETE""",

    "fashion": """STRICT FASHION CHECK:
✗ Shapeless blob garment → DELETE
✗ Wrong item entirely → DELETE
✗ Rubber/plastic blob texture → DELETE""",

    "electronics": """STRICT ELECTRONICS CHECK:
✗ Device is blob with no features → DELETE
✗ Wrong device entirely → DELETE
✗ Melted/fused body → DELETE""",

    "design": """STRICT DESIGN CHECK:
✗ Blank/empty image → DELETE
✗ Pure noise → DELETE
✗ Wrong category entirely → DELETE""",

    "general": """STRICT CHECK:
✗ Blank/empty → DELETE
✗ Pure noise → DELETE
✗ Subject absent → DELETE
✗ Unrecognizable blob → DELETE""",
}


def _build_qwen_prompt(item, subject, category, slug_base):
    """
    V9.0 — Improved SEO prompt:
    - Structured 320-380 word description
    - LSI keywords embedded naturally
    - Google E-E-A-T compliant
    - Unique title via hash-based pattern
    """
    group = _get_category_group(category)
    rule  = GROUP_CHECK_RULES.get(group, GROUP_CHECK_RULES["general"])

    return f"""You are an ULTRA-STRICT quality inspector + SEO writer for UltraPNG.com (free transparent PNG library).

IMAGE INFO: prompt="{item.get('prompt','')}" | expected="{subject}" | category={category} | group={group}

══ STEP 1: SUBJECT MATCH ══
Does the image actually show "{subject}"? If different subject → subject_match:false → DELETE immediately.

══ STEP 2: QUALITY CHECK ══
{rule}

══ STEP 3: AI ARTIFACT CHECK (inspect carefully) ══
✗ EXTRA FINGERS on humans (must be 5 per hand) → DELETE
✗ GARBLED TEXT or unreadable letters visible → DELETE
✗ SEVERELY ASYMMETRIC features that should be symmetric → DELETE
✗ OBJECTS FLOATING without physical support → DELETE
✗ BLURRY or SMEARED patches while rest is sharp → DELETE
✗ IMPOSSIBLE PHYSICS (wrong shadows, floating liquids) → DELETE
✗ DUPLICATED elements (extra petals, double handles, clone artifacts) → DELETE

══ STEP 4: CONFIDENCE SCORE (0-10) ══
9-10 = Perfect commercial quality
7-8  = Good, minor acceptable flaws
5-6  = Borderline — DELETE
0-4  = Bad quality — DELETE
RULE: confidence below 7 → verdict must be DELETE

══ STEP 5: FINAL VERDICT ══
DELETE if ANY of these: subject_match=false OR quality defect found OR confidence < 7

══ STEP 6: SEO CONTENT (write ONLY if verdict=KEEP, else return empty strings) ══

DESCRIPTION RULES (CRITICAL — follow exactly):
- Write exactly 320-380 words total
- 100% unique natural human writing — no robotic repetition
- Google E-E-A-T compliant — authoritative, trustworthy tone
- Embed these LSI keywords naturally: transparent PNG, free download, HD quality, no background, digital asset, transparent background, high resolution

DESCRIPTION STRUCTURE:
Section 1 — About This Image (85-100 words):
Describe exactly what you visually see in this {subject} image. Include: visual appearance, colors, style, quality details, composition. Make it informative and unique per image.

Section 2 — Best Uses (65-75 words):
Describe 4-5 practical use cases: flex banner printing, social media posts, YouTube thumbnails, e-commerce listings, invitation cards, Canva projects, Photoshop composites. Write in natural sentences, not bullets.

Section 3 — Technical Details (50-60 words):
Explain PNG format benefits, transparent background advantage, HD resolution suitability, BiRefNet AI edge quality, file compatibility. Include keywords: transparent PNG, high resolution, clean edges naturally.

Section 4 — Design Ideas (55-65 words):
Give 3 creative project ideas specifically for this {subject} image. Mention Canva, Photoshop, CorelDRAW, PowerPoint compatibility naturally.

Section 5 — FAQ (2 questions, 45-55 words total):
Q1: Is this {subject} PNG completely free to download?
A1: Answer yes with 1-2 sentences about UltraPNG free policy.
Q2: Can I use this transparent PNG in Canva or Photoshop?
A2: Answer yes with 1-2 sentences about compatibility.

Return ONLY valid JSON — no markdown, no code fences, no extra text:
{{
  "subject_match": true/false,
  "shape_match": true/false,
  "confidence": 0-10,
  "verdict": "KEEP"/"DELETE",
  "reason": "specific defect description, or empty string if KEEP",
  "title": "auto-generated from pattern — leave as empty string, pipeline will set",
  "slug": "max 55 chars kebab-case: {slug_base}-[color-or-style]-png-hd",
  "meta_desc": "max 155 chars: unique, keyword-rich, action-oriented description for Google snippet",
  "h1": "descriptive: [color] [style] {subject} Transparent PNG HD Free Download",
  "tags": "comma-separated 18 tags: include subject name, colors, style, use cases, transparent, PNG, free, HD, UltraPNG, canva, download, no background",
  "description": "320-380 word description following the 5-section structure above — plain text, no markdown headers"
}}
CRITICAL: JSON only. No duplicate keys. confidence<7 means verdict must be DELETE."""


def phase2_qwen_filter_seo(generated):
    ckpt = load_checkpoint("phase2_posts")
    if ckpt:
        return ckpt

    log("=" * 56)
    log("PHASE 2: Qwen V9.0 — 7B 8-bit STRICT Filter + SEO")
    log("=" * 56)

    if not generated:
        return []

    from transformers import (
        Qwen2_5_VLForConditionalGeneration,
        AutoProcessor,
        BitsAndBytesConfig,
    )
    from qwen_vl_utils import process_vision_info

    # ── V9.0: 8-bit quantization — ~7GB VRAM, better quality ──
    bnb_config = BitsAndBytesConfig(
        load_in_8bit=True,
        llm_int8_threshold=6.0,
        llm_int8_has_fp16_weight=False,
    )

    processor = AutoProcessor.from_pretrained(
        QWEN_HF_ID, use_fast=True, cache_dir=str(HF_CACHE))
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        QWEN_HF_ID,
        quantization_config=bnb_config,
        device_map="auto",
        cache_dir=str(HF_CACHE),
    )
    model.eval()
    log(f"Qwen 7B 8-bit loaded! VRAM: ~7GB | Processing {len(generated)} images...\n")

    posts, deleted, used_slugs = [], 0, set()
    t0 = time.time()

    partial = load_checkpoint("phase2_posts_partial")
    resume_from = 0
    if partial:
        posts      = partial
        used_slugs = set(f"{p['category']}/{p['slug']}" for p in posts)
        resume_from = len(posts)
        log(f"  Resuming from {resume_from}")

    stats = {"wrong_subject": 0, "wrong_shape": 0, "low_confidence": 0,
             "deformed": 0, "parse_fail": 0}

    for i, item_data in enumerate(generated):
        if i < resume_from:
            continue

        item     = item_data["item"]
        category = item["category"]
        subject  = item.get("subject_name") or category.replace("-"," ").replace("_"," ").title()
        prompt   = item.get("prompt", f"a {subject}")
        slug_base = slugify(subject)
        path     = Path(item_data["path"])
        group    = _get_category_group(category)

        approved_path = APPROVED_DIR / path.relative_to(GENERATED_DIR)
        approved_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with Image.open(path).convert("RGB") as img_orig:
                iw, ih = img_orig.size
                if max(iw, ih) > 512:
                    r = 512 / max(iw, ih)
                    img_pil = img_orig.resize((int(iw*r), int(ih*r)), Image.LANCZOS).copy()
                else:
                    img_pil = img_orig.copy()

            messages = [{"role": "user", "content": [
                {"type": "image", "image": img_pil},
                {"type": "text",  "text": _build_qwen_prompt(item, subject, category, slug_base)},
            ]}]

            text = processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True)
            img_inputs, vid_inputs = process_vision_info(messages)
            inputs = processor(
                text=[text], images=img_inputs, videos=vid_inputs,
                padding=True, return_tensors="pt").to(model.device)

            with torch.no_grad():
                out_ids = model.generate(
                    **inputs,
                    max_new_tokens=1400,
                    do_sample=False,
                    pad_token_id=processor.tokenizer.eos_token_id,
                )

            trimmed = [out_ids[k][len(inputs.input_ids[k]):] for k in range(len(out_ids))]
            raw = processor.batch_decode(
                trimmed, skip_special_tokens=True,
                clean_up_tokenization_spaces=True)[0].strip()

            # 3-pass JSON parser
            ai, parse_ok = {}, False
            for attempt_fn in [
                lambda r: json.loads(r[r.find("{"):r.rfind("}")+1]),
                lambda r: json.loads(re.sub(r'[\x00-\x1f\x7f]', ' ',
                    r[r.find("{"):r.rfind("}")+1])),
                lambda r: json.loads(re.sub(r'(?<!\\)\n', '\\n',
                    re.sub(r'[\x00-\x08\x0b-\x1f\x7f]', ' ',
                        r[r.find("{"):r.rfind("}")+1]))),
            ]:
                try:
                    ai = attempt_fn(raw)
                    parse_ok = True
                    break
                except Exception:
                    continue

            if not parse_ok:
                raise ValueError(f"JSON parse failed. Raw[:200]: {raw[:200]}")

            def _bool(v):
                if isinstance(v, str):
                    return v.lower() not in ("false","no","0")
                return bool(v)

            subject_match = _bool(ai.get("subject_match", True))
            shape_match   = _bool(ai.get("shape_match", True))
            confidence    = int(ai.get("confidence", 0))
            verdict       = ai.get("verdict", "DELETE").strip().upper()
            reason        = ai.get("reason", "")

            delete_reason = None
            if not subject_match:
                delete_reason = f"Wrong subject (expected={subject})"
                stats["wrong_subject"] += 1
            elif group == "animals" and not shape_match:
                delete_reason = f"Wrong body shape for {subject}"
                stats["wrong_shape"] += 1
            elif confidence < 7:
                delete_reason = f"Low confidence={confidence}"
                stats["low_confidence"] += 1
            elif verdict == "DELETE":
                delete_reason = reason or "Quality failed"
                stats["deformed"] += 1

            if delete_reason:
                log(f"  DELETE [{i+1}/{len(generated)}] {path.name} | {delete_reason}")
                path.unlink(missing_ok=True)
                deleted += 1
                continue

            shutil.copy2(str(path), str(approved_path))

            # Slug deduplication
            raw_slug = ai.get("slug") or f"{slug_base}-png-hd"
            slug = slugify(raw_slug)
            base_slug, sfx = slug, 1
            while f"{category}/{slug}" in used_slugs:
                slug = f"{base_slug}-{sfx}"; sfx += 1
            used_slugs.add(f"{category}/{slug}")

            # Description — fallback if too short
            desc = ai.get("description", "")
            if not desc or len(desc.split()) < 100:
                desc = _fallback_desc(subject, category, prompt)

            # V9.0: Unique title via deterministic hash pattern
            unique_title = _make_unique_title(subject, slug)

            post = {
                "category":     category,
                "subcategory":  item.get("subcategory", "general"),
                "subject_name": subject,
                "filename":     item["filename"],
                "original_prompt": prompt,
                "slug":         slug,
                "title":        unique_title,
                "h1":           ai.get("h1") or f"{subject} Transparent PNG HD Free Download",
                "meta_desc":    (ai.get("meta_desc") or
                    f"Download {subject} transparent PNG free HD. No background, perfect for Canva, Photoshop. UltraPNG.com")[:155],
                "alt_text":     (ai.get("h1") or f"{subject} PNG") +
                    " Transparent Background Free Download UltraPNG",
                "tags":         ai.get("tags") or
                    f"{subject},png,transparent,free download,hd,no background,ultrapng,canva",
                "description":  desc,
                "word_count":   len(desc.split()),
                "ai_generated": True,
                "qwen_confidence": confidence,
                "qwen_group":   group,
                "approved_path": str(approved_path),
                "png_file_id":  "", "webp_file_id": "",
                "download_url": "", "preview_url": "",
                "preview_url_small": "", "webp_preview_url": "",
                "preview_w": 800, "preview_h": 800,
                "date_added": datetime.now().strftime("%Y-%m-%d"),
            }
            posts.append(post)

            rate = max((i+1-resume_from), 1) / (time.time()-t0)
            eta  = (len(generated)-i-1) / max(rate, 0.01) / 60
            log(f"  KEEP [{i+1}/{len(generated)}] {slug} (conf={confidence}) | ETA {eta:.0f}min")

        except Exception as e:
            log(f"  FAIL→DELETE [{i+1}] {item.get('filename','?')}: {e}")
            stats["parse_fail"] += 1
            path.unlink(missing_ok=True)
            deleted += 1

        if (i+1) % 10 == 0:
            gc.collect()
            torch.cuda.empty_cache()
            save_checkpoint("phase2_posts_partial", posts)

    del model, processor
    free_memory()
    # Clean Qwen cache
    for c in HF_CACHE.iterdir():
        if c.is_dir() and "qwen" in c.name.lower():
            shutil.rmtree(str(c), ignore_errors=True)
    if GENERATED_DIR.exists():
        shutil.rmtree(str(GENERATED_DIR), ignore_errors=True)
        GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    save_checkpoint("phase2_posts", posts)
    log(f"PHASE 2 DONE — Kept: {len(posts)} | Deleted: {deleted}")
    log(f"  Stats: {stats}\n")
    return posts


def _fallback_desc(subject, category, prompt=""):
    """Fallback description when Qwen output is too short."""
    return (
        f"This {subject} PNG image is available as a free high-resolution transparent "
        f"background download at UltraPNG.com. The image features clean, pixel-perfect "
        f"edges processed by BiRefNet AI for professional quality results.\n\n"
        f"This transparent PNG is ideal for flex banner printing, social media posts, "
        f"YouTube thumbnails, e-commerce product listings, invitation card designs, "
        f"and digital advertising. Compatible with Canva, Photoshop, CorelDRAW, Figma, "
        f"and PowerPoint.\n\n"
        f"The HD resolution ensures this {subject} image remains sharp across all uses "
        f"from small social media icons to large format flex printing. The transparent "
        f"background (alpha channel) allows seamless placement on any color or design.\n\n"
        f"Creative uses include festival poster designs, shop banner layouts, "
        f"Instagram story templates, WhatsApp sticker packs, and product catalog pages. "
        f"The clean cut-out quality makes it suitable for professional commercial projects.\n\n"
        f"Is this {subject} PNG free? Yes, completely free with no signup required and "
        f"no watermark on the downloaded file. Can I use this in Canva? Yes, upload via "
        f"My Files in Canva and drag directly onto your canvas."
    )


# ══════════════════════════════════════════════════
# PHASE 3 — BiRefNet Background Removal (1024px FP16)
# ══════════════════════════════════════════════════
def phase3_bg_remove(posts):
    ckpt = load_checkpoint("phase3_transparent")
    if ckpt:
        return ckpt

    log("=" * 56)
    log("PHASE 3: BiRefNet_HR 1024px FP16 — BG Removal")
    log("=" * 56)

    if not posts:
        return []

    from torchvision import transforms
    from transformers import AutoModelForImageSegmentation

    rmbg = AutoModelForImageSegmentation.from_pretrained(
        RMBG_HF_ID, trust_remote_code=True, cache_dir=str(HF_CACHE))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch.set_float32_matmul_precision("high")
    rmbg = rmbg.to(device).eval().half()
    log(f"  BiRefNet on {device.upper()} | FP16 | 1024px\n")

    tfm = transforms.Compose([
        transforms.Resize((1024, 1024)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    def remove_bg(pil_img):
        ow, oh = pil_img.size
        inp = tfm(pil_img.convert("RGB")).unsqueeze(0).to(device).half()
        with torch.no_grad():
            pred = rmbg(inp)[-1].sigmoid().cpu()[0].squeeze()
        mask   = transforms.ToPILImage()(pred).resize((ow, oh), Image.LANCZOS)
        result = pil_img.convert("RGBA")
        result.putalpha(mask)
        return result

    result_posts, t0 = [], time.time()
    for i, post in enumerate(posts):
        path = Path(post["approved_path"])
        try:
            out = TRANSPARENT_DIR / path.relative_to(APPROVED_DIR)
            out.parent.mkdir(parents=True, exist_ok=True)
            if out.exists():
                result_posts.append({**post, "transparent_path": str(out)})
                continue
            img    = Image.open(str(path)).convert("RGB")
            result = remove_bg(img)
            result.save(str(out), "PNG", compress_level=0)
            result_posts.append({**post, "transparent_path": str(out)})
            if (i+1) % 20 == 0:
                log(f"  BG: {i+1}/{len(posts)} | {(i+1)/(time.time()-t0):.2f}/s")
        except Exception as e:
            log(f"  RMBG FAIL {path.name}: {e}")

    del rmbg, tfm
    free_memory()
    for c in HF_CACHE.iterdir():
        if c.is_dir() and any(k in c.name.lower() for k in ["rmbg","briaai","birefnet"]):
            shutil.rmtree(str(c), ignore_errors=True)
    if APPROVED_DIR.exists():
        shutil.rmtree(str(APPROVED_DIR), ignore_errors=True)
        APPROVED_DIR.mkdir(parents=True, exist_ok=True)

    save_checkpoint("phase3_transparent", result_posts)
    log(f"PHASE 3 DONE — {len(result_posts)} transparent PNGs\n")
    return result_posts


# ══════════════════════════════════════════════════
# PHASE 4 — Drive Upload (parallel, PNG+WebP only)
# ══════════════════════════════════════════════════
def phase4_upload(posts):
    ckpt = load_checkpoint("phase4_uploaded")
    if ckpt:
        return ckpt

    log("=" * 56)
    log("PHASE 4: Drive Upload — PNG + WebP (parallel)")
    log("=" * 56)

    if not posts:
        return []

    token    = get_drive_token()
    fcache   = {}
    png_root = drive_folder(token, "png_library_images")
    prv_root = drive_folder(token, "png_library_previews")
    log(f"Uploading {len(posts)} images...\n")

    # Pre-build folder IDs (sequential — Drive API rate limit safe)
    for post in posts:
        key = f"{post['category']}/{post.get('subcategory','general')}"
        if key not in fcache:
            cp = drive_folder(token, post["category"], png_root)
            sp = drive_folder(token, post.get("subcategory","general"), cp)
            cr = drive_folder(token, post["category"], prv_root)
            sr = drive_folder(token, post.get("subcategory","general"), cr)
            fcache[key] = {"png": sp, "preview": sr}

    uploaded, t0 = [], time.time()

    def _upload_one(post):
        nonlocal token
        path    = Path(post["transparent_path"])
        key     = f"{post['category']}/{post.get('subcategory','general')}"
        folders = fcache[key]

        png_bytes = path.read_bytes()
        pr = drive_upload(token, folders["png"], path.name, png_bytes)
        drive_share(token, pr["id"])

        webp_bytes, pw, ph = make_preview_webp(path)
        wr = drive_upload(token, folders["preview"], path.stem + ".webp",
                          webp_bytes, "image/webp")
        drive_share(token, wr["id"])

        return {
            **post,
            "png_file_id":       pr["id"],
            "webp_file_id":      wr["id"],
            "download_url":      download_url(pr["id"]),
            "preview_url":       preview_url(wr["id"], 800),
            "preview_url_small": preview_url(wr["id"], 400),
            "webp_preview_url":  preview_url(wr["id"], 800),
            "preview_w": pw, "preview_h": ph,
            "date_added": datetime.now().strftime("%Y-%m-%d"),
        }

    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = {pool.submit(_upload_one, p): p for p in posts}
        for fut in as_completed(futs):
            try:
                uploaded.append(fut.result())
                if len(uploaded) % 10 == 0:
                    log(f"  Uploaded: {len(uploaded)}/{len(posts)} | "
                        f"{len(uploaded)/(time.time()-t0):.2f}/s")
            except Exception as e:
                log(f"  Upload FAIL: {e}")

    uploaded.sort(key=lambda x: x.get("filename",""))
    save_checkpoint("phase4_uploaded", uploaded)
    log(f"PHASE 4 DONE — {len(uploaded)} uploaded in {(time.time()-t0)/60:.0f}min")

    if TRANSPARENT_DIR.exists():
        shutil.rmtree(str(TRANSPARENT_DIR), ignore_errors=True)
        TRANSPARENT_DIR.mkdir(parents=True, exist_ok=True)
    return uploaded


# ══════════════════════════════════════════════════
# PHASE 5 — JSON Push to REPO2
# ══════════════════════════════════════════════════
def save_data_split(all_data, data_dir):
    data_dir.mkdir(parents=True, exist_ok=True)
    by_cat = {}
    for item in all_data:
        by_cat.setdefault(item["category"], []).append(item)
    for cat, items in by_cat.items():
        fname = data_dir / f"{cat}.json"
        tmp = str(fname) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        os.replace(tmp, str(fname))
    (data_dir / "_index.json").write_text(
        json.dumps({c: len(v) for c, v in by_cat.items()},
                   ensure_ascii=False, indent=2), "utf-8")
    log(f"  Saved {len(by_cat)} JSON files")

def load_all_data(data_dir):
    out = []
    if not data_dir.exists():
        return out
    for jf in data_dir.glob("*.json"):
        if jf.name.startswith("_"):
            continue
        try:
            entries = json.loads(jf.read_text("utf-8"))
            if isinstance(entries, list):
                out.extend(entries)
        except Exception:
            pass
    return out

def _sparse_clone(repo_url):
    shutil.rmtree(str(REPO2_DIR), ignore_errors=True)
    REPO2_DIR.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["git","clone","--depth","1","--filter=blob:none",
        "--sparse",repo_url,str(REPO2_DIR)], capture_output=True)
    if r.returncode != 0:
        shutil.rmtree(str(REPO2_DIR), ignore_errors=True)
        subprocess.run(["git","clone","--depth","1",repo_url,str(REPO2_DIR)],
            capture_output=True, check=True)
        return
    subprocess.run(["git","sparse-checkout","init","--cone"],
        cwd=str(REPO2_DIR), capture_output=True)
    subprocess.run(["git","sparse-checkout","set","data"],
        cwd=str(REPO2_DIR), capture_output=True)

def phase5_build_push(new_posts):
    log("=" * 56)
    log("PHASE 5: JSON Push to REPO2/data/")
    log("=" * 56)

    if not GITHUB_TOKEN or not GITHUB_REPO2:
        log("  No REPO2 config — skipping"); return
    if not new_posts:
        log("  No new posts"); return

    repo_url = f"https://x-access-token:{GITHUB_TOKEN}@github.com/{GITHUB_REPO2}.git"

    if REPO2_DIR.exists() and (REPO2_DIR / ".git").exists():
        try:
            subprocess.run(["git","pull","--rebase","--autostash"],
                cwd=str(REPO2_DIR), capture_output=True, check=True)
            subprocess.run(["git","remote","set-url","origin",repo_url],
                cwd=str(REPO2_DIR), capture_output=True)
        except Exception:
            shutil.rmtree(str(REPO2_DIR), ignore_errors=True)
            _sparse_clone(repo_url)
    else:
        _sparse_clone(repo_url)

    data_dir = REPO2_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    all_data = load_all_data(data_dir)
    existing = set(f"{d['category']}/{d['slug']}" for d in all_data)
    added = 0
    for post in new_posts:
        key = f"{post['category']}/{post['slug']}"
        if key not in existing:
            all_data.append(post)
            existing.add(key)
            added += 1
    log(f"  +{added} new | Total: {len(all_data)}")
    save_data_split(all_data, data_dir)

    orig = os.getcwd()
    try:
        os.chdir(str(REPO2_DIR))
        subprocess.run(["git","config","user.name","github-actions[bot]"],
            capture_output=True)
        subprocess.run(["git","config","user.email",
            "github-actions[bot]@users.noreply.github.com"], capture_output=True)
        subprocess.run(["git","add","data/"], check=True, capture_output=True)
        if subprocess.run(["git","diff","--staged","--quiet"],
                capture_output=True).returncode != 0:
            msg = (f"data: +{added} ({len(all_data)} total) "
                   f"[{datetime.now().strftime('%Y-%m-%d')}]")
            subprocess.run(["git","commit","-m",msg], check=True, capture_output=True)
            p = subprocess.run(["git","push"], capture_output=True, text=True)
            log(f"  Push {'OK' if p.returncode==0 else 'FAILED'}: +{added}")
        else:
            log("  Nothing to commit")
    except subprocess.CalledProcessError as e:
        log(f"  Git error: {e}")
    finally:
        os.chdir(orig)


# ══════════════════════════════════════════════════
# PHASE 6 — Logs to REPO1
# ══════════════════════════════════════════════════
def phase6_save_logs(stats):
    log("=" * 56)
    log("PHASE 6: Save logs")

    token = GITHUB_TOKEN_REPO1 or GITHUB_TOKEN
    if not token or not GITHUB_REPO1:
        log("  No REPO1 — skipping"); return

    repo_url = f"https://x-access-token:{token}@github.com/{GITHUB_REPO1}.git"
    try:
        if not REPO1_DIR.exists():
            subprocess.run(["git","clone","--depth","1",repo_url,str(REPO1_DIR)],
                capture_output=True, check=True)
        else:
            subprocess.run(["git","pull","--rebase","--autostash"],
                cwd=str(REPO1_DIR), capture_output=True)
            subprocess.run(["git","remote","set-url","origin",repo_url],
                cwd=str(REPO1_DIR), capture_output=True)

        logs_dir = REPO1_DIR / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now().strftime("%Y-%m-%d_%H-%M")

        summary = (
            f"ULTRAPNG V9.0 — RUN REPORT\n{'='*60}\n"
            f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"Batch: {START_INDEX}->{END_INDEX}\n"
            + "".join(f"{k}: {v}\n" for k, v in stats.items())
            + f"{'='*60}\n\nFULL LOG\n{'='*60}\n"
        )
        full_log = summary + "\n".join(_LOG_LINES)
        (logs_dir / f"{now}.log").write_text(full_log, "utf-8")
        (logs_dir / "latest.log").write_text(full_log, "utf-8")

        # Keep only last 30 logs
        for old in sorted(logs_dir.glob("????-??-??_??-??.log"))[:-30]:
            old.unlink()

        orig = os.getcwd()
        try:
            os.chdir(str(REPO1_DIR))
            subprocess.run(["git","config","user.name","github-actions[bot]"],
                capture_output=True)
            subprocess.run(["git","config","user.email",
                "github-actions[bot]@users.noreply.github.com"], capture_output=True)
            subprocess.run(["git","add","logs/"], check=True, capture_output=True)
            if subprocess.run(["git","diff","--staged","--quiet"],
                    capture_output=True).returncode != 0:
                msg = (f"[logs] {now} | gen={stats.get('generated',0)} "
                       f"posts={stats.get('posts',0)}")
                subprocess.run(["git","commit","-m",msg], check=True, capture_output=True)
                subprocess.run(["git","push"], capture_output=True)
                log("  Logs pushed")
        finally:
            os.chdir(orig)
    except Exception as e:
        log(f"  Log error: {e}")


# ══════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════
def main():
    t0    = time.time()
    stats = {
        "status": "running", "generated": 0, "deleted": 0,
        "approved": 0, "transparent": 0, "uploaded": 0,
        "posts": 0, "duration": "?",
    }

    print("╔══════════════════════════════════════════════════════╗")
    print("║  UltraPNG V9.0 — FLUX → Qwen7B → RMBG → Drive → Git║")
    print("╚══════════════════════════════════════════════════════╝")
    print(f"  Batch: {START_INDEX} → {END_INDEX} ({END_INDEX-START_INDEX} prompts)")
    print(f"  FLUX: {FLUX_HF_ID}")
    print(f"  Qwen: {QWEN_HF_ID} [8-bit quantized ~7GB VRAM]")
    print(f"  RMBG: {RMBG_HF_ID} (1024px FP16)")
    if torch.cuda.is_available():
        p = torch.cuda.get_device_properties(0)
        print(f"  GPU: {p.name} | {p.total_memory/1e9:.0f}GB VRAM")
    print()

    try:
        prompts = load_prompts()
        if not prompts:
            raise Exception("No prompts loaded!")

        batch = prompts[START_INDEX:END_INDEX]
        log(f"Batch: {len(batch)} prompts\n")
        skip_set = load_skip_set_from_json()

        # ── Phase 1: Generate ──
        generated = phase1_generate(batch, skip_set)
        stats["generated"] = len(generated)
        if not generated:
            log("No images generated.")
            return

        # ── Phase 2: Qwen Filter + SEO ──
        posts = phase2_qwen_filter_seo(generated)
        stats["approved"] = len(posts)
        stats["deleted"]  = len(generated) - len(posts)
        if not posts:
            log("All images deleted by Qwen quality filter.")
            return

        # ── Phase 3: Background Removal ──
        transparent = phase3_bg_remove(posts)
        stats["transparent"] = len(transparent)
        if not transparent:
            log("Background removal failed for all images.")
            return

        # ── Phase 4: Upload to Drive ──
        uploaded = phase4_upload(transparent)
        stats["uploaded"] = len(uploaded)
        if not uploaded:
            log("Drive upload failed.")
            return

        # ── Phase 5: Push JSON to REPO2 ──
        phase5_build_push(uploaded)
        stats["posts"] = len(uploaded)

        # Cleanup checkpoints
        for ck in CHECKPOINT_DIR.glob("*.json"):
            ck.unlink()

        hrs = (time.time()-t0) / 3600
        stats["duration"] = f"{hrs:.1f}h"
        stats["status"]   = "SUCCESS"

        print(f"\n{'='*56}")
        print(f"  V9.0 DONE in {hrs:.1f}h")
        print(f"  Generated:{len(generated)} | Deleted:{stats['deleted']} | "
              f"Approved:{len(posts)} | Uploaded:{len(uploaded)}")
        print(f"{'='*56}")

    except Exception as e:
        stats["duration"] = f"{(time.time()-t0)/3600:.1f}h"
        stats["status"]   = f"FAILED: {str(e)[:80]}"
        log(f"FATAL: {e}")
        raise
    finally:
        phase6_save_logs(stats)


if __name__ == "__main__":
    main()
