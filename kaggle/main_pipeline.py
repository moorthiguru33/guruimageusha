"""
╔══════════════════════════════════════════════════════════════╗
║   UltraPNG.com — PNG Library Pipeline V5.5                  ║
║   WORLD BEST ARCHITECTURE                                   ║
╠══════════════════════════════════════════════════════════════╣
║  PHASE 1 → FLUX.2-Klein-4B   Generate 1024x1024 images     ║
║  PHASE 2 → Qwen2.5-VL-3B    Filter + SEO (ONE PASS)        ║
║            Detects two-headed / deformed / fused animals    ║
║            Keeps group photos safely                        ║
║            Safe for Tools, Flowers, Food, Clipart           ║
║            Generates full SEO content same call             ║
║            DELETE Qwen → Free VRAM                          ║
║  PHASE 3 → RMBG-2.0 ONNX    Background removal (GPU)       ║
║  PHASE 4 → Google Drive      Upload PNG + JPG + WebP        ║
║  PHASE 5 → HTML Build + Git Push → REPO2 Live              ║
║  PHASE 6 → Save Run Logs → REPO1 (visible on GitHub!)      ║
╠══════════════════════════════════════════════════════════════╣
║  WHY SINGLE QWEN PASS IS WORLD BEST:                        ║
║  CLIP cannot detect two-headed / fused animals (60% acc)    ║
║  CLIP deletes tools, flowers, clipart wrongly               ║
║  Qwen loads once → Filter + SEO → unload = 1x VRAM only    ║
║  Qwen accuracy: 95% (sees image like a human)               ║
╠══════════════════════════════════════════════════════════════╣
║  ALL V5.4 FIXES CARRIED:                                    ║
║  slugify fixed, checkpoint system, JSON split, WebP+EXIF,  ║
║  diagonal watermark, Drive retry, sitemap split,            ║
║  robots.txt, llms.txt, git pull, concurrency,               ║
║  sparse checkout, Telegram notifications, search tags       ║
╚══════════════════════════════════════════════════════════════╝

inject_creds.py prepends os.environ[] lines before this file.
"""

import os, sys, json, time, gc, re, io, shutil, base64, subprocess, math
from pathlib import Path
from datetime import datetime

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

# ══════════════════════════════════════════════════════════════
# GLOBAL LOG CAPTURE — saves all output to GitHub REPO1/logs/
# ══════════════════════════════════════════════════════════════
_LOG_LINES = []

class _TeeWriter:
    def __init__(self, original):
        self._orig = original
    def write(self, msg):
        self._orig.write(msg)
        if msg.strip():
            _LOG_LINES.append(msg.rstrip())
    def flush(self):
        self._orig.flush()
    def isatty(self):
        return False

sys.stdout = _TeeWriter(sys.__stdout__)

# ── Install deps ──────────────────────────────────────────────
print("=" * 56)
print("Installing dependencies...")
PKGS = [
    "diffusers>=0.33.0", "transformers>=4.47.0",
    "accelerate>=0.28.0", "sentencepiece",
    "Pillow>=10.0", "numpy", "requests",
    "onnxruntime-gpu", "torchvision",
    "qwen-vl-utils", "bitsandbytes",
    "opencv-python-headless", "piexif",
]
for pkg in PKGS:
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", pkg],
        capture_output=True, text=True)
    print(f"  {'OK  ' if r.returncode == 0 else 'WARN'} {pkg}")
print("Done!\n")

import torch
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import requests as req

# ══════════════════════════════════════════════════════════════
# PATHS
# ══════════════════════════════════════════════════════════════
MODELS_DIR      = Path("/kaggle/input/my-pipeline-models")
FLUX_DIR        = MODELS_DIR / "flux2-klein"
QWEN_DIR        = MODELS_DIR / "qwen-vision"
# Auto-find ONNX model file (supports model.onnx, BiRefNet.onnx, etc.)
def _find_onnx():
    search_dirs = [
        MODELS_DIR / "rembg" / "onnx",
        MODELS_DIR / "rembg",
    ]
    for d in search_dirs:
        if d.exists():
            hits = list(d.glob("*.onnx"))
            if hits:
                return hits[0]
    return MODELS_DIR / "rembg" / "onnx" / "model.onnx"  # fallback path for error msg
RMBG_ONNX = _find_onnx()

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

# ══════════════════════════════════════════════════════════════
# CONFIG — injected by inject_creds.py
# ══════════════════════════════════════════════════════════════
GOOGLE_CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN", "")
GITHUB_TOKEN         = os.environ.get("GITHUB_TOKEN_REPO2", "")
GITHUB_REPO2         = os.environ.get("GITHUB_REPO2", "")
GITHUB_REPO1         = os.environ.get("GITHUB_REPO", "")
GITHUB_TOKEN_REPO1   = os.environ.get("GITHUB_TOKEN_REPO1", "")
TELEGRAM_BOT_TOKEN   = ""
TELEGRAM_CHAT_ID     = ""
START_INDEX          = int(float(os.environ.get("START_INDEX", "0").strip()))
END_INDEX            = int(float(os.environ.get("END_INDEX", "200").strip()))

SITE_URL        = "https://www.ultrapng.com"
SITE_NAME       = "UltraPNG"
WATERMARK_TEXT  = "www.ultrapng.com"
ITEMS_PER_PAGE  = 24
SITEMAP_MAX_URL = 45000

# ══════════════════════════════════════════════════════════════
# UTILITIES
# ══════════════════════════════════════════════════════════════
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def free_memory():
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
    used = torch.cuda.memory_allocated(0) / 1e9 if torch.cuda.is_available() else 0
    log(f"  GPU used: {used:.1f}GB")

def slugify(s, max_len=60):
    s = re.sub(r'[^a-z0-9]+', '-', str(s).lower()).strip('-')
    if len(s) > max_len:
        cut = s[:max_len]
        idx = cut.rfind('-')
        s   = cut[:idx] if idx > max_len // 2 else cut
    return s or 'untitled'

def esc(s):
    return (str(s or '')
            .replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;').replace("'", "&#39;"))

def preview_url(fid, size=800):
    return f"https://lh3.googleusercontent.com/d/{fid}=s{size}"

def download_url(fid):
    return f"https://drive.usercontent.google.com/download?id={fid}&export=download&authuser=0"

def send_telegram(message, parse_mode="HTML"):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        r = req.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": parse_mode},
            timeout=15)
        if not r.ok:
            log(f"  Telegram warn: {r.status_code}")
    except Exception as e:
        log(f"  Telegram error (non-fatal): {e}")

# ══════════════════════════════════════════════════════════════
# CHECKPOINT SYSTEM
# ══════════════════════════════════════════════════════════════
def save_checkpoint(name, data):
    path = CHECKPOINT_DIR / f"{name}.json"
    tmp  = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, str(path))
    log(f"  Checkpoint saved: {name} ({len(data)} items)")

def load_checkpoint(name):
    path = CHECKPOINT_DIR / f"{name}.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        log(f"  Checkpoint loaded: {name} ({len(data)} items)")
        return data
    return None

# ══════════════════════════════════════════════════════════════
# GOOGLE DRIVE API
# ══════════════════════════════════════════════════════════════
_token_cache = {"value": None, "expires": 0}

def get_drive_token():
    if _token_cache["value"] and time.time() < _token_cache["expires"]:
        return _token_cache["value"]
    r = req.post("https://oauth2.googleapis.com/token", data={
        "client_id":     GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": GOOGLE_REFRESH_TOKEN,
        "grant_type":    "refresh_token",
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
    return req.post(
        "https://www.googleapis.com/drive/v3/files",
        headers={**h, "Content-Type": "application/json"},
        json=meta, timeout=30).json()["id"]

def drive_upload(token, folder_id, name, data, mime="image/png", retries=3):
    for attempt in range(1, retries + 1):
        try:
            h        = {"Authorization": f"Bearer {token}"}
            metadata = json.dumps({"name": name, "parents": [folder_id]})
            b        = "----UltraPNGPipe"
            body = (
                f"--{b}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{metadata}\r\n"
                f"--{b}\r\nContent-Type: {mime}\r\n\r\n"
            ).encode() + data + f"\r\n--{b}--".encode()
            r = req.post(
                "https://www.googleapis.com/upload/drive/v3/files"
                "?uploadType=multipart&fields=id,name",
                headers={**h, "Content-Type": f'multipart/related; boundary="{b}"'},
                data=body, timeout=120)
            if r.ok:
                return r.json()
            raise Exception(f"HTTP {r.status_code}: {r.text[:150]}")
        except Exception as e:
            if attempt < retries:
                log(f"  Upload retry {attempt}/{retries}: {e}")
                time.sleep(5 * attempt)
            else:
                raise

def drive_share(token, fid):
    try:
        req.post(
            f"https://www.googleapis.com/drive/v3/files/{fid}/permissions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"role": "reader", "type": "anyone"}, timeout=30)
    except Exception:
        pass

def make_previews(png_path):
    """Diagonal watermarked JPG + WebP previews with EXIF copyright."""
    import piexif

    with Image.open(png_path).convert("RGBA") as img_rgba:
        w, h = img_rgba.size
        if max(w, h) > 800:
            r        = 800 / max(w, h)
            img_rgba = img_rgba.resize((int(w * r), int(h * r)), Image.LANCZOS)
        w, h = img_rgba.size

        bg  = Image.new("RGB", (w, h), (255, 255, 255))
        drw = ImageDraw.Draw(bg)
        for ry in range(0, h, 20):
            for cx in range(0, w, 20):
                if (ry // 20 + cx // 20) % 2 == 1:
                    drw.rectangle([cx, ry, cx + 20, ry + 20], fill=(232, 232, 232))
        bg.paste(img_rgba.convert("RGB"), mask=img_rgba.split()[3])

        try:
            fnt = ImageFont.truetype(
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 13)
        except Exception:
            fnt = ImageFont.load_default()

        wm_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        wm_draw  = ImageDraw.Draw(wm_layer)
        for ry in range(-h, h + 110, 110):
            for cx in range(-w, w + 110, 110):
                wm_draw.text((cx, ry), WATERMARK_TEXT, fill=(0, 0, 0, 42), font=fnt)
        wm_rot  = wm_layer.rotate(-30, expand=False)
        bg_rgba = bg.convert("RGBA")
        bg_rgba.alpha_composite(wm_rot)
        bg = bg_rgba.convert("RGB")

        drw2 = ImageDraw.Draw(bg)
        drw2.rectangle([0, h - 36, w, h], fill=(13, 13, 20))
        try:
            fnt2 = ImageFont.truetype(
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 15)
        except Exception:
            fnt2 = fnt
        drw2.text((w // 2 - 72, h - 26), WATERMARK_TEXT, fill=(245, 166, 35), font=fnt2)

        exif_bytes = piexif.dump({
            "0th": {
                piexif.ImageIFD.Copyright: WATERMARK_TEXT.encode(),
                piexif.ImageIFD.Artist:    SITE_NAME.encode(),
                piexif.ImageIFD.Software:  b"UltraPNG Pipeline V5.5",
            }
        })

        jpg_buf = io.BytesIO()
        bg.save(jpg_buf, "JPEG", quality=85, optimize=True, exif=exif_bytes)

        webp_buf = io.BytesIO()
        bg.save(webp_buf, "WEBP", quality=82, method=4)

    return jpg_buf.getvalue(), webp_buf.getvalue(), w, h

# ══════════════════════════════════════════════════════════════
# SKIP SET — from REPO2 JSON (fast, no Drive scan)
# ══════════════════════════════════════════════════════════════
def load_skip_set_from_json():
    log("Building skip-set from REPO2 JSON files...")
    skip_set = set()

    if not REPO2_DIR.exists():
        try:
            repo_url = f"https://x-access-token:{GITHUB_TOKEN}@github.com/{GITHUB_REPO2}.git"
            subprocess.run(
                ["git", "clone", "--depth", "1", "--filter=blob:none",
                 "--sparse", repo_url, str(REPO2_DIR)],
                capture_output=True, check=True)
            subprocess.run(
                ["git", "sparse-checkout", "init", "--cone"],
                cwd=str(REPO2_DIR), capture_output=True, check=True)
            subprocess.run(
                ["git", "sparse-checkout", "set", "data"],
                cwd=str(REPO2_DIR), capture_output=True, check=True)
        except Exception as e:
            log(f"  Skip-set: REPO2 not set or empty — starting fresh (no duplicates check)")
            return skip_set

    data_dir = REPO2_DIR / "data"
    if not data_dir.exists():
        log("  No data dir — starting fresh")
        return skip_set

    for jf in data_dir.glob("*.json"):
        if jf.name.startswith("_"):
            continue
        try:
            entries = json.loads(jf.read_text("utf-8"))
            for e in entries:
                fn = e.get("filename", "")
                if fn:
                    skip_set.add(fn)
        except Exception:
            pass

    log(f"  Skip-set: {len(skip_set)} already-done filenames")
    return skip_set

def load_prompts():
    log("Loading prompts...")
    if GITHUB_REPO1 and not PROJECT_DIR.exists():
        os.system(
            f"git clone --depth 1 https://github.com/{GITHUB_REPO1} {PROJECT_DIR} 2>/dev/null")
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

# ══════════════════════════════════════════════════════════════
# PHASE 1 — FLUX.2-Klein-4B  Image Generation
# ══════════════════════════════════════════════════════════════
def phase1_generate(batch, skip_set):
    ckpt = load_checkpoint("phase1_generated")
    if ckpt:
        return ckpt

    log("=" * 56)
    log("PHASE 1: FLUX.2-Klein-4B — Image Generation")
    log("=" * 56)

    # Flux2KleinPipeline was added in diffusers 0.33+
    # Fallback to FluxPipeline if older version installed
    try:
        from diffusers import Flux2KleinPipeline as _FluxCls
        log("Loading FLUX.2-Klein via Flux2KleinPipeline...")
    except ImportError:
        from diffusers import FluxPipeline as _FluxCls
        log("Loading FLUX.2-Klein via FluxPipeline (diffusers fallback)...")

    log("Loading FLUX.2 (instant from dataset)...")

    # ── Smart loader: works for BOTH diffusers layout AND single .safetensors ──
    _loaded = False
    if FLUX_DIR.is_dir():
        _ckpt_files     = sorted(FLUX_DIR.glob("*.safetensors"))
        _has_components = (FLUX_DIR / "transformer").is_dir()

        if _has_components:
            # Full diffusers layout: transformer/, vae/, text_encoder/, scheduler/
            log("  Mode: from_pretrained (full diffusers layout)")
            pipe = _FluxCls.from_pretrained(str(FLUX_DIR), torch_dtype=torch.bfloat16)
            _loaded = True
        elif _ckpt_files:
            # Single consolidated .safetensors (e.g. flux-2-klein-4b.safetensors)
            log(f"  Mode: from_single_file ({_ckpt_files[0].name})")
            pipe = _FluxCls.from_single_file(str(_ckpt_files[0]), torch_dtype=torch.bfloat16)
            _loaded = True
        else:
            log(f"  ⚠ FLUX_DIR exists but contains no .safetensors: {FLUX_DIR}")
    else:
        log(f"  ⚠ FLUX_DIR not found: {FLUX_DIR}")

    if not _loaded:
        _contents = (sorted(p.name for p in FLUX_DIR.iterdir())
                     if FLUX_DIR.exists() else "DIRECTORY MISSING")
        raise FileNotFoundError(
            f"FLUX model not found at: {FLUX_DIR}\n"
            f"  Contents: {_contents}\n"
            f"  Fix 1: Attach dataset 'my-pipeline-models' to this Kaggle kernel via UI.\n"
            f"  Fix 2: Ensure flux2-klein/ contains a .safetensors file or full diffusers structure."
        )

    pipe.enable_model_cpu_offload(gpu_id=0)
    pipe.set_progress_bar_config(disable=True)
    log(f"FLUX.2 loaded | Batch: {len(batch)} | Skip: {len(skip_set)}\n")

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

            gen = torch.Generator("cpu").manual_seed(item["seed"])
            img = pipe(
                prompt=item["prompt"],
                num_inference_steps=4,
                guidance_scale=1.0,
                height=1024, width=1024,
                generator=gen,
            ).images[0]

            # Blank image check (0.3% of pixels)
            arr    = np.array(img)
            n_px   = arr.shape[0] * arr.shape[1]
            thresh = int(n_px * 0.003)
            if arr.std() < 5 or (arr < 250).sum() < thresh:
                log(f"  Retry (blank): {fname}")
                gen2 = torch.Generator("cpu").manual_seed(item["seed"] + 99)
                img  = pipe(
                    prompt=item["prompt"],
                    num_inference_steps=4,
                    guidance_scale=1.0,
                    height=1024, width=1024,
                    generator=gen2,
                ).images[0]

            img.save(str(out), "PNG", compress_level=0)
            generated.append({"path": str(out), "item": item})

            done = len(generated)
            rate = done / (time.time() - t0)
            eta  = (len(batch) - i - 1) / rate / 60 if rate > 0 else 0
            log(f"  [{i+1}/{len(batch)}] OK {fname} | {item['category']} | ETA {eta:.0f}min")

        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            log(f"  OOM: {fname}")
        except Exception as e:
            log(f"  FAIL {fname}: {e}")

    log("\n  Deleting FLUX.2 -> freeing ~8GB VRAM...")
    del pipe
    free_memory()

    save_checkpoint("phase1_generated", generated)
    log(f"PHASE 1 DONE — Generated: {len(generated)} | Skipped: {skipped}\n")
    return generated

# ══════════════════════════════════════════════════════════════
# PHASE 2 — Qwen2.5-VL-3B SINGLE PASS: Filter + SEO
#
# WORLD BEST: One Qwen load handles both quality filter AND
# SEO content generation. Replaces CLIP entirely.
#
# FILTER RULES:
#   DELETE: two-headed, fused species, severely deformed
#   KEEP:   group photos same species, all tools/food/flowers
# ══════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════
# CATEGORY GROUPS — Smart filter rules per group
# Every category gets subject-match + quality check (no bypass)
# ══════════════════════════════════════════════════════════════

# Maps keyword → group name (checked via 'in category.lower()')
CATEGORY_GROUP_MAP = [
    # ── ANIMALS & CREATURES ───────────────────────────────────
    (["animal","bird","insect","fish","seafood","poultry","reptile",
      "butterfly","eagle","parrot","chicken","hen","cock",
      "goat","cow","buffalo","dog","cat","elephant","tiger","lion",
      "deer","rabbit","horse","camel","bear","monkey","snake",
      "crab","prawn","shrimp","lobster","squid","octopus",
      "tilapia","salmon","tuna","rohu","catla"], "animals"),

    # ── COOKED FOOD & DISHES ─────────────────────────────────
    (["food","dish","recipe","meal","curry","rice","biryani","pulao",
      "chicken_65","butter_chicken","paneer","dosa","idli","vada",
      "sambar","rasam","roti","chapati","paratha","naan","puri",
      "pizza","burger","sandwich","pasta","noodle","soup","stew",
      "fry","roast","grill","kebab","tikka","korma","masala",
      "indian_food","world_food","food_indian","food_world",
      "bakery","snack","cake","bread","cookie","biscuit",
      "sweet","halwa","ladoo","barfi","kheer","payasam",
      "indian_sweet","dairy","egg","poultry_chicken","raw_meat",
      "bakery_snacks","cool_drink","beverage"], "food"),

    # ── FRUITS & VEGETABLES ───────────────────────────────────
    (["fruit","vegetable","herb","spice","nut","dry_fruit",
      "ayurvedic","herbal"], "produce"),

    # ── FLOWERS & PLANTS & NATURE ────────────────────────────
    (["flower","plant","tree","leaf","nature","botanical",
      "garden","forest","sky","celestial","nature_tree",
      "sky_celestial"], "nature"),

    # ── TOOLS & HARDWARE ─────────────────────────────────────
    (["tool","hardware","equipment","machine","instrument",
      "kitchen","vessel","pot","pan","utensil","kitchen_vessel",
      "pots_vessel"], "tools"),

    # ── FASHION & ACCESSORIES ────────────────────────────────
    (["jewel","jewelry","jewellery","necklace","ring","bangle",
      "earring","bracelet","watch","bag","purse","handbag",
      "shoe","footwear","sandal","slipper","boot","heel",
      "cloth","dress","saree","lehenga","kurta","shirt",
      "indian_dress","clothing"], "fashion"),

    # ── ELECTRONICS & GADGETS ────────────────────────────────
    (["electronic","mobile","phone","laptop","computer","tablet",
      "accessory","cable","charger","earphone","speaker",
      "computer_accessory","mobile_accessory"], "electronics"),

    # ── CLIPART / ICONS / LOGOS / DESIGN ─────────────────────
    (["clipart","icon","logo","badge","frame","border","pattern",
      "texture","offer","effect","festival","pooja","background",
      "abstract","text_effect","music","stationery","office",
      "sport","vehicle","car","bike","medical","furniture",
      "frames_border","offer_logo"], "design"),
]

def _get_category_group(category: str) -> str:
    cat = category.lower()
    for keywords, group in CATEGORY_GROUP_MAP:
        if any(kw in cat for kw in keywords):
            return group
    return "general"

# ── Per-group CHECK INSTRUCTIONS ─────────────────────────────
GROUP_CHECK_RULES = {

    "animals": """SUBJECT MATCH CHECK:
- The prompt says: "{subject}" — does the image show EXACTLY that animal/species?
- If it shows a COMPLETELY DIFFERENT species → subject_match: false
  Examples: prompt=chicken but image=duck | prompt=crab but image=lobster | prompt=tiger but image=lion (different enough)
- Same species in different pose/style/angle → subject_match: true
- Cooked/prepared version when prompt expects live animal → subject_match: false

BODY SHAPE CHECK (very important — check before quality):
Every animal has a SPECIFIC expected body shape. If the body shape is wrong → shape_match: false → DELETE.

SHAPE REFERENCE TABLE — check the animal against its correct shape:
┌─────────────────┬──────────────────────────────────────────────────────────────┐
│ Animal          │ Expected Shape                                               │
├─────────────────┼──────────────────────────────────────────────────────────────┤
│ CRAB            │ Wide, flat, fan/hexagonal body with 2 claws + 8 legs visible │
│                 │ DELETE if: round blob, oval lump, egg shape, no claws/legs   │
├─────────────────┼──────────────────────────────────────────────────────────────┤
│ FISH (general)  │ Streamlined torpedo/oval body, clear tail fin, side fins     │
│                 │ DELETE if: circular disc shape, square, blob with no fins    │
├─────────────────┼──────────────────────────────────────────────────────────────┤
│ PRAWN/SHRIMP    │ Curved C/U shape, segmented body, long antennae, fan tail    │
│                 │ DELETE if: straight stick, ball shape, no segmentation       │
├─────────────────┼──────────────────────────────────────────────────────────────┤
│ LOBSTER         │ Long elongated body, large front claws, segmented tail       │
│                 │ DELETE if: round shape, no claws, no tail fan                │
├─────────────────┼──────────────────────────────────────────────────────────────┤
│ SQUID/OCTOPUS   │ Squid=torpedo+tentacles | Octopus=round head+8 arms spread  │
│                 │ DELETE if: no visible tentacles/arms, blob shape             │
├─────────────────┼──────────────────────────────────────────────────────────────┤
│ CHICKEN/HEN/    │ Plump round body, 2 wings, 2 legs, beak, comb visible        │
│ ROOSTER         │ DELETE if: oval blob, no beak, no wings visible at all       │
├─────────────────┼──────────────────────────────────────────────────────────────┤
│ DUCK/GOOSE      │ Round body, flat bill (not pointed beak), webbed feet        │
│                 │ DELETE if: pointed beak shown (that's a different bird)      │
├─────────────────┼──────────────────────────────────────────────────────────────┤
│ EAGLE/HAWK      │ Large wingspan when flying, hooked beak, talons visible      │
│                 │ DELETE if: no wings visible, round blob, no hooked beak      │
├─────────────────┼──────────────────────────────────────────────────────────────┤
│ PARROT          │ Compact body, curved beak, long tail feathers, vivid colors  │
│                 │ DELETE if: straight beak, no tail, blob shape                │
├─────────────────┼──────────────────────────────────────────────────────────────┤
│ BUTTERFLY       │ 4 wings with visible patterns, thin body/antennae            │
│                 │ DELETE if: 2 wings only (that's a moth style but check), blob│
├─────────────────┼──────────────────────────────────────────────────────────────┤
│ COW/BUFFALO     │ Large rectangular body, 4 legs, horns, udder/tail visible    │
│                 │ DELETE if: round shape, no legs visible, no distinguishing   │
├─────────────────┼──────────────────────────────────────────────────────────────┤
│ GOAT/SHEEP      │ Compact body, 4 legs, horns or woolly coat                   │
│                 │ DELETE if: oval blob, no legs, no head features              │
├─────────────────┼──────────────────────────────────────────────────────────────┤
│ TIGER/LION      │ Large muscular cat body, 4 legs, distinctive markings/mane  │
│                 │ DELETE if: round blob, no legs, no stripes/mane              │
├─────────────────┼──────────────────────────────────────────────────────────────┤
│ ELEPHANT        │ Very large body, long trunk, big ears, 4 pillar legs, tusks  │
│                 │ DELETE if: no trunk visible, round shape, tiny               │
├─────────────────┼──────────────────────────────────────────────────────────────┤
│ SNAKE           │ Long thin elongated S/coil shape, scales, no legs            │
│                 │ DELETE if: round ball, thick blob, has legs                  │
├─────────────────┼──────────────────────────────────────────────────────────────┤
│ RABBIT          │ Round body, LONG ears (key feature), short tail, 4 paws      │
│                 │ DELETE if: short ears (looks like cat/rat), blob shape       │
├─────────────────┼──────────────────────────────────────────────────────────────┤
│ DOG/CAT         │ 4 legs, pointed ears (cat) or floppy ears (dog), tail        │
│                 │ DELETE if: no legs, round blob, no distinctive ears/tail     │
├─────────────────┼──────────────────────────────────────────────────────────────┤
│ HORSE/CAMEL     │ Horse=tall slender 4-leg | Camel=hump(s) visible clearly     │
│                 │ DELETE if: no hump (camel), blob shape, no legs              │
└─────────────────┴──────────────────────────────────────────────────────────────┘

For animals NOT in the table: use common sense — if the body shape is a blob/oval/circle
with NO distinctive features of that animal → DELETE.

QUALITY CHECK (only if subject matches AND shape is correct):
- DELETE if: two or more heads on ONE body
- DELETE if: two completely different species FUSED into one impossible creature
- DELETE if: extra limbs growing from wrong body parts (e.g. wing from stomach)
- DELETE if: face/head severely distorted with impossible features (3+ eyes, melted face)
- KEEP if: group of 2–5 same species (completely normal)
- KEEP if: AI/cartoon/illustrated style with correct body shape
- KEEP if: minor artistic styling but animal is clearly recognizable

Add shape_match field to your JSON response:
"shape_match": true or false  (false = wrong body shape → DELETE)""",

    "food": """SUBJECT MATCH CHECK:
- The prompt says: "{subject}" — does the image show EXACTLY that dish/food item?
- Chicken 65 prompt → must show fried spicy chicken pieces, NOT raw chicken, NOT butter chicken
- Biryani prompt → must show layered rice dish with spices, NOT plain rice, NOT pulao
- Dosa prompt → must show thin crispy crepe, NOT idli, NOT uttapam
- If completely wrong food shown → subject_match: false
- Same dish in slightly different presentation/plating → subject_match: true
- Raw ingredient when cooked dish expected → subject_match: false

QUALITY CHECK (only if subject matches):
- DELETE if: food is clearly rotten, moldy, inedible-looking
- DELETE if: completely unrecognizable blob with no food structure
- DELETE if: wrong serving vessel that makes it unidentifiable
- KEEP if: plated differently but same dish
- KEEP if: AI/illustration style of the correct food
- KEEP if: multiple portions of the same dish""",

    "produce": """SUBJECT MATCH CHECK:
- The prompt says: "{subject}" — does the image show EXACTLY that fruit/vegetable/herb?
- Mango prompt → must show mango shape, NOT papaya or similar
- Grapes prompt → must show grape cluster, NOT berries in general
- If completely different produce shown → subject_match: false
- Different variety/color of same fruit → subject_match: true (e.g., red mango vs yellow mango)

QUALITY CHECK (only if subject matches):
- DELETE if: severely rotten or moldy (not fresh/food-safe looking)
- DELETE if: deformed beyond recognition (not natural shape at all)
- KEEP if: slightly imperfect or bruised (normal)
- KEEP if: multiple pieces of the same fruit/vegetable
- KEEP if: cross-section/cut view of the correct item
- KEEP if: illustrated/cartoon style""",

    "nature": """SUBJECT MATCH CHECK:
- The prompt says: "{subject}" — does the image show EXACTLY that flower/plant/tree?
- Rose prompt → must show rose petals/shape, NOT generic flower
- Lotus prompt → must show lotus, NOT water lily when clearly different
- If completely different plant shown → subject_match: false
- Different color variety of same flower → subject_match: true

QUALITY CHECK (only if subject matches):
- DELETE if: completely melted/unrecognizable plant structure
- KEEP if: wilted (still recognizable)
- KEEP if: bud/half-open/fully-open stages
- KEEP if: single or bouquet arrangement
- KEEP if: illustrated/watercolor/AI art style""",

    "tools": """SUBJECT MATCH CHECK:
- The prompt says: "{subject}" — does the image show EXACTLY that tool/object?
- Hammer prompt → must show hammer, NOT wrench
- Kadai (cooking pot) prompt → must show kadai, NOT regular pot
- If completely wrong tool/object shown → subject_match: false
- Different design/material of same tool → subject_match: true

QUALITY CHECK (only if subject matches):
- DELETE if: object is so distorted it cannot be identified
- DELETE if: multiple completely different tools merged into one impossible object
- KEEP if: stylized/metallic/illustrated version of correct tool
- KEEP if: set of same tools
- KEEP if: viewed from unusual angle but still identifiable""",

    "fashion": """SUBJECT MATCH CHECK:
- The prompt says: "{subject}" — does the image show EXACTLY that item?
- Gold necklace prompt → must show necklace, NOT earring, NOT bracelet
- Saree prompt → must show saree, NOT lehenga, NOT dupatta alone
- Watch prompt → must show wristwatch, NOT wall clock
- If completely wrong fashion item → subject_match: false
- Different design/color/style of same item → subject_match: true

QUALITY CHECK (only if subject matches):
- DELETE if: item is so distorted it cannot be recognized as wearable
- DELETE if: mixed with unrelated body parts in disturbing way
- KEEP if: worn by model or shown standalone
- KEEP if: different angle or artistic style""",

    "electronics": """SUBJECT MATCH CHECK:
- The prompt says: "{subject}" — does the image show EXACTLY that device/accessory?
- iPhone prompt → must show smartphone, NOT tablet, NOT laptop
- Earphone prompt → must show earphone/earbud, NOT speaker
- If completely wrong device shown → subject_match: false
- Different brand/color/model of same device type → subject_match: true

QUALITY CHECK (only if subject matches):
- DELETE if: device is so melted/distorted it cannot be identified
- KEEP if: stylized/illustration version of correct device
- KEEP if: shown with cables/accessories""",

    "design": """SUBJECT MATCH CHECK:
- The prompt says: "{subject}" — does the image show relevant design/graphic?
- Offer banner prompt → must show promotional/sale design, NOT random clipart
- Diwali frame prompt → must show festival-themed frame, NOT Christmas
- If completely wrong design category shown → subject_match: false
- Different style/color of same design type → subject_match: true

QUALITY CHECK (only if subject matches):
- DELETE if: completely blank or unrecognizable image
- DELETE if: random noise with no design structure
- KEEP if: any clear graphic, icon, frame, pattern
- KEEP if: any recognizable festival/offer/clipart element""",

    "general": """SUBJECT MATCH CHECK:
- The prompt says: "{subject}" — does the image show the expected subject?
- If a completely unrelated object/scene is shown → subject_match: false
- Same subject in different style/angle → subject_match: true

QUALITY CHECK (only if subject matches):
- DELETE if: image is completely unrecognizable or blank
- DELETE if: severely deformed beyond any recognition
- KEEP if: any clear representation of the subject""",
}


def _build_qwen_prompt(item, subject, category, slug_base):
    group      = _get_category_group(category)
    check_rule = GROUP_CHECK_RULES.get(group, GROUP_CHECK_RULES["general"])
    check_rule = check_rule.replace("{subject}", subject)

    return f"""You are a STRICT quality inspector AND SEO writer for UltraPNG.com — a free transparent PNG library.

IMAGE PROMPT USED: "{item.get('prompt', '')}"
EXPECTED SUBJECT: {subject}
CATEGORY: {category}
GROUP: {group}

════════════════════════════════════════
STEP 1 — SUBJECT MATCH (Most Important)
════════════════════════════════════════
{check_rule}

════════════════════════════════════════
STEP 2 — CONFIDENCE SCORE
════════════════════════════════════════
Give a confidence score 0–10:
- 9–10: Perfect match, excellent quality
- 7–8:  Good match, minor issues
- 5–6:  Uncertain — borderline
- 0–4:  Wrong subject OR severely deformed

RULE: If confidence < 6 → verdict must be DELETE

════════════════════════════════════════
STEP 3 — VERDICT
════════════════════════════════════════
verdict = DELETE if ANY of:
  • subject_match is false (wrong item shown)
  • confidence < 6
  • image is blank/pure noise

verdict = KEEP if:
  • subject_match is true AND confidence >= 6

════════════════════════════════════════
STEP 4 — SEO CONTENT (only if KEEP)
════════════════════════════════════════
If verdict is KEEP, fill all SEO fields.
If verdict is DELETE, use empty strings for SEO fields.

Return ONLY valid JSON starting with {{ — no markdown, no explanation:

{{
  "subject_match": true or false,
  "shape_match": true or false,
  "confidence": 0-10,
  "verdict": "KEEP" or "DELETE",
  "reason": "one line reason if DELETE, else empty string",
  "title": "20+ words: {subject} [specific visual details] Transparent PNG HD Free Download | UltraPNG",
  "slug": "max 55 chars: {slug_base}-[2-3 visual words]-png-hd",
  "meta_desc": "max 155 chars: {subject} visual detail transparent free UltraPNG.com",
  "h1": "{subject} [visual details] PNG HD Image",
  "tags": "18 comma-separated: name, visual words, {subject} PNG free, {subject} transparent PNG, canva, flex banner, social media, ultrapng",
  "description": "650+ words:\\n## About This {subject} PNG Image\\n[200+ words 2 paragraphs]\\n## Image Quality & Technical Details\\n[100 words]\\n## Design Ideas & Creative Applications\\n[8 bullet points]\\n## Technical Specifications\\n[table: Format/Background/Resolution/Edge Quality/Compatible With/Print Ready/License]\\n## How to Download\\n[6 numbered steps]\\n## Frequently Asked Questions\\n[4 Q&A: free?/Canva?/watermark?/flex banner?]\\n## Why UltraPNG\\n[80 words]"
}}"""


# ══════════════════════════════════════════════════════════════
# PHASE 2 — Qwen2.5-VL-3B  SMART FILTER + SEO
# ══════════════════════════════════════════════════════════════
def phase2_qwen_filter_seo(generated):
    ckpt = load_checkpoint("phase2_posts")
    if ckpt:
        return ckpt

    log("=" * 56)
    log("PHASE 2: Qwen2.5-VL-3B — SMART FILTER + SEO")
    log("  Step 1: Subject Match  (wrong item → DELETE)")
    log("  Step 2: Confidence <6  (uncertain → DELETE)")
    log("  Step 3: Quality Check  (deformed → DELETE)")
    log("  Step 4: SEO Generation (if KEEP)")
    log("  NO category bypass — every image inspected")
    log("=" * 56)

    if not generated:
        return []

    from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
    from qwen_vl_utils import process_vision_info

    log("Loading Qwen2.5-VL-3B from dataset...")
    processor = AutoProcessor.from_pretrained(str(QWEN_DIR), use_fast=True)
    model     = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        str(QWEN_DIR),
        torch_dtype=torch.float16,
        device_map="auto",
    )
    model.eval()
    log(f"Qwen loaded! Processing {len(generated)} images...\n")

    posts      = []
    deleted    = 0
    used_slugs = set()
    t0         = time.time()

    # Partial checkpoint recovery
    partial     = load_checkpoint("phase2_posts_partial")
    resume_from = 0
    if partial:
        posts       = partial
        used_slugs  = set(f"{p['category']}/{p['slug']}" for p in posts)
        resume_from = len(posts)
        log(f"  Partial checkpoint: resuming from item {resume_from}")

    # Delete reason stats
    stats = {"wrong_subject": 0, "low_confidence": 0, "deformed": 0, "parse_fail": 0}

    for i, item_data in enumerate(generated):
        if i < resume_from:
            continue

        item      = item_data["item"]
        category  = item["category"]
        subject   = item.get("subject_name") or category.replace("-", " ").replace("_", " ").title()
        prompt    = item.get("prompt", f"a {subject}")
        slug_base = slugify(subject)
        path      = Path(item_data["path"])
        group     = _get_category_group(category)

        approved_path = APPROVED_DIR / path.relative_to(GENERATED_DIR)
        approved_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with Image.open(path).convert("RGB") as img_orig:
                iw, ih = img_orig.size
                mxs    = 512
                if max(iw, ih) > mxs:
                    r       = mxs / max(iw, ih)
                    img_pil = img_orig.resize((int(iw * r), int(ih * r)), Image.LANCZOS).copy()
                else:
                    img_pil = img_orig.copy()

            messages = [{
                "role": "user",
                "content": [
                    {"type": "image", "image": img_pil},
                    {"type": "text",  "text":  _build_qwen_prompt(item, subject, category, slug_base)},
                ],
            }]

            text = processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True)
            img_inputs, vid_inputs = process_vision_info(messages)
            inputs = processor(
                text=[text], images=img_inputs, videos=vid_inputs,
                padding=True, return_tensors="pt",
            ).to(model.device)

            with torch.no_grad():
                out_ids = model.generate(
                    **inputs,
                    max_new_tokens=2500,
                    temperature=0.3,      # lower = more deterministic for inspection
                    top_p=0.9,
                    do_sample=True,
                    pad_token_id=processor.tokenizer.eos_token_id,
                )

            trimmed = [out_ids[k][len(inputs.input_ids[k]):]
                       for k in range(len(out_ids))]
            raw = processor.batch_decode(
                trimmed, skip_special_tokens=True,
                clean_up_tokenization_spaces=True)[0].strip()

            # Parse JSON
            ai = {}
            try:
                j0, j1 = raw.find("{"), raw.rfind("}") + 1
                if j0 >= 0 and j1 > j0:
                    ai = json.loads(raw[j0:j1])
            except Exception:
                try:
                    clean = re.sub(r'[\x00-\x1f\x7f]', ' ',
                                   raw[raw.find("{"):raw.rfind("}") + 1])
                    ai = json.loads(clean)
                except Exception:
                    ai = {}

            # ── Extract decision fields ──
            subject_match = ai.get("subject_match", True)
            if isinstance(subject_match, str):
                subject_match = subject_match.lower() not in ("false", "no", "0")
            confidence    = int(ai.get("confidence", 7))
            verdict       = ai.get("verdict", "KEEP").strip().upper()
            reason        = ai.get("reason", "")

            # ── Smart DELETE logic ──
            shape_match = ai.get("shape_match", True)
            if isinstance(shape_match, str):
                shape_match = shape_match.lower() not in ("false", "no", "0")

            delete_reason = None
            if not subject_match:
                delete_reason = f"Wrong subject (expected={subject}, group={group})"
                stats["wrong_subject"] += 1
            elif group == "animals" and not shape_match:
                delete_reason = f"Wrong body shape for {subject}"
                stats["wrong_shape"] = stats.get("wrong_shape", 0) + 1
            elif confidence < 6:
                delete_reason = f"Low confidence={confidence} — {reason}"
                stats["low_confidence"] += 1
            elif verdict == "DELETE":
                delete_reason = reason or "Deformed/quality failed"
                stats["deformed"] += 1

            if delete_reason:
                log(f"  DELETE [{i+1}/{len(generated)}] {path.name}")
                log(f"         {delete_reason}")
                path.unlink(missing_ok=True)
                deleted += 1
                continue

            # ── KEEP ──
            shutil.copy2(str(path), str(approved_path))

            raw_slug  = ai.get("slug") or f"{slug_base}-png-hd"
            slug      = slugify(raw_slug)
            base, sfx = slug, 1
            while f"{category}/{slug}" in used_slugs:
                slug = f"{base}-{sfx}"; sfx += 1
            used_slugs.add(f"{category}/{slug}")

            desc = ai.get("description", "")
            if not desc or len(desc.split()) < 100:
                desc = _fallback_desc(subject, category, prompt)

            post = {
                "category":        category,
                "subcategory":     item.get("subcategory", "general"),
                "subject_name":    subject,
                "filename":        item["filename"],
                "original_prompt": prompt,
                "slug":            slug,
                "title":           ai.get("title") or f"{subject} Transparent PNG HD Free Download | UltraPNG",
                "h1":              ai.get("h1")    or f"{subject} PNG HD Image",
                "meta_desc":       (ai.get("meta_desc") or
                                    f"Download {subject} PNG transparent background free HD. UltraPNG.com")[:155],
                "alt_text":        (ai.get("h1") or f"{subject} PNG") +
                                   " Transparent Background Free Download UltraPNG",
                "tags":            ai.get("tags") or
                                   f"{subject},png,transparent,free download,hd,{subject} PNG free,ultrapng",
                "description":     desc,
                "word_count":      len(desc.split()),
                "ai_generated":    bool(ai),
                "qwen_confidence": confidence,
                "qwen_group":      group,
                "approved_path":   str(approved_path),
                "png_file_id": "", "jpg_file_id": "", "webp_file_id": "",
                "download_url": "", "preview_url": "", "preview_url_small": "",
                "webp_preview_url": "", "preview_w": 800, "preview_h": 800,
                "date_added": datetime.now().strftime("%Y-%m-%d"),
            }
            posts.append(post)

            rate = max((i + 1 - resume_from), 1) / (time.time() - t0)
            eta  = (len(generated) - i - 1) / rate / 60
            log(f"  KEEP [{i+1}/{len(generated)}] {slug} (conf={confidence}, grp={group}, shape={'✓' if shape_match else 'n/a'}) | ETA {eta:.0f}min")

        except Exception as e:
            log(f"  Qwen FAIL [{i+1}] {item.get('filename','?')}: {e}")
            stats["parse_fail"] += 1
            shutil.copy2(str(path), str(approved_path))
            posts.append(_fallback_post(item_data, subject, category, prompt,
                                        used_slugs, str(approved_path)))

        if (i + 1) % 10 == 0:
            gc.collect()
            torch.cuda.empty_cache()
            save_checkpoint("phase2_posts_partial", posts)

    log("\n  Deleting Qwen2.5-VL-3B -> freeing VRAM...")
    del model, processor
    free_memory()

    save_checkpoint("phase2_posts", posts)
    log(f"PHASE 2 DONE — Kept: {len(posts)} | Deleted: {deleted}")
    log(f"  Delete breakdown → WrongSubject:{stats['wrong_subject']} "
        f"WrongShape:{stats.get('wrong_shape',0)} "
        f"LowConf:{stats['low_confidence']} Deformed:{stats['deformed']} "
        f"ParseFail:{stats['parse_fail']}\n")
    return posts



def _fallback_desc(subject, category, prompt=""):
    ph = f' (prompt: "{prompt[:100]}")' if prompt else ""
    return f"""## About This {subject} PNG Image

This high-quality {subject} PNG image{ph} is available for free download from UltraPNG.com. The image features a completely transparent background, making it perfect for graphic designers working on flex banners, social media posts, YouTube thumbnails, and digital marketing designs. Every edge is precisely processed using RMBG-2.0 AI for seamless integration into any project.

The {subject} collection at UltraPNG.com is updated daily with fresh AI-generated images across 50+ categories. This PNG delivers professional-grade transparency that works in Photoshop, Canva, CorelDRAW, and Figma — no manual background removal needed.

## Image Quality & Technical Details

This {subject} PNG is processed using RMBG-2.0 ONNX AI for pixel-perfect transparent edges. The HD resolution stays sharp at any scale, from 200px social media icons to 4096px flex banner prints. Clean alpha channel with anti-aliased edges blends naturally on any background.

## Design Ideas & Creative Applications

- Flex banner and large-format hoarding designs for businesses
- Social media posts, Instagram stories, and WhatsApp status graphics
- YouTube thumbnail and channel banner designs
- Wedding invitation cards and event poster designs
- Restaurant menu cards and food delivery app images
- Birthday celebration and felicitation banners
- E-commerce product catalog and online shop listings
- PowerPoint, Google Slides, and Canva presentations

## Technical Specifications

| Specification | Details |
|---|---|
| Format | PNG with Full Alpha Channel |
| Background | 100% Transparent |
| Resolution | HD — print and digital ready |
| Edge Quality | AI-processed (RMBG-2.0), clean anti-aliased |
| Compatible With | Photoshop, Canva, CorelDRAW, Figma, GIMP |
| Print Ready | Yes — flex, vinyl, hoarding printing |
| License | Free personal and commercial use |
| Watermark | Preview only — downloaded file is clean |

## How to Download

1. Click the **Download PNG Free** button on this page
2. A 15-second countdown timer begins
3. When the timer ends, click **Download Now!**
4. The clean PNG saves to your Downloads folder
5. Open in Photoshop or Canva, drag onto your canvas
6. Resize freely — stays HD at any scale

## Frequently Asked Questions

**Is this {subject} PNG completely free?**
Yes — 100% free personal and commercial use. No account, no sign-up. No watermark on downloaded file.

**Can I use this in Canva?**
Yes. Canva Uploads, upload PNG, drag onto canvas. Transparent background works perfectly.

**Does the downloaded PNG have a watermark?**
No. Preview shows watermark for protection — downloaded file is completely clean.

**Can I print on flex banners?**
Yes. HD resolution is print-ready for large-format flex, vinyl, and hoarding.

## Why UltraPNG

UltraPNG.com is a free transparent PNG library updated daily with quality-verified AI-generated images. Every PNG features pixel-perfect RMBG-2.0 transparency. Completely free — no fees, no signup, no watermarks. Trusted by designers and marketers worldwide."""


def _fallback_post(item_data, subject, category, prompt, used_slugs, approved_path=""):
    item      = item_data["item"]
    slug      = slugify(f"{subject}-png-hd")
    base, sfx = slug, 1
    while f"{category}/{slug}" in used_slugs:
        slug = f"{base}-{sfx}"; sfx += 1
    used_slugs.add(f"{category}/{slug}")
    desc = _fallback_desc(subject, category, prompt)
    return {
        "category": category, "subcategory": item.get("subcategory", "general"),
        "subject_name": subject, "filename": item.get("filename", ""),
        "original_prompt": prompt, "slug": slug,
        "title": f"{subject} Transparent PNG HD Free Download | UltraPNG",
        "h1": f"{subject} PNG HD Image",
        "meta_desc": f"Download {subject} PNG transparent background free HD. UltraPNG.com.",
        "alt_text": f"{subject} PNG Transparent Background Free Download UltraPNG",
        "tags": f"{subject},png,transparent,free download,hd,{subject} PNG free,ultrapng",
        "description": desc, "word_count": len(desc.split()), "ai_generated": False,
        "approved_path": approved_path,
        "png_file_id": "", "jpg_file_id": "", "webp_file_id": "",
        "download_url": "", "preview_url": "", "preview_url_small": "",
        "webp_preview_url": "", "preview_w": 800, "preview_h": 800,
        "date_added": datetime.now().strftime("%Y-%m-%d"),
    }

# ══════════════════════════════════════════════════════════════
# PHASE 3 — RMBG-2.0 ONNX  Background Removal
# ══════════════════════════════════════════════════════════════
def phase3_bg_remove(posts):
    ckpt = load_checkpoint("phase3_transparent")
    if ckpt:
        return ckpt

    log("=" * 56)
    log("PHASE 3: RMBG-2.0 ONNX — Background Removal (GPU)")
    log("=" * 56)

    if not posts:
        return []

    import onnxruntime as ort
    import cv2

    if not RMBG_ONNX.exists():
        raise FileNotFoundError(f"ONNX model not found: {RMBG_ONNX}")

    providers = (["CUDAExecutionProvider", "CPUExecutionProvider"]
                 if ort.get_device() == "GPU" else ["CPUExecutionProvider"])
    session  = ort.InferenceSession(str(RMBG_ONNX), providers=providers)
    inp_name = session.get_inputs()[0].name
    log(f"RMBG ONNX loaded | {session.get_providers()[0]}\n")

    def remove_bg(img_pil):
        ow, oh  = img_pil.size
        img_np  = np.array(img_pil.convert("RGB")).astype(np.float32) / 255.0
        img_rs  = cv2.resize(img_np, (1024, 1024), interpolation=cv2.INTER_LINEAR)
        mean    = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std     = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        img_rs  = (img_rs - mean) / std
        inp     = img_rs.transpose(2, 0, 1)[np.newaxis].astype(np.float32)
        outputs = session.run(None, {inp_name: inp})
        mask    = outputs[0][0, 0]
        if mask.max() > 1.0 or mask.min() < 0.0:
            mask = 1.0 / (1.0 + np.exp(-mask))
        mask_full = cv2.resize(mask, (ow, oh), interpolation=cv2.INTER_LINEAR)
        mask_full = (mask_full * 255).clip(0, 255).astype(np.uint8)
        result    = img_pil.convert("RGBA")
        result.putalpha(Image.fromarray(mask_full))
        return result

    result_posts, t0 = [], time.time()

    for i, post in enumerate(posts):
        path = Path(post["approved_path"])
        try:
            rel = path.relative_to(APPROVED_DIR)
            out = TRANSPARENT_DIR / rel
            out.parent.mkdir(parents=True, exist_ok=True)

            if out.exists():
                result_posts.append({**post, "transparent_path": str(out)})
                continue

            with Image.open(path).convert("RGB") as img_pil:
                result = remove_bg(img_pil)
            result.save(str(out), "PNG", compress_level=0)
            result_posts.append({**post, "transparent_path": str(out)})

            if (i + 1) % 20 == 0:
                log(f"  BG done: {i+1}/{len(posts)} | {(i+1)/(time.time()-t0):.2f}/s")

        except Exception as e:
            log(f"  RMBG FAIL {path.name}: {e}")

    log("\n  Deleting RMBG session...")
    del session
    free_memory()

    save_checkpoint("phase3_transparent", result_posts)
    log(f"PHASE 3 DONE — Transparent PNGs: {len(result_posts)}\n")
    return result_posts

# ══════════════════════════════════════════════════════════════
# PHASE 4 — Google Drive Upload + URL Capture
# ══════════════════════════════════════════════════════════════
def phase4_upload(posts):
    ckpt = load_checkpoint("phase4_uploaded")
    if ckpt:
        return ckpt

    log("=" * 56)
    log("PHASE 4: Google Drive Upload + URL Capture")
    log("=" * 56)

    if not posts:
        return []

    token     = get_drive_token()
    fcache    = {}
    png_root  = drive_folder(token, "png_library_images")
    prev_root = drive_folder(token, "png_library_previews")
    log(f"Drive ready. Uploading {len(posts)} images...\n")

    uploaded, t0 = [], time.time()

    for i, post in enumerate(posts):
        path = Path(post["transparent_path"])

        if i > 0 and i % 50 == 0:
            token = get_drive_token()
            log(f"  Token refreshed at upload {i}")

        try:
            cat = post["category"]
            sub = post.get("subcategory", "general")
            key = f"{cat}/{sub}"

            if key not in fcache:
                cp = drive_folder(token, cat, png_root)
                sp = drive_folder(token, sub, cp)
                cr = drive_folder(token, cat, prev_root)
                sr = drive_folder(token, sub, cr)
                fcache[f"p_{key}"] = sp
                fcache[f"r_{key}"] = sr

            png_bytes = path.read_bytes()
            pr  = drive_upload(token, fcache[f"p_{key}"], path.name, png_bytes)
            drive_share(token, pr["id"])

            jpg_bytes, webp_bytes, pw, ph = make_previews(path)

            jr  = drive_upload(token, fcache[f"r_{key}"],
                               path.stem + ".jpg", jpg_bytes, "image/jpeg")
            drive_share(token, jr["id"])

            wr  = drive_upload(token, fcache[f"r_{key}"],
                               path.stem + ".webp", webp_bytes, "image/webp")
            drive_share(token, wr["id"])

            uploaded.append({
                **post,
                "png_file_id":       pr["id"],
                "jpg_file_id":       jr["id"],
                "webp_file_id":      wr["id"],
                "download_url":      download_url(pr["id"]),
                "preview_url":       preview_url(jr["id"], 800),
                "preview_url_small": preview_url(jr["id"], 400),
                "webp_preview_url":  preview_url(wr["id"], 800),
                "preview_w": pw, "preview_h": ph,
                "date_added": datetime.now().strftime("%Y-%m-%d"),
            })

            if (i + 1) % 10 == 0:
                log(f"  Uploaded: {i+1}/{len(posts)} | {(i+1)/(time.time()-t0):.2f}/s")
            time.sleep(0.05)

        except Exception as e:
            log(f"  Upload FAIL {path.name}: {e}")

    save_checkpoint("phase4_uploaded", uploaded)
    log(f"PHASE 4 DONE — Uploaded: {len(uploaded)} in {(time.time()-t0)/60:.0f}min\n")
    return uploaded

# ══════════════════════════════════════════════════════════════
# HTML BUILDER
# ══════════════════════════════════════════════════════════════
def md_to_html(md):
    if not md: return ""
    o = str(md)
    o = re.sub(r'^### (.+)$', r'<h3>\1</h3>', o, flags=re.MULTILINE)
    o = re.sub(r'^## (.+)$',  r'<h2>\1</h2>', o, flags=re.MULTILINE)
    o = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', o)
    def tbl(m):
        rows = [r for r in m.group(0).strip().split('\n')
                if not re.match(r'^\|[\s\-|:]+\|$', r)]
        html = ""
        for idx, row in enumerate(rows):
            cells = [c.strip() for c in row.strip('|').split('|')]
            tag   = 'th' if idx == 0 else 'td'
            html += '<tr>' + ''.join(f'<{tag}>{c}</{tag}>' for c in cells) + '</tr>'
        return f'<table class="spec-table">{html}</table>'
    o = re.sub(r'((?:^\|.+\|\n?)+)', tbl, o, flags=re.MULTILINE)
    o = re.sub(r'^- (.+)$', r'<li>\1</li>', o, flags=re.MULTILINE)
    o = re.sub(r'(<li>.*?</li>\n?)+', lambda m: f'<ul>{m.group(0)}</ul>', o)
    o = re.sub(r'^\d+\. (.+)$', r'<oli>\1</oli>', o, flags=re.MULTILINE)
    o = re.sub(r'(<oli>.*?</oli>\n?)+',
               lambda m: '<ol>' + m.group(0).replace('<oli>', '<li>').replace('</oli>', '</li>') + '</ol>', o)
    o = re.sub(r'\n{2,}', '</p><p>', o)
    o = f'<p>{o}</p>'
    o = re.sub(r'<p>\s*</p>', '', o)
    return o

def _head(title, desc, url, img="", kw="", webp_img=""):
    og_img = webp_img or img
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}"/>
{f'<meta name="keywords" content="{esc(kw)}"/>' if kw else ''}
<meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1"/>
<link rel="canonical" href="{url}"/>
<meta property="og:type" content="website"/>
<meta property="og:url" content="{url}"/>
<meta property="og:title" content="{esc(title)}"/>
<meta property="og:description" content="{esc(desc)}"/>
{f'<meta property="og:image" content="{esc(og_img)}"/>' if og_img else ''}
<meta property="og:site_name" content="UltraPNG"/>
<meta name="twitter:card" content="summary_large_image"/>
<link rel="icon" type="image/svg+xml" href="/favicon.svg"/>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Sora:wght@500;600;700;800&family=Outfit:wght@400;500;600;700&display=swap" media="print" onload="this.media='all'"/>
<link rel="stylesheet" href="/css/style.css?v=22"/>
<link rel="stylesheet" href="/css/png-library.css?v=10"/>"""

def _header():
    return ('<header><div class="header-inner">'
            '<a href="/" class="logo"><div class="logo-icon">U</div>'
            '<div class="logo-text"><span class="logo-name">Ultra<span>PNG</span></span>'
            '<span class="logo-sub">Free Transparent PNG Images</span></div></a>'
            '<nav><a href="/">Home</a><a href="/png-library/" class="active">PNG Library</a>'
            '<a href="/pages/about.html">About</a>'
            '<a href="/pages/contact.html" class="nav-contact">Contact</a></nav>'
            '</div></header>')

def _footer():
    return (f'<footer><div class="footer-inner">'
            f'<div class="footer-links">'
            f'<a href="/png-library/">PNG Library</a>'
            f'<a href="/pages/about.html">About</a>'
            f'<a href="/pages/contact.html">Contact</a>'
            f'<a href="/pages/terms.html">Terms</a>'
            f'<a href="/pages/privacy.html">Privacy</a></div>'
            f'<p>&copy; {datetime.now().year} UltraPNG.com — Free Transparent PNG Images.</p>'
            f'</div></footer>')

def build_item_page(post, related):
    url       = f"{SITE_URL}/png-library/{post['category']}/{post['slug']}/"
    img       = post.get("preview_url", "")
    webp_img  = post.get("webp_preview_url", "")
    desc_html = md_to_html(post.get("description", ""))
    enc_dl    = base64.b64encode(post.get("download_url", "").encode()).decode()
    tags      = [t.strip() for t in post.get("tags", "").split(",") if t.strip()]
    cat_label = post.get("subject_name", post["category"])
    tags_html = "".join(
        f'<a href="/png-library/?q={esc(t)}" class="png-tag">{esc(t)}</a>' for t in tags)
    share_text = json.dumps(f'{post.get("h1", "")} PNG Free Download — ')

    img_tag = (
        f'<picture>'
        f'<source srcset="{esc(webp_img)}" type="image/webp"/>'
        f'<img src="{esc(img)}" alt="{esc(post.get("alt_text",""))}" '
        f'width="{post.get("preview_w",800)}" height="{post.get("preview_h",800)}" '
        f'fetchpriority="high" onerror="this.src=\'/img/placeholder.png\'"/>'
        f'</picture>'
    ) if webp_img else (
        f'<img src="{esc(img)}" alt="{esc(post.get("alt_text",""))}" '
        f'width="{post.get("preview_w",800)}" height="{post.get("preview_h",800)}" '
        f'fetchpriority="high" onerror="this.src=\'/img/placeholder.png\'"/>'
    )

    rel_html = "".join(
        f'<a href="/png-library/{r["category"]}/{r["slug"]}/" class="png-related-card">'
        f'<div class="png-related-thumb">'
        f'<img src="{esc(r.get("preview_url_small",r.get("preview_url","")))} " '
        f'alt="{esc(r.get("h1",""))}" loading="lazy" width="300" height="300" '
        f'onerror="this.parentNode.style.display=\'none\'"/></div>'
        f'<span class="png-related-name">{esc(r.get("h1",""))}</span></a>\n'
        for r in related[:24]
    )

    schema = json.dumps({
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "ImageObject", "name": post.get("h1", ""),
             "description": post.get("meta_desc", ""),
             "contentUrl": post.get("download_url", ""), "thumbnailUrl": img,
             "encodingFormat": "image/png", "isAccessibleForFree": True,
             "datePublished": post.get("date_added", ""),
             "license": f"{SITE_URL}/pages/terms.html",
             "publisher": {"@type": "Organization", "name": "UltraPNG", "url": SITE_URL + "/"},
             "keywords": ", ".join(tags)},
            {"@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE_URL + "/"},
                {"@type": "ListItem", "position": 2, "name": "PNG Library", "item": f"{SITE_URL}/png-library/"},
                {"@type": "ListItem", "position": 3, "name": cat_label, "item": f"{SITE_URL}/png-library/{post['category']}/"},
                {"@type": "ListItem", "position": 4, "name": post.get("h1", "")},
            ]},
            {"@type": "FAQPage", "mainEntity": [
                {"@type": "Question", "name": f"Is this {cat_label} PNG free?",
                 "acceptedAnswer": {"@type": "Answer", "text": "Yes — 100% free. No account required."}},
                {"@type": "Question", "name": "Can I use this PNG in Canva?",
                 "acceptedAnswer": {"@type": "Answer", "text": "Yes. Upload via My Files in Canva."}},
                {"@type": "Question", "name": "Does the downloaded PNG have a watermark?",
                 "acceptedAnswer": {"@type": "Answer", "text": "No. Downloaded file is completely clean."}},
                {"@type": "Question", "name": "Can I print this on flex banners?",
                 "acceptedAnswer": {"@type": "Answer", "text": "Yes. HD PNG is print-ready for flex/hoarding."}},
            ]},
        ]
    })

    return f"""{_head(post.get("title",""), post.get("meta_desc",""), url, img, post.get("tags",""), webp_img)}
{f'<link rel="preload" as="image" href="{esc(webp_img or img)}" fetchpriority="high"/>' if (webp_img or img) else ''}
<script type="application/ld+json">{schema}</script>
</head>
<body class="png-item-page">
{_header()}
<nav class="breadcrumb" aria-label="Breadcrumb">
  <a href="/">Home</a><span>&rsaquo;</span>
  <a href="/png-library/">PNG Library</a><span>&rsaquo;</span>
  <a href="/png-library/{post['category']}/">{esc(cat_label)}</a><span>&rsaquo;</span>
  <span aria-current="page">{esc(post.get("h1",""))}</span>
</nav>
<div class="png-item-wrap"><div class="png-item-layout"><div class="png-item-center">
<div class="png-item-top-row">
<div class="png-item-img-col"><div class="png-img-card">{img_tag}</div></div>
<div class="png-item-info-col">
  <h1 class="png-dl-title">{esc(post.get("h1",""))}</h1>
  <div class="png-dl-btn-wrap" id="bW">
    <button class="png-dl-btn" onclick="startCD()" aria-label="Download PNG Free">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/>
      </svg>Download PNG Free
    </button>
  </div>
  <div class="png-timer-wrap" id="tW">
    <svg class="png-timer-circle" viewBox="0 0 120 120">
      <circle class="png-timer-ring-bg" cx="60" cy="60" r="52"/>
      <circle class="png-timer-ring" id="tR" cx="60" cy="60" r="52"
              stroke-dasharray="326.73" stroke-dashoffset="0"/>
      <text class="png-timer-text" x="60" y="68" text-anchor="middle" id="tN">15</text>
    </svg>
    <div class="png-timer-label">Preparing your download...</div>
  </div>
  <div class="png-dl-ready" id="rW">
    <button class="png-dl-ready-btn" onclick="triggerDL()">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <path d="M22 11.08V12a10 10 0 11-5.93-9.14"/>
        <polyline points="22 4 12 14.01 9 11.01"/>
      </svg>Download Now!
    </button>
  </div>
  <div class="png-share-bar">
    <button class="png-share-btn png-share-wa" onclick="shareWA()">WhatsApp</button>
    <button class="png-share-btn png-share-cp" onclick="copyLink()" id="cpBtn">Copy Link</button>
  </div>
</div>
</div>
<div class="png-item-desc-col">
  <div class="png-content">{desc_html}</div>
  <div class="png-tags">{tags_html}</div>
  {f'<div class="png-related-section"><h2>More {esc(cat_label)} PNG Images</h2><div class="png-related-masonry">{rel_html}</div></div>' if rel_html else ''}
</div>
</div></div></div>
{_footer()}
<script>
var _d="{enc_dl}",_s=15,_pg="{esc(url)}";
function startCD(){{
  document.getElementById('bW').style.display='none';
  document.getElementById('tW').classList.add('active');
  var r=document.getElementById('tR'),n=document.getElementById('tN'),t=326.73,c=_s;
  var iv=setInterval(function(){{
    c--;n.textContent=c;r.style.strokeDashoffset=t*(1-c/_s);
    if(c<=0){{clearInterval(iv);document.getElementById('tW').classList.remove('active');
      document.getElementById('rW').classList.add('active');setTimeout(triggerDL,300);}}
  }},1000);
}}
function triggerDL(){{
  try{{var u=atob(_d);var a=document.createElement('a');a.href=u;a.download='';
    a.style.display='none';document.body.appendChild(a);a.click();
    setTimeout(function(){{document.body.removeChild(a);}},200);}}catch(e){{console.error(e);}}
}}
function shareWA(){{window.open('https://wa.me/?text='+encodeURIComponent({share_text}+_pg),'_blank','noopener');}}
function copyLink(){{navigator.clipboard&&navigator.clipboard.writeText(_pg).then(function(){{
  var b=document.getElementById('cpBtn');b.textContent='Copied!';
  setTimeout(function(){{b.textContent='Copy Link';}},2000);}});}}
</script>
</body></html>"""

def build_category_page(cat, items):
    label = items[0].get("subject_name", cat) if items else cat
    url   = f"{SITE_URL}/png-library/{cat}/"
    img   = items[0].get("preview_url", "") if items else ""
    total = len(items)
    cards = "".join(
        f'<a href="/png-library/{it["category"]}/{it["slug"]}/" '
        f'class="mpng-item-card cat-item" data-pg="{idx // ITEMS_PER_PAGE}" '
        f'title="{esc(it.get("h1",""))}">'
        f'<div class="mpng-item-thumb">'
        + (f'<picture><source srcset="{esc(it.get("webp_preview_url","") or it.get("preview_url_small",""))}" type="image/webp"/><img src="{esc(it.get("preview_url_small",it.get("preview_url","")))}" alt="{esc(it.get("h1",""))}" loading="lazy" width="400" height="400"/></picture>' if it.get("preview_url_small") or it.get("preview_url") else "")
        + f'</div><div class="mpng-item-label">{esc(it.get("h1",""))}</div></a>\n'
        for idx, it in enumerate(items)
    )
    tp  = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    pag = (f'<nav class="pg-nav">'
           f'<button class="pg-btn pg-btn-prev" id="cP" onclick="catPage(_cp-1)" disabled>&#8592; Previous</button>'
           f'<span class="pg-info" id="cI">Page 1 of {tp}</span>'
           f'<button class="pg-btn pg-btn-next" id="cN" onclick="catPage(_cp+1)">Next &#8594;</button>'
           f'</nav>') if tp > 1 else ""
    _pg_title = f"{label} PNG Images Free Download ({total}+) | UltraPNG"
    _pg_desc  = f"Download {total}+ free {label} transparent PNG. HD Photoshop Canva."
    return (f'{_head(_pg_title, _pg_desc, url, img)}\n</head><body>{_header()}\n'
            f'<nav class="breadcrumb"><a href="/">Home</a><span>&rsaquo;</span>'
            f'<a href="/png-library/">PNG Library</a><span>&rsaquo;</span>'
            f'<span>{esc(label)}</span></nav>\n'
            f'<div class="cat-pg-wrap">'
            f'<h1 class="cat-pg-title">{esc(label)} PNG Images <span class="sec-count">({total})</span></h1>'
            f'<div class="png-masonry" id="catMasonry">{cards}</div>{pag}</div>\n'
            f'{_footer()}\n'
            f'<script>var _cp=0,_tp={tp};'
            f'function catPage(p){{if(p<0||p>=_tp)return;_cp=p;'
            f'document.querySelectorAll(".cat-item").forEach(function(c){{'
            f'c.style.display=parseInt(c.dataset.pg||0)===p?"":"none";}});'
            f'var P=document.getElementById("cP"),N=document.getElementById("cN");'
            f'if(P)P.disabled=p===0;if(N)N.disabled=p===_tp-1;'
            f'var I=document.getElementById("cI");if(I)I.textContent="Page "+(p+1)+" of "+_tp;}}'
            f'catPage(0);</script></body></html>')

def build_main_page(all_data):
    url    = f"{SITE_URL}/png-library/"
    by_cat = {}
    for item in all_data:
        by_cat.setdefault(item["category"], []).append(item)
    cats   = sorted(by_cat.keys())
    ti, tc = len(all_data), len(cats)

    cat_cards = "".join(
        f'<a href="/png-library/{cat}/" class="mpng-cat-card" '
        f'data-cat="{esc(by_cat[cat][0].get("subject_name",cat).lower())}" '
        f'data-search="{esc(",".join(set(t.strip() for item in by_cat[cat][:3] for t in item.get("tags","").lower().split(",") if t.strip()))[:200])}">'
        f'<div class="mpng-cat-previews">'
        + "".join(
            f'<img src="{esc(it.get("preview_url_small",it.get("preview_url","")))} " '
            f'alt="{esc(by_cat[cat][0].get("subject_name",cat))}" loading="lazy" '
            f'width="200" height="200" onerror="this.remove()"/>'
            for it in by_cat[cat][:4]
            if it.get("preview_url_small") or it.get("preview_url")
        )
        + f'</div><div class="mpng-cat-footer">'
        f'<span class="mpng-cat-name">{esc(by_cat[cat][0].get("subject_name",cat))}</span>'
        f'<span class="mpng-cat-cnt">{len(by_cat[cat])} images</span>'
        f'</div></a>\n'
        for cat in cats
    )

    recent    = sorted(all_data, key=lambda x: x.get("date_added", ""), reverse=True)[:ITEMS_PER_PAGE * 5]
    rec_cards = "".join(
        f'<a href="/png-library/{it["category"]}/{it["slug"]}/" '
        f'class="mpng-item-card recent-item" data-rpg="{idx // ITEMS_PER_PAGE}">'
        f'<div class="mpng-item-thumb">'
        + (f'<img src="{esc(it.get("preview_url_small",it.get("preview_url","")))}" alt="{esc(it.get("h1",""))}" loading="lazy" width="400" height="400"/>' if it.get("preview_url_small") or it.get("preview_url") else "")
        + f'</div><div class="mpng-item-label">{esc(it.get("h1",""))}</div>'
        + f'<div class="mpng-item-cat">{esc(it.get("subject_name", it["category"]))}</div></a>\n'
        for idx, it in enumerate(recent)
    )

    trp = max(1, (len(recent) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    pag = (f'<nav class="pg-nav">'
           f'<button class="pg-btn pg-btn-prev" id="rP" onclick="recentPage(_rcp-1)" disabled>&#8592; Previous</button>'
           f'<span class="pg-info" id="rI">Page 1 of {trp}</span>'
           f'<button class="pg-btn pg-btn-next" id="rN" onclick="recentPage(_rcp+1)">Next &#8594;</button>'
           f'</nav>') if trp > 1 else ""

    _mp_title = f"UltraPNG {ti}+ Free Transparent PNG Images HD"
    _mp_desc  = f"Download {ti}+ free HD transparent PNG. {tc} categories. No watermark no signup."
    _mp_img   = all_data[0].get("preview_url","") if all_data else ""
    return (f'{_head(_mp_title, _mp_desc, url, _mp_img)}\n</head><body>{_header()}\n'
            f'<div class="mpng-hero">'
            f'<div class="mpng-hero-badge">&#127881; 100% Free &#8212; No Signup &#8212; Updated Daily</div>'
            f'<h1 class="mpng-hero-title">Ultra<span>PNG</span></h1>'
            f'<p class="mpng-hero-sub">Download <strong>{ti}+</strong> free HD transparent PNG. No watermark. No signup.</p>'
            f'<div class="mpng-stats">'
            f'<div class="mpng-stat"><div class="mpng-stat-num">{ti}+</div><div class="mpng-stat-lbl">PNG Images</div></div>'
            f'<div class="mpng-stat"><div class="mpng-stat-num">{tc}</div><div class="mpng-stat-lbl">Categories</div></div>'
            f'<div class="mpng-stat"><div class="mpng-stat-num">100%</div><div class="mpng-stat-lbl">Free</div></div>'
            f'<div class="mpng-stat"><div class="mpng-stat-num">HD</div><div class="mpng-stat-lbl">Quality</div></div>'
            f'</div>'
            f'<div class="mpng-search-wrap">'
            f'<input type="search" id="mpngSearch" '
            f'placeholder="Search PNG... (Fish, Car, Wedding, Flower, Tool...)" '
            f'oninput="filterMpng(this.value)" aria-label="Search PNG images"/>'
            f'</div></div>\n'
            f'<div class="mpng-section"><div class="mpng-section-head">'
            f'<h2 class="mpng-section-title">Browse <span>Categories</span></h2>'
            f'<span>{tc} collections</span></div>'
            f'<div class="mpng-cat-grid" id="mpngCatGrid">{cat_cards}</div></div>\n'
            f'<div class="mpng-section"><div class="mpng-section-head">'
            f'<h2 class="mpng-section-title">Recently <span>Added</span></h2></div>'
            f'<div class="mpng-masonry" id="mpngMasonry">{rec_cards}</div>{pag}</div>\n'
            f'{_footer()}\n'
            f'<script>var _rcp=0,_rtp={trp};'
            f'function filterMpng(q){{q=(q||"").trim().toLowerCase();'
            f'document.querySelectorAll(".mpng-cat-card").forEach(function(c){{'
            f'var n=(c.getAttribute("data-cat")||"").toLowerCase();'
            f'var s=(c.getAttribute("data-search")||"").toLowerCase();'
            f'c.style.display=q.length<2||n.includes(q)||s.includes(q)?"":"none";}});}}'
            f'function recentPage(p){{if(p<0||p>=_rtp)return;_rcp=p;'
            f'document.querySelectorAll(".recent-item").forEach(function(c){{'
            f'c.style.display=parseInt(c.dataset.rpg||0)===p?"":"none";}});'
            f'var P=document.getElementById("rP"),N=document.getElementById("rN");'
            f'if(P)P.disabled=p===0;if(N)N.disabled=p===_rtp-1;'
            f'var I=document.getElementById("rI");if(I)I.textContent="Page "+(p+1)+" of "+_rtp;}}'
            f'recentPage(0);</script></body></html>')

def build_sitemaps(all_data, out_dir):
    today   = datetime.now().strftime("%Y-%m-%d")
    entries = []
    entries.append(
        f'<url><loc>{SITE_URL}/png-library/</loc><lastmod>{today}</lastmod>'
        f'<changefreq>daily</changefreq><priority>0.9</priority></url>')
    for cat in sorted(set(i["category"] for i in all_data)):
        entries.append(
            f'<url><loc>{SITE_URL}/png-library/{cat}/</loc><lastmod>{today}</lastmod>'
            f'<changefreq>weekly</changefreq><priority>0.8</priority></url>')
    for item in all_data:
        img_tag = (f'<image:image><image:loc>{esc(item["preview_url"])}</image:loc>'
                   f'<image:title>{esc(item.get("h1",""))}</image:title></image:image>'
                   if item.get("preview_url") else "")
        entries.append(
            f'<url><loc>{SITE_URL}/png-library/{item["category"]}/{item["slug"]}/</loc>'
            f'<lastmod>{item.get("date_added",today)}</lastmod>'
            f'<changefreq>monthly</changefreq><priority>0.7</priority>{img_tag}</url>')

    ns       = ('xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
                'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"')
    chunks   = [entries[i:i + SITEMAP_MAX_URL] for i in range(0, len(entries), SITEMAP_MAX_URL)]
    sm_files = []
    for idx, chunk in enumerate(chunks, 1):
        fname   = f"sitemap-png-{idx}.xml"
        content = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset {ns}>\n' + "\n".join(chunk) + '\n</urlset>'
        (out_dir / fname).write_text(content, "utf-8")
        sm_files.append(fname)

    today_str = datetime.now().strftime("%Y-%m-%d")
    index     = "\n".join(
        f'<sitemap><loc>{SITE_URL}/{f}</loc><lastmod>{today_str}</lastmod></sitemap>'
        for f in sm_files)
    (out_dir / "sitemap-png.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'{index}\n</sitemapindex>', "utf-8")
    log(f"  Sitemaps: {len(sm_files)} files ({len(entries)} URLs)")

def build_robots_txt(out_dir):
    (out_dir / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\n"
        f"User-agent: GPTBot\nDisallow: /\n\n"
        f"User-agent: ClaudeBot\nDisallow: /\n\n"
        f"User-agent: CCBot\nDisallow: /\n\n"
        f"User-agent: anthropic-ai\nDisallow: /\n\n"
        f"Sitemap: {SITE_URL}/sitemap-png.xml\n", "utf-8")

def build_llms_txt(out_dir):
    (out_dir / "llms.txt").write_text(
        f"# {SITE_NAME}\n\n"
        f"> {SITE_URL} — Free Transparent PNG images\n\n"
        f"## About\nFree HD transparent PNG images. Updated daily. No signup.\n\n"
        f"## Collections\n{SITE_URL}/png-library/\n", "utf-8")

def save_data_split(all_data, data_dir):
    data_dir.mkdir(parents=True, exist_ok=True)
    by_cat = {}
    for item in all_data:
        by_cat.setdefault(item["category"], []).append(item)
    for cat, items in by_cat.items():
        fname = data_dir / f"{cat}.json"
        tmp   = str(fname) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        os.replace(tmp, str(fname))
    (data_dir / "_index.json").write_text(
        json.dumps({cat: len(items) for cat, items in by_cat.items()},
                   ensure_ascii=False, indent=2), "utf-8")
    log(f"  Data saved: {len(by_cat)} category JSON files")

def load_all_data(data_dir):
    all_data = []
    if not data_dir.exists():
        return all_data
    for jf in data_dir.glob("*.json"):
        if jf.name.startswith("_") or jf.name == "png-library.json":
            continue
        try:
            entries = json.loads(jf.read_text("utf-8"))
            if isinstance(entries, list):
                all_data.extend(entries)
        except Exception:
            pass
    return all_data

# ══════════════════════════════════════════════════════════════
# PHASE 5 — HTML Build + Git Push to REPO2
# ══════════════════════════════════════════════════════════════
def phase5_build_push(new_posts):
    log("=" * 56)
    log("PHASE 5: HTML Build + Git Push to REPO2")
    log("=" * 56)

    if not GITHUB_TOKEN or not GITHUB_REPO2:
        log("  WARNING: GITHUB_REPO2 / GITHUB_TOKEN_REPO2 not set — skipping git push")
        log("  (Set GITHUB_REPO2 secret to enable website push)")
        return
    if not new_posts:
        log("No new posts"); return

    repo_url = f"https://x-access-token:{GITHUB_TOKEN}@github.com/{GITHUB_REPO2}.git"

    if REPO2_DIR.exists() and (REPO2_DIR / ".git").exists():
        log("REPO2 exists — pulling latest...")
        try:
            subprocess.run(["git", "pull", "--rebase", "--autostash"],
                           cwd=str(REPO2_DIR), capture_output=True, check=True)
            subprocess.run(["git", "remote", "set-url", "origin", repo_url],
                           cwd=str(REPO2_DIR), capture_output=True)
        except Exception as e:
            log(f"  Pull failed ({e}) — re-cloning...")
            shutil.rmtree(str(REPO2_DIR))
            subprocess.run(["git", "clone", "--depth", "1", repo_url, str(REPO2_DIR)],
                           capture_output=True, check=True)
    else:
        log(f"Cloning REPO2: {GITHUB_REPO2}...")
        subprocess.run(["git", "clone", "--depth", "1", repo_url, str(REPO2_DIR)],
                       capture_output=True, check=True)
        subprocess.run(["git", "remote", "set-url", "origin", repo_url],
                       cwd=str(REPO2_DIR), capture_output=True)

    data_dir = REPO2_DIR / "data"
    all_data = load_all_data(data_dir)
    log(f"Existing entries: {len(all_data)}")

    existing_keys = set(f"{d['category']}/{d['slug']}" for d in all_data)
    added = 0
    for post in new_posts:
        key = f"{post['category']}/{post['slug']}"
        if key not in existing_keys:
            all_data.append(post)
            existing_keys.add(key)
            added += 1
    log(f"Merged: +{added} | Total: {len(all_data)}")

    save_data_split(all_data, data_dir)

    out_dir = REPO2_DIR / "png-library"
    out_dir.mkdir(parents=True, exist_ok=True)
    by_cat = {}
    for item in all_data:
        by_cat.setdefault(item["category"], []).append(item)

    pages_built   = 0
    affected_cats = set(p["category"] for p in new_posts)

    for post in new_posts:
        cat     = post["category"]
        related = [i for i in by_cat.get(cat, []) if i["slug"] != post["slug"]][:24]
        d       = out_dir / cat / post["slug"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(build_item_page(post, related), "utf-8")
        pages_built += 1

    for cat in affected_cats:
        d = out_dir / cat
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(
            build_category_page(cat, by_cat.get(cat, [])), "utf-8")
        pages_built += 1

    (out_dir / "index.html").write_text(build_main_page(all_data), "utf-8")
    pages_built += 1

    build_sitemaps(all_data, REPO2_DIR)
    build_robots_txt(REPO2_DIR)
    build_llms_txt(REPO2_DIR)
    log(f"Pages built: {pages_built}")

    today    = datetime.now().strftime("%Y-%m-%d")
    orig_dir = os.getcwd()
    try:
        os.chdir(str(REPO2_DIR))
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"],
                       check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email",
                        "github-actions[bot]@users.noreply.github.com"],
                       check=True, capture_output=True)
        subprocess.run(["git", "add", "-A"], check=True, capture_output=True)
        diff = subprocess.run(["git", "diff", "--staged", "--quiet"], capture_output=True)
        if diff.returncode != 0:
            msg  = f"PNG Library: +{added} images ({len(all_data)} total) [{today}]"
            subprocess.run(["git", "commit", "-m", msg], check=True, capture_output=True)
            push = subprocess.run(["git", "push"], capture_output=True, text=True)
            if push.returncode == 0:
                log(f"REPO2 pushed! Site: {len(all_data)} images total")
            else:
                log(f"Push failed: {push.stderr[:200]}")
        else:
            log("Nothing to commit.")
    except subprocess.CalledProcessError as e:
        log(f"Git error: {e}")
    finally:
        os.chdir(orig_dir)

# ══════════════════════════════════════════════════════════════
# PHASE 6 — Save Run Logs to REPO1 (visible on GitHub!)
#
# Every run creates: REPO1/logs/YYYY-MM-DD_HH-MM.log
# Latest run: REPO1/logs/latest.log
# Run history table: REPO1/logs/README.md
#
# View logs at: https://github.com/YOUR_REPO/tree/main/logs
# ══════════════════════════════════════════════════════════════
def phase6_save_logs(stats: dict):
    log("=" * 56)
    log("PHASE 6: Saving run logs to REPO1/logs/ (GitHub visible)")
    log("=" * 56)

    token = GITHUB_TOKEN_REPO1 or GITHUB_TOKEN
    if not token or not GITHUB_REPO1:
        log("  No REPO1 token/repo — skipping log save")
        return

    repo_url = f"https://x-access-token:{token}@github.com/{GITHUB_REPO1}.git"

    try:
        if not REPO1_DIR.exists():
            subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, str(REPO1_DIR)],
                capture_output=True, check=True)
        else:
            subprocess.run(["git", "pull", "--rebase", "--autostash"],
                           cwd=str(REPO1_DIR), capture_output=True)
            subprocess.run(["git", "remote", "set-url", "origin", repo_url],
                           cwd=str(REPO1_DIR), capture_output=True)

        logs_dir = REPO1_DIR / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        now      = datetime.now().strftime("%Y-%m-%d_%H-%M")
        log_file = logs_dir / f"{now}.log"

        summary = (
            f"ULTRAPNG PIPELINE V5.5 — RUN REPORT\n"
            f"{'=' * 60}\n"
            f"Date       : {datetime.now().strftime('%Y-%m-%d %H:%M IST')}\n"
            f"Batch      : {START_INDEX} -> {END_INDEX}\n"
            f"Generated  : {stats.get('generated', 0)}\n"
            f"Deleted    : {stats.get('deleted', 0)}  (unreal/deformed by Qwen)\n"
            f"Approved   : {stats.get('approved', 0)}\n"
            f"Transparent: {stats.get('transparent', 0)}\n"
            f"Uploaded   : {stats.get('uploaded', 0)}\n"
            f"Posts      : {stats.get('posts', 0)}\n"
            f"Duration   : {stats.get('duration', '?')}\n"
            f"Status     : {stats.get('status', 'unknown')}\n"
            f"{'=' * 60}\n\n"
            f"FULL LOG\n"
            f"{'=' * 60}\n"
        )
        full_log = summary + "\n".join(_LOG_LINES)
        log_file.write_text(full_log, "utf-8")

        # Keep only last 30 run logs
        all_logs = sorted(logs_dir.glob("????-??-??_??-??.log"))
        for old in all_logs[:-30]:
            old.unlink()

        # latest.log — always overwrite
        (logs_dir / "latest.log").write_text(full_log, "utf-8")

        # README.md — run history table
        readme = logs_dir / "README.md"
        rows   = []
        if readme.exists():
            for line in readme.read_text("utf-8").split("\n"):
                if line.startswith("| 20"):
                    rows.append(line)
        new_row = (
            f"| {now.replace('_',' ')} "
            f"| {stats.get('generated',0)} "
            f"| {stats.get('deleted',0)} "
            f"| {stats.get('approved',0)} "
            f"| {stats.get('uploaded',0)} "
            f"| {stats.get('posts',0)} "
            f"| {stats.get('duration','?')} "
            f"| {stats.get('status','?')} |"
        )
        rows.insert(0, new_row)
        rows = rows[:50]
        readme.write_text(
            "# UltraPNG Pipeline — Run History\n\n"
            "| Date & Time | Generated | Deleted | Approved | Uploaded | Posts | Duration | Status |\n"
            "|-------------|-----------|---------|----------|----------|-------|----------|--------|\n"
            + "\n".join(rows) + "\n", "utf-8")

        # Commit + push
        orig_dir = os.getcwd()
        try:
            os.chdir(str(REPO1_DIR))
            subprocess.run(["git", "config", "user.name", "github-actions[bot]"],
                           check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email",
                            "github-actions[bot]@users.noreply.github.com"],
                           check=True, capture_output=True)
            subprocess.run(["git", "add", "logs/"], check=True, capture_output=True)
            diff = subprocess.run(["git", "diff", "--staged", "--quiet"], capture_output=True)
            if diff.returncode != 0:
                commit_msg = (
                    f"[logs] {now} | "
                    f"gen={stats.get('generated',0)} "
                    f"del={stats.get('deleted',0)} "
                    f"posts={stats.get('posts',0)} "
                    f"| {stats.get('status','?')}"
                )
                subprocess.run(["git", "commit", "-m", commit_msg],
                               check=True, capture_output=True)
                push = subprocess.run(["git", "push"], capture_output=True, text=True)
                if push.returncode == 0:
                    log(f"Logs pushed to REPO1!")
                    log(f"  View: https://github.com/{GITHUB_REPO1}/tree/main/logs")
                else:
                    log(f"  Log push failed: {push.stderr[:100]}")
        finally:
            os.chdir(orig_dir)

    except Exception as e:
        log(f"  Log save error (non-fatal): {e}")

# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
def main():
    t0    = time.time()
    stats = {"status": "running", "generated": 0, "deleted": 0,
             "approved": 0, "transparent": 0, "uploaded": 0, "posts": 0,
             "duration": "?"}

    print("╔══════════════════════════════════════════════════════╗")
    print("║  UltraPNG V5.5 — WORLD BEST PIPELINE               ║")
    print("║  FLUX -> Qwen(Filter+SEO) -> RMBG -> Drive -> Git  ║")
    print("╚══════════════════════════════════════════════════════╝")
    print(f"  Batch  : {START_INDEX} -> {END_INDEX} ({END_INDEX-START_INDEX} prompts)")
    print(f"  REPO2  : {GITHUB_REPO2}")
    if torch.cuda.is_available():
        p = torch.cuda.get_device_properties(0)
        print(f"  GPU    : {p.name} | VRAM: {p.total_memory/1e9:.0f}GB")
    print()

    # ── Dataset path check ──────────────────────────────────
    print("  Dataset model paths:")
    for _lbl, _pth in [("FLUX  ", FLUX_DIR), ("Qwen  ", QWEN_DIR), ("RMBG  ", RMBG_ONNX)]:
        _ok = Path(_pth).exists()
        print(f"    {'✅' if _ok else '❌'} {_lbl}: {_pth}")
        if _ok and Path(_pth).is_dir():
            _sub = sorted(p.name for p in Path(_pth).iterdir())
            print(f"         └─ {_sub}")
    if MODELS_DIR.exists():
        _top = sorted([p.name for p in MODELS_DIR.iterdir()])
        print(f"    📂 Dataset top-level: {_top}")
    else:
        print(f"    ❌ MODELS_DIR missing: {MODELS_DIR}")
        print(f"       → Fix: Add 'my-pipeline-models' dataset to this notebook via Kaggle UI!")
    print()

    try:
        prompts = load_prompts()
        if not prompts:
            raise Exception("No prompts loaded!")

        batch = prompts[START_INDEX:END_INDEX]
        log(f"Batch: {len(batch)} prompts\n")

        send_telegram(
            f"<b>UltraPNG V5.5 Started</b>\n"
            f"Batch: <code>{START_INDEX} -> {END_INDEX}</code> ({len(batch)} prompts)\n"
            f"{datetime.now().strftime('%Y-%m-%d %H:%M IST')}"
        )

        skip_set  = load_skip_set_from_json()

        # PHASE 1: Generate
        generated = phase1_generate(batch, skip_set)
        stats["generated"] = len(generated)
        if not generated:
            send_telegram("Pipeline stopped: No new images generated.")
            return

        send_telegram(f"Phase 1 done. Generated: <code>{len(generated)}</code>")

        # PHASE 2: Qwen Single Pass (Filter + SEO)
        posts = phase2_qwen_filter_seo(generated)
        stats["approved"] = len(posts)
        stats["deleted"]  = len(generated) - len(posts)
        if not posts:
            send_telegram("Pipeline stopped: All images deleted by Qwen.")
            return

        send_telegram(
            f"Phase 2 done (Qwen).\n"
            f"Kept: <code>{len(posts)}</code> | "
            f"Deleted (unreal): <code>{stats['deleted']}</code>"
        )

        # PHASE 3: Background removal
        transparent = phase3_bg_remove(posts)
        stats["transparent"] = len(transparent)
        if not transparent:
            send_telegram("Pipeline stopped: BG removal failed.")
            return

        send_telegram(f"Phase 3 done. Transparent PNGs: <code>{len(transparent)}</code>")

        # PHASE 4: Upload to Drive
        uploaded = phase4_upload(transparent)
        stats["uploaded"] = len(uploaded)
        if not uploaded:
            send_telegram("Pipeline stopped: Drive upload failed.")
            return

        send_telegram(f"Phase 4 done. Uploaded to Drive: <code>{len(uploaded)}</code>")

        # PHASE 5: Build HTML + push to REPO2
        phase5_build_push(uploaded)
        stats["posts"] = len(uploaded)

        # Clear checkpoints
        for ck in CHECKPOINT_DIR.glob("*.json"):
            ck.unlink()

        hrs = (time.time() - t0) / 3600
        stats["duration"] = f"{hrs:.1f}h"
        stats["status"]   = "SUCCESS"

        print(f"\n╔══════════════════════════════════════════════════════╗")
        print(f"║  DONE in {hrs:.1f}h")
        print(f"║  Gen:{len(generated)} Del:{stats['deleted']} OK:{len(posts)}")
        print(f"║  Trans:{len(transparent)} Up:{len(uploaded)}")
        print(f"╚══════════════════════════════════════════════════════╝")

        send_telegram(
            f"<b>UltraPNG V5.5 COMPLETE!</b>\n"
            f"Time: <code>{hrs:.1f}h</code>\n"
            f"Generated: <code>{len(generated)}</code>\n"
            f"Deleted (unreal): <code>{stats['deleted']}</code>\n"
            f"Approved: <code>{len(posts)}</code>\n"
            f"Uploaded: <code>{len(uploaded)}</code>\n"
            f"Site: {SITE_URL}/png-library/\n"
            f"Logs: https://github.com/{GITHUB_REPO1}/tree/main/logs"
        )

    except Exception as e:
        hrs = (time.time() - t0) / 3600
        stats["duration"] = f"{hrs:.1f}h"
        stats["status"]   = f"FAILED: {str(e)[:80]}"
        log(f"FATAL: {e}")
        send_telegram(
            f"<b>UltraPNG V5.5 FAILED!</b>\n"
            f"Error: <code>{str(e)[:300]}</code>\n"
            f"Logs: https://github.com/{GITHUB_REPO1}/tree/main/logs"
        )
        raise
    finally:
        phase6_save_logs(stats)

if __name__ == "__main__":
    main()
