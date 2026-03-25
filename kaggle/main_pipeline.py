"""
╔══════════════════════════════════════════════════════════════╗
║   UltraPNG.com — PNG Library Pipeline V7.0                  ║
╠══════════════════════════════════════════════════════════════╣
║  PHASE 1 → FLUX.2-Klein-4B   Generate 1024x1024 images     ║
║  PHASE 2 → NO QWEN (NO SEO)                              ║
║  PHASE 3 → RMBG-2.0 ONNX    Background removal (GPU)       ║
║  PHASE 4 → Google Drive      Upload PNG + WebP             ║
║  PHASE 5 → Update ultradata.xlsx (NO JSON push)           ║
║  PHASE 6 → Save Run Logs → REPO1 (visible on GitHub!)      ║
╠══════════════════════════════════════════════════════════════╣
║  V7.0 CHANGES:                                              ║
║  • No Qwen / No SEO in Kaggle Section 1                     ║
╚══════════════════════════════════════════════════════════════╝

inject_creds.py prepends os.environ[] lines before this file.
"""

import os, sys, json, time, gc, re, io, shutil, base64, subprocess, math
from pathlib import Path
from datetime import datetime

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

# ── HuggingFace cache dir (writable in Kaggle) ────────────────
HF_CACHE = Path("/kaggle/working/hf_cache")
HF_CACHE.mkdir(parents=True, exist_ok=True)
os.environ["HF_HOME"]               = str(HF_CACHE)
os.environ["HUGGINGFACE_HUB_CACHE"] = str(HF_CACHE)
os.environ["TRANSFORMERS_CACHE"]    = str(HF_CACHE)
# Set HF token if available (faster downloads, no rate limits)
_hf_token = os.environ.get("HF_TOKEN", "")
if _hf_token:
    os.environ["HUGGINGFACE_HUB_TOKEN"] = _hf_token

# ══════════════════════════════════════════════════════════════
# HuggingFace Model IDs  ← change here if repo name differs
# ══════════════════════════════════════════════════════════════
FLUX_HF_ID = "black-forest-labs/FLUX.2-klein-4B"
RMBG_HF_ID = "ZhengPeng7/BiRefNet_HR"  # Highest quality: 2048x2048 trained, public MIT, no gating, verified working

# ══════════════════════════════════════════════════════════════
# GLOBAL LOG CAPTURE
# ══════════════════════════════════════════════════════════════
_LOG_LINES = []

def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    _LOG_LINES.append(line)

# ── Install deps ──────────────────────────────────────────────
print("=" * 56)
print("Installing dependencies...")
PKGS = [
    "git+https://github.com/huggingface/diffusers.git",
    "transformers>=4.47.0",
    "accelerate>=0.28.0", "sentencepiece",
    "huggingface_hub>=0.23.0",
    "Pillow>=10.0", "numpy", "requests",
    "onnxruntime-gpu", "torchvision",
    "opencv-python-headless", "piexif",
    "openpyxl",
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
START_INDEX          = int(float(os.environ.get("START_INDEX", "0").strip()))
END_INDEX            = int(float(os.environ.get("END_INDEX", "200").strip()))

SITE_URL        = "https://www.ultrapng.com"
SITE_NAME       = "UltraPNG"
WATERMARK_TEXT  = "www.ultrapng.com"
ITEMS_PER_PAGE  = 24

SITEMAP_MAX_URL = 45000

# ══════════════════════════════════════════════════════════════
# CATEGORY ENHANCERS — prompt quality boost per category
# ══════════════════════════════════════════════════════════════
CATEGORY_ENHANCERS = {
    "indian_foods":     ", appetizing food styling, steam visible, glistening surface",
    "food_indian":      ", appetizing food styling, steam visible, glistening surface",
    "world_foods":      ", appetizing food styling, steam visible, glistening sauce",
    "food_world":       ", appetizing food styling, steam visible, glistening sauce",
    "fruits":           ", natural skin texture, juice droplets",
    "vegetables":       ", natural surface texture, fresh harvest quality",
    "flowers":          ", petal vein detail, natural color saturation",
    "jewellery_models": ", gem facet reflections, gold metal mirror finish",
    "jewellery":        ", gem facet reflections, gold metal mirror finish",
    "vehicles":         ", automotive paint reflection, chrome detail",
    "vehicles_cars":    ", automotive paint reflection, chrome detail",
    "vehicles_bikes":   ", automotive paint reflection, chrome detail",
    "poultry_animals":  ", fur and feather strand detail, catchlight in eyes",
    "animals":          ", fur and feather strand detail, catchlight in eyes",
    "raw_meat":         ", fresh meat texture, glistening moist surface",
    "cool_drinks":      ", condensation droplets, liquid transparency",
    "beverages":        ", condensation droplets, liquid transparency",
    "footwear":         ", leather grain, stitching detail",
    "shoes":            ", leather grain, stitching detail",
    "indian_dress":     ", fabric weave, embroidery thread detail",
    "clothing":         ", fabric weave, embroidery thread detail",
    "office_models":    ", professional portrait, sharp clothing detail",
}

def enhance_prompt(raw_prompt, category):
    cat = (category or "").lower()
    for key, extra in CATEGORY_ENHANCERS.items():
        if cat.startswith(key) or key in cat:
            return raw_prompt + extra
    return raw_prompt

# ══════════════════════════════════════════════════════════════
# UTILITIES
# ══════════════════════════════════════════════════════════════
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
                piexif.ImageIFD.Software:  b"UltraPNG Pipeline V6.0",
            }
        })
        jpg_buf = io.BytesIO()
        bg.save(jpg_buf, "JPEG", quality=85, optimize=True, exif=exif_bytes)
        webp_buf = io.BytesIO()
        bg.save(webp_buf, "WEBP", quality=82, method=4)
    return jpg_buf.getvalue(), webp_buf.getvalue(), w, h

# ══════════════════════════════════════════════════════════════
# SKIP SET
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
            subprocess.run(["git", "sparse-checkout", "init", "--cone"],
                           cwd=str(REPO2_DIR), capture_output=True, check=True)
            subprocess.run(["git", "sparse-checkout", "set", "data"],
                           cwd=str(REPO2_DIR), capture_output=True, check=True)
        except Exception:
            log("  Skip-set: REPO2 empty — starting fresh")
            return skip_set
    data_dir = REPO2_DIR / "data"
    if not data_dir.exists():
        log("  No data dir — starting fresh")
        return skip_set
    for jf in data_dir.glob("*.json"):
        if jf.name.startswith("_"):
            continue
        try:
            for e in json.loads(jf.read_text("utf-8")):
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
# PHASE 1 — FLUX.2-Klein-4B  (loads from HuggingFace)
# ══════════════════════════════════════════════════════════════
def phase1_generate(batch, skip_set):
    ckpt = load_checkpoint("phase1_generated")
    if ckpt:
        return ckpt

    log("=" * 56)
    log("PHASE 1: FLUX.2-Klein-4B — Image Generation")
    log(f"  Loading from HuggingFace: {FLUX_HF_ID}")
    log("=" * 56)

    from diffusers import Flux2KleinPipeline

    log(f"  Loading: {FLUX_HF_ID}")
    log("  (First run: downloads ~8GB — ~5 min)")
    pipe = Flux2KleinPipeline.from_pretrained(
        FLUX_HF_ID,
        torch_dtype=torch.bfloat16,
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

            gen    = torch.Generator("cpu").manual_seed(item["seed"])
            prompt = enhance_prompt(item["prompt"], item.get("category", ""))
            img = pipe(
                prompt=prompt,
                num_inference_steps=4,
                guidance_scale=1.0,
                height=1024, width=1024,
                generator=gen,
            ).images[0]

            # Blank image check
            arr    = np.array(img)
            n_px   = arr.shape[0] * arr.shape[1]
            thresh = int(n_px * 0.003)
            if arr.std() < 5 or (arr < 250).sum() < thresh:
                log(f"  Retry (blank): {fname}")
                gen2 = torch.Generator("cpu").manual_seed(item["seed"] + 99)
                img  = pipe(
                    prompt=prompt,
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

    log("\n  Deleting FLUX.2 -> freeing VRAM + disk cache...")
    del pipe
    free_memory()

    # Delete FLUX HF cache to free ~8GB disk for Qwen download
    import shutil as _shutil
    for _cache_sub in HF_CACHE.iterdir():
        if _cache_sub.is_dir():
            _name = _cache_sub.name.lower()
            if "flux" in _name or "black-forest" in _name:
                _shutil.rmtree(str(_cache_sub), ignore_errors=True)
                log(f"  Deleted FLUX cache: {_cache_sub.name}")
    _used = sum(f.stat().st_size for f in HF_CACHE.rglob("*") if f.is_file()) / 1e9
    log(f"  HF cache after cleanup: {_used:.1f}GB")

    save_checkpoint("phase1_generated", generated)
    log(f"PHASE 1 DONE — Generated: {len(generated)} | Skipped: {skipped}\n")
    return generated

# ══════════════════════════════════════════════════════════════
# SECTION 1 — No-Qwen Preparation (subject + approved copies)
# ══════════════════════════════════════════════════════════════
def _title_case_words(s):
    s = re.sub(r"\s+", " ", str(s or "").strip())
    if not s:
        return ""
    return " ".join(w[:1].upper() + w[1:].lower() if w else "" for w in s.split(" "))

def extract_subject_name_from_prompt(prompt, category):
    """
    Heuristic to convert the generated prompt into a human-readable subject name.
    Example: "chicken biryani in bowl, on white plate, front view, ..." →
             "Chicken Biryani With White Plate"
    """
    prompt = str(prompt or "")
    parts = [p.strip() for p in prompt.split(",") if p.strip()]
    first = parts[0] if parts else ""

    # Remove leading count words (if any)
    first = re.sub(r"^(single|two|three|four|five|pair|group of|a|an|the)\s+", "", first, flags=re.I).strip()

    # For food-like prompts, the first chunk often ends with "in bowl"/"on plate" etc.
    core = re.split(r"\s+(in|on)\s+", first, maxsplit=1, flags=re.I)[0].strip() if first else ""

    # Extract vessel from next chunk: typically "on white plate" / "in steel thali" / etc.
    vessel = ""
    for p in parts[1:3]:
        m = re.match(r"^(on|in)\s+(.+)$", p, flags=re.I)
        if m:
            vessel = m.group(2).strip()
            break

    # Strip common view tokens from core for non-food categories.
    core = re.sub(
        r"(front view|side view|side profile|top view|overhead|close-?up|macro|full body|eye level|3/4|three quarter|45 degree.*)$",
        "",
        core,
        flags=re.I,
    ).strip()
    core = re.sub(r"\bwhole\b$", "", core, flags=re.I).strip()

    if core:
        core_tc = _title_case_words(core)
    else:
        core_tc = _title_case_words(category.replace("-", " ").replace("_", " "))

    if vessel:
        # Remove view tokens from vessel chunk too (just in case).
        vessel = re.sub(
            r"(front view|side view|side profile|top view|overhead|close-?up|macro|full body|eye level|3/4|three quarter|45 degree.*)$",
            "",
            vessel,
            flags=re.I,
        ).strip()
        vessel_tc = _title_case_words(vessel)
        if vessel_tc:
            return f"{core_tc} With {vessel_tc}"
    return core_tc

def phase2_prepare_posts_no_model(generated):
    """
    Convert Phase 1 outputs into Phase 3/4 inputs without model filtering/SEO.
    This keeps Flux + RMBG code untouched.
    """
    posts = []
    for item_data in generated:
        item = item_data["item"]
        category = item["category"]
        subcategory = item.get("subcategory", "general")
        prompt = item.get("prompt", "")
        subject_name = extract_subject_name_from_prompt(prompt, category)
        slug = slugify(subject_name)

        src_path = Path(item_data["path"])
        rel = src_path.relative_to(GENERATED_DIR)
        approved_path = APPROVED_DIR / rel
        approved_path.parent.mkdir(parents=True, exist_ok=True)
        if not approved_path.exists():
            shutil.copy2(str(src_path), str(approved_path))

        posts.append({
            "category": category,
            "subcategory": subcategory,
            "subject_name": subject_name,
            "filename": item["filename"],
            "original_prompt": prompt,
            "slug": slug,
            "approved_path": str(approved_path),

            # Placeholders filled by later phases
            "png_file_id": "",
            "jpg_file_id": "",
            "webp_file_id": "",
            "download_url": "",
            "webp_download_url": "",
            "preview_url": "",
            "preview_url_small": "",
            "webp_preview_url": "",
            "preview_w": 800,
            "preview_h": 800,
            "date_added": datetime.now().strftime("%Y-%m-%d"),
        })
    return posts

def update_ultradata_xlsx_from_uploaded(uploaded_posts):
    """
    Append each run into ultradata.xlsx (sheet name: `ultradata`) in repo root.
    Uses low API calls by doing a single XLSX commit at the end.
    """
    if not uploaded_posts:
        return

    token = GITHUB_TOKEN_REPO1 or GITHUB_TOKEN
    if not token or not GITHUB_REPO1:
        log("  WARNING: GITHUB_REPO1 / GITHUB_TOKEN_REPO1 not set — skipping ultradata.xlsx update")
        return

    try:
        import openpyxl
    except Exception as e:
        log(f"  WARNING: openpyxl missing ({e}) — skipping ultradata.xlsx update")
        return

    # Ensure we have a writable clone of the repo root
    repo_url = f"https://x-access-token:{token}@github.com/{GITHUB_REPO1}.git"
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)

    if not (PROJECT_DIR / ".git").exists():
        subprocess.run(["git", "clone", "--depth", "1", repo_url, str(PROJECT_DIR)],
                       check=True, capture_output=True)
    else:
        subprocess.run(["git", "remote", "set-url", "origin", repo_url],
                       cwd=str(PROJECT_DIR), check=True, capture_output=True)

    subprocess.run(["git", "config", "user.name", "github-actions[bot]"],
                   cwd=str(PROJECT_DIR), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email",
                    "github-actions[bot]@users.noreply.github.com"],
                   cwd=str(PROJECT_DIR), check=True, capture_output=True)

    xlsx_path = PROJECT_DIR / "ultradata.xlsx"

    headers = [
        "subject_name",
        "category",
        "subcategory",
        "filename",
        "slug",
        "download_url",
        "webp_download_url",
        "preview_url",
        "preview_url_small",
        "webp_preview_url",
        "png_file_id",
        "webp_file_id",
        "date_added",
    ]

    if xlsx_path.exists():
        wb = openpyxl.load_workbook(str(xlsx_path))
        if "ultradata" in wb.sheetnames:
            ws = wb["ultradata"]
        else:
            ws = wb.active
            ws.title = "ultradata"
    else:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "ultradata"
        ws.append(headers)

    # Map header → column index (1-based)
    existing_header = [c.value for c in ws[1][:len(headers)]]
    if not existing_header or any(h not in existing_header for h in headers):
        ws.delete_rows(1, ws.max_row)
        ws.append(headers)

    col_idx = {h: i + 1 for i, h in enumerate(headers)}
    filename_col = col_idx["filename"]

    existing_filenames = set()
    for row in ws.iter_rows(min_row=2, values_only=True):
        fn = row[filename_col - 1] if row and len(row) >= filename_col else ""
        if fn:
            existing_filenames.add(str(fn))

    added = 0
    for p in uploaded_posts:
        fn = p.get("filename", "")
        if not fn or str(fn) in existing_filenames:
            continue
        ws.append([
            p.get("subject_name", ""),
            p.get("category", ""),
            p.get("subcategory", ""),
            p.get("filename", ""),
            p.get("slug", ""),
            p.get("download_url", ""),
            p.get("webp_download_url", ""),
            p.get("preview_url", ""),
            p.get("preview_url_small", ""),
            p.get("webp_preview_url", ""),
            p.get("png_file_id", ""),
            p.get("webp_file_id", ""),
            p.get("date_added", datetime.now().strftime("%Y-%m-%d")),
        ])
        existing_filenames.add(str(fn))
        added += 1

    if added == 0:
        log("  ultradata.xlsx: no new rows to add")
        return

    tmp_path = str(xlsx_path) + ".tmp"
    wb.save(tmp_path)
    os.replace(tmp_path, str(xlsx_path))

    diff_check = subprocess.run(["git", "diff", "--quiet", "--", "ultradata.xlsx"],
                                 cwd=str(PROJECT_DIR), capture_output=True)
    if diff_check.returncode == 0:
        log("  ultradata.xlsx unchanged after diff check — skipping commit")
        return

    subprocess.run(["git", "add", "ultradata.xlsx"], cwd=str(PROJECT_DIR), check=True, capture_output=True)
    msg = f"Update ultradata: +{added} entries ({datetime.now().strftime('%Y-%m-%d')})"
    subprocess.run(["git", "commit", "-m", msg], cwd=str(PROJECT_DIR), check=True, capture_output=True)
    push = subprocess.run(["git", "push"], cwd=str(PROJECT_DIR), capture_output=True, text=True)
    if push.returncode == 0:
        log(f"  ultradata.xlsx pushed! +{added} entries")
    else:
        log(f"  ultradata.xlsx push failed: {push.stderr[:300]}")

# ══════════════════════════════════════════════════════════════
# PHASE 2 — Qwen2.5-VL-3B SINGLE PASS: Filter + SEO
# ══════════════════════════════════════════════════════════════
CATEGORY_GROUP_MAP = [
    (["animal","bird","insect","fish","seafood","poultry","reptile",
      "butterfly","eagle","parrot","chicken","hen","cock",
      "goat","cow","buffalo","dog","cat","elephant","tiger","lion",
      "deer","rabbit","horse","camel","bear","monkey","snake",
      "crab","prawn","shrimp","lobster","squid","octopus",
      "tilapia","salmon","tuna","rohu","catla"], "animals"),
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
    (["fruit","vegetable","herb","spice","nut","dry_fruit",
      "ayurvedic","herbal"], "produce"),
    (["flower","plant","tree","leaf","nature","botanical",
      "garden","forest","sky","celestial","nature_tree",
      "sky_celestial"], "nature"),
    (["tool","hardware","equipment","machine","instrument",
      "kitchen","vessel","pot","pan","utensil","kitchen_vessel",
      "pots_vessel"], "tools"),
    (["jewel","jewelry","jewellery","necklace","ring","bangle",
      "earring","bracelet","watch","bag","purse","handbag",
      "shoe","footwear","sandal","slipper","boot","heel",
      "cloth","dress","saree","lehenga","kurta","shirt",
      "indian_dress","clothing"], "fashion"),
    (["electronic","mobile","phone","laptop","computer","tablet",
      "accessory","cable","charger","earphone","speaker",
      "computer_accessory","mobile_accessory"], "electronics"),
    (["clipart","icon","logo","badge","frame","border","pattern",
      "texture","offer","effect","festival","pooja","background",
      "abstract","text_effect","music","stationery","office",
      "sport","vehicle","car","bike","medical","furniture",
      "frames_border","offer_logo"], "design"),
]

def _get_category_group(category):
    cat = category.lower()
    for keywords, group in CATEGORY_GROUP_MAP:
        if any(kw in cat for kw in keywords):
            return group
    return "general"

GROUP_CHECK_RULES = {
    "animals": """STRICT ANIMAL QUALITY INSPECTION — DELETE if ANY of these are true:

BODY & SHAPE DEFECTS (check every part carefully):
✗ Extra or missing legs (e.g. dog with 3 legs or 6 legs)
✗ Extra or missing heads (two heads fused together or half-head)
✗ Fused body parts — legs merged into a blob, wings fused to body
✗ Distorted or melted body shape — body looks like a bag or blob
✗ Extra limbs growing from wrong locations (leg from back, arm from neck)
✗ Floating disconnected body parts visible
✗ Tail growing from wrong position or multiple tails
✗ Incorrect number of eyes, ears, or horns for the species
✗ Face melted or unrecognizable — eyes/nose/mouth merged or missing

FACE QUALITY:
✗ Face is a blob — no clear eyes, nose, mouth visible
✗ Eyes are asymmetric blobs or both eyes on same side
✗ Mouth wide open in unnatural way showing wrong teeth/tongue structure
✗ Skull shape is wrong for the species

SPECIES MISMATCH:
✗ Completely different animal than expected (cat when dog expected)
✗ Cooked/dead version when live animal expected
✗ Cartoon/human hybrid that lost animal identity

KEEP even if:
✓ Cartoon or illustrated style (if body shape is correct)
✓ Group of same species animals
✓ Different pose, angle, or color variety
✓ Baby or young version of expected animal

Add these to your evaluation: "shape_match", "face_match", "limb_count_ok"
Set shape_match=false if body is blob/deformed. Set face_match=false if face is unrecognizable.""",

    "food": """STRICT FOOD QUALITY INSPECTION — DELETE if ANY of these are true:

FOOD APPEARANCE DEFECTS:
✗ Food looks rotten, moldy, or decomposed
✗ Food is completely unrecognizable as any dish
✗ Wrong food type — pizza shown when biryani expected
✗ Raw ingredients shown when cooked dish expected (or vice versa)
✗ Food has unnatural colors (blue meat, green bread unless intentional)
✗ Dish shape is a blob — no visible food structure or texture
✗ Multiple unrelated foods merged into one blob
✗ Plate/bowl has impossible shape or is melted

QUALITY DEFECTS:
✗ Food texture looks plastic, rubber, or artificial
✗ Extreme pixelation making food unrecognizable
✗ Food floating in mid-air with no plate/surface context

KEEP even if:
✓ Different plating style for the same dish
✓ Artistic or illustrated style food
✓ Viewed from unusual angle if still recognizable
✓ Different sauce color or spice level""",

    "produce": """STRICT PRODUCE QUALITY INSPECTION — DELETE if ANY of these are true:

FRUIT/VEGETABLE DEFECTS:
✗ Severely rotten or decomposed fruit/vegetable
✗ Fruit has impossible shape — melted, blobby, or fused mass
✗ Wrong produce entirely (apple when mango expected)
✗ Fruit and vegetable merged into unrecognizable hybrid
✗ Skin/texture is smooth blob with no natural surface detail
✗ Multiple different fruits fused together into one object
✗ Completely flat 2D looking with no volume

KEEP even if:
✓ Different color variety of same fruit (green apple instead of red)
✓ Cut or sliced version of expected fruit
✓ Multiple pieces of same fruit
✓ Slightly bruised but still recognizable
✓ Illustrated or cartoon style""",

    "nature": """STRICT NATURE QUALITY INSPECTION — DELETE if ANY of these are true:

FLOWER/PLANT DEFECTS:
✗ Flower petals are blobs with no petal structure
✗ Completely wrong plant — tree shown when flower expected
✗ Petals fused into a single melted mass
✗ Stem is absent when it should be present
✗ Multiple plant species fused into one unnatural hybrid
✗ Completely unrecognizable as any plant

KEEP even if:
✓ Different color of same flower
✓ Different stage of bloom (bud vs open flower)
✓ Artistic or illustrated style
✓ Multiple flowers of same species""",

    "tools": """STRICT TOOLS/KITCHEN QUALITY INSPECTION — DELETE if ANY of these are true:

TOOL DEFECTS:
✗ Tool shape is a blob — no functional parts visible
✗ Handle and head merged into unrecognizable mass
✗ Wrong tool entirely (knife when spoon expected)
✗ Tool has impossible geometry — melted or twisted beyond recognition
✗ Kitchen vessel has no opening or impossible shape
✗ Multiple different tools fused together

KEEP even if:
✓ Different design or material of same tool
✓ Viewed from unusual angle if still recognizable
✓ Illustrated or stylized version""",

    "fashion": """STRICT FASHION QUALITY INSPECTION — DELETE if ANY of these are true:

FASHION ITEM DEFECTS:
✗ Garment is a shapeless blob with no recognizable structure
✗ Wrong item entirely (saree when shirt expected)
✗ Shoes/bags fused into unrecognizable mass
✗ Jewelry has no visible gems, links, or structure
✗ Garment has impossible shape — sleeves from wrong places
✗ Fabric texture looks like rubber or plastic blob

KEEP even if:
✓ Different color or style of same garment type
✓ On a model vs standalone
✓ Different embroidery pattern or material""",

    "electronics": """STRICT ELECTRONICS QUALITY INSPECTION — DELETE if ANY of these are true:

ELECTRONICS DEFECTS:
✗ Device is a blob — no screen, buttons, or ports visible
✗ Wrong device entirely (phone when laptop expected)
✗ Screen and body melted into one mass
✗ Device has impossible shape — completely deformed
✗ Multiple different devices fused together

KEEP even if:
✓ Different brand or model of same device type
✓ Illustrated or cartoon version
✓ Viewed from different angle""",

    "design": """STRICT DESIGN/LOGO/CLIPART QUALITY INSPECTION — DELETE if ANY of these are true:

DESIGN DEFECTS:
✗ Completely blank or pure white/black image with no content
✗ Pure noise with no recognizable graphic element
✗ Wrong category entirely — photo when logo expected
✗ Text is completely unreadable blob
✗ Graphic elements are all merged into one mud-colored blob
✗ Frame/border has no clear edge structure

KEEP even if:
✓ Simple or minimal design
✓ Different color scheme
✓ Slightly abstract if category is "effects" or "abstract" """,

    "general": """STRICT GENERAL QUALITY INSPECTION — DELETE if ANY of these are true:

✗ Completely blank or empty image
✗ Image is pure noise or random pixels with no subject
✗ Expected subject is completely absent from image
✗ Subject is an unrecognizable blob — no defining features
✗ Wildly different object than expected (no resemblance)

KEEP even if:
✓ Artistic or illustrated style
✓ Different pose or angle
✓ Background elements present""",
}

def _build_disabled_prompt(item, subject, category, slug_base):
    raise RuntimeError("Model filter is fully disabled. This helper must not be called.")
    return f"""You are an ULTRA-STRICT quality inspector AND SEO writer for UltraPNG.com — a free transparent PNG library.

IMAGE PROMPT USED: "{item.get('prompt', '')}"
EXPECTED SUBJECT: {subject}
CATEGORY: {category} | GROUP: {group}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 1 — SUBJECT MATCH (Most Important)
Check: does the image show "{subject}"?
- Completely different subject → subject_match: false → DELETE immediately
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 2 — DETAILED QUALITY CHECK
{check_rule}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 3 — CONFIDENCE SCORE (0-10)
9-10: Perfect — all body parts correct, clear subject, professional quality
7-8: Good — minor imperfections, subject clearly recognizable
5-6: Borderline/Poor — noticeable defects (MUST DELETE)
0-4: Wrong/Deformed — major defects (MUST DELETE)
RULE: confidence < 7 → verdict = DELETE (STRICT — borderline = DELETE)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 4 — VERDICT
DELETE if: subject_match=false OR any quality defect found OR confidence < 7
KEEP only if: subject correct AND no body/shape defects AND confidence >= 7
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 5 — SEO (only if KEEP; if DELETE return empty strings for all SEO fields)

Return ONLY valid JSON, no markdown, no extra keys:
{{
  "subject_match": true or false,
  "shape_match": true or false,
  "confidence": 0-10,
  "verdict": "KEEP" or "DELETE",
  "reason": "specific defect found if DELETE (e.g. extra leg on right side, face is blob, wrong species), else empty string",
  "title": "UNIQUE 20+ words — {subject} + 2-3 specific visual details (color/style/angle/texture) seen in THIS image + Transparent PNG HD Free Download | UltraPNG",
  "slug": "SLUG RULES: max 55 chars, lowercase hyphens only. MUST include 2-3 visual detail words seen in THIS image. NEVER use filename. NEVER use only subject name alone. Format: {slug_base}-[color-or-style]-[visual-detail]-png-hd. Examples: golden-ripe-mango-closeup-png-hd, red-crab-side-view-claws-png-hd, white-jasmine-bouquet-fresh-png-hd",
  "meta_desc": "max 155 chars — describe THIS specific image uniquely with color, style, use case. For free download at UltraPNG.",
  "h1": "UNIQUE — color + style + subject + context visible in image. Example: Fresh Red Crab Side View Transparent PNG HD",
  "tags": "18 comma-separated tags — subject name, specific color, style, material, 3 use cases, PNG free, transparent PNG, canva, flex banner, social media, ultrapng, HD, free download, background removed",
  "description": "Write 300-400 UNIQUE words about THIS specific image only. Structure exactly:\n\n## About This {subject} PNG Image\n80-100 words: describe exactly what you SEE — color, style, angle, texture, mood. Start with the most striking visual detail. NEVER start with This high-quality.\n\n## Best Uses for This Image\n60-80 words: specific creative uses for THIS image — flex banner, Canva, social media, invitation cards, packaging.\n\n## Technical Quality\n50-60 words: transparent background, RMBG-2.0 processing, HD resolution, clean alpha channel, print-ready.\n\n## Design Ideas\n- [specific use case 1, 10-12 words]\n- [specific use case 2, 10-12 words]\n- [specific use case 3, 10-12 words]\n- [specific use case 4, 10-12 words]\n- [specific use case 5, 10-12 words]\n\n## FAQ\n**Is this {subject} PNG free?** Yes — 100% free, no signup, no watermark on download.\n**Can I use this in Canva?** Yes. Upload via My Files in Canva and drag to canvas."
}}

ABSOLUTE RULES:
- Return ONLY the JSON object — no text before or after
- No duplicate keys in JSON
- DELETE scores 0-6 — ONLY keep 7, 8, 9, 10
- Reason MUST name the specific defect (e.g. "3 legs instead of 4", "face is unrecognizable blob", "extra head on back")
- Slug MUST contain visual detail words from THIS image, not just the subject name
- Description MUST be 300-400 words unique to THIS image"""

def phase2_disabled_filter_seo(generated):
    raise RuntimeError("Model filter is fully disabled. This phase must not be called.")

    log("=" * 56)
    log("PHASE 2: Qwen2.5-VL-3B — SMART FILTER + SEO")
    log(f"  Loading from HuggingFace: {QWEN_HF_ID}")
    log("=" * 56)

    if not generated:
        return []

    from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
    from disabled_vl_utils import process_vision_info

    processor = AutoProcessor.from_pretrained(
        QWEN_HF_ID, use_fast=True, cache_dir=str(HF_CACHE))
    model     = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        QWEN_HF_ID,
        torch_dtype=torch.float16,
        device_map="auto",
        cache_dir=str(HF_CACHE),
    )
    model.eval()
    log(f"Qwen loaded! Processing {len(generated)} images...\n")

    posts, deleted, used_slugs = [], 0, set()
    t0 = time.time()

    partial     = load_checkpoint("phase2_posts_partial")
    resume_from = 0
    if partial:
        posts       = partial
        used_slugs  = set(f"{p['category']}/{p['slug']}" for p in posts)
        resume_from = len(posts)
        log(f"  Partial checkpoint: resuming from {resume_from}")

    stats = {"wrong_subject": 0, "wrong_shape": 0,
             "low_confidence": 0, "deformed": 0, "parse_fail": 0}

    for i, item_data in enumerate(generated):
        if i < resume_from:
            continue

        item      = item_data["item"]
        category  = item["category"]
        subject   = (item.get("subject_name") or
                     category.replace("-", " ").replace("_", " ").title())
        prompt    = item.get("prompt", f"a {subject}")
        slug_base = slugify(subject)
        path      = Path(item_data["path"])
        group     = _get_category_group(category)

        approved_path = APPROVED_DIR / path.relative_to(GENERATED_DIR)
        approved_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with Image.open(path).convert("RGB") as img_orig:
                iw, ih = img_orig.size
                # 512px — optimal balance of quality and Qwen inference speed
                if max(iw, ih) > 512:
                    r       = 512 / max(iw, ih)
                    img_pil = img_orig.resize((int(iw * r), int(ih * r)), Image.LANCZOS).copy()
                else:
                    img_pil = img_orig.copy()

            messages = [{"role": "user", "content": [
                {"type": "image", "image": img_pil},
                {"type": "text",  "text":  _build_disabled_prompt(item, subject, category, slug_base)},
            ]}]

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
                    max_new_tokens=1200,   # 300-400 word desc fits in 1200 tokens — 2x faster
                    temperature=0.1,       # Near-deterministic → fewer JSON parse errors
                    top_p=0.9,
                    do_sample=False,       # Greedy decode → consistent JSON structure
                    pad_token_id=processor.tokenizer.eos_token_id,
                )

            trimmed = [out_ids[k][len(inputs.input_ids[k]):]
                       for k in range(len(out_ids))]
            raw = processor.batch_decode(
                trimmed, skip_special_tokens=True,
                clean_up_tokenization_spaces=True)[0].strip()

            ai = {}
            parse_ok = False

            # Pass 1: direct JSON extract
            try:
                j0, j1 = raw.find("{"), raw.rfind("}") + 1
                if j0 >= 0 and j1 > j0:
                    ai = json.loads(raw[j0:j1])
                    parse_ok = True
            except Exception:
                pass

            # Pass 2: strip control chars then parse
            if not parse_ok:
                try:
                    chunk = raw[raw.find("{"):raw.rfind("}") + 1]
                    clean = re.sub(r'[\x00-\x1f\x7f]', ' ', chunk)
                    ai = json.loads(clean)
                    parse_ok = True
                except Exception:
                    pass

            # Pass 3: aggressive clean — fix unescaped newlines inside strings
            if not parse_ok:
                try:
                    chunk = raw[raw.find("{"):raw.rfind("}") + 1]
                    clean = re.sub(r'[\x00-\x08\x0b-\x1f\x7f]', ' ', chunk)
                    # Fix unescaped newlines inside JSON strings
                    clean = re.sub(r'(?<!\\)\n', '\\n', clean)
                    ai = json.loads(clean)
                    parse_ok = True
                except Exception:
                    pass

            # All passes failed → raise so outer except → DELETE
            if not parse_ok:
                raise ValueError(f"JSON parse failed after 3 passes. Raw[:200]: {raw[:200]}")

            subject_match = ai.get("subject_match", True)
            if isinstance(subject_match, str):
                subject_match = subject_match.lower() not in ("false", "no", "0")
            confidence = int(ai.get("confidence", 7))
            verdict    = ai.get("verdict", "KEEP").strip().upper()
            reason     = ai.get("reason", "")
            shape_match = ai.get("shape_match", True)
            if isinstance(shape_match, str):
                shape_match = shape_match.lower() not in ("false", "no", "0")

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

            raw_slug = ai.get("slug") or f"{slug_base}-png-hd"
            slug     = slugify(raw_slug)
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
                "model_confidence": confidence,
                "model_group":      group,
                "approved_path":   str(approved_path),
                "png_file_id": "", "jpg_file_id": "", "webp_file_id": "",
                "download_url": "", "preview_url": "", "preview_url_small": "",
                "webp_preview_url": "", "preview_w": 800, "preview_h": 800,
                "date_added": datetime.now().strftime("%Y-%m-%d"),
            }
            posts.append(post)

            rate = max((i + 1 - resume_from), 1) / (time.time() - t0)
            eta  = (len(generated) - i - 1) / rate / 60
            log(f"  KEEP [{i+1}/{len(generated)}] {slug} (conf={confidence}) | ETA {eta:.0f}min")

        except Exception as e:
            # V7.0: parse fail = DELETE — do NOT keep bad images via fallback
            log(f"  Qwen FAIL→DELETE [{i+1}] {item.get('filename','?')}: {e}")
            stats["parse_fail"] += 1
            path.unlink(missing_ok=True)   # delete the generated image
            deleted += 1
            continue

        if (i + 1) % 10 == 0:
            gc.collect(); torch.cuda.empty_cache()
            save_checkpoint("phase2_posts_partial", posts)

    log("\n  Deleting Qwen -> freeing VRAM + disk cache...")
    del model, processor
    free_memory()

    # Delete Qwen HF cache to free ~6GB disk for RMBG download
    import shutil as _shutil
    for _cache_sub in HF_CACHE.iterdir():
        if _cache_sub.is_dir():
            _name = _cache_sub.name.lower()
            if "disabled" in _name:
                _shutil.rmtree(str(_cache_sub), ignore_errors=True)
                log(f"  Deleted Qwen cache: {_cache_sub.name}")

    # Delete GENERATED_DIR images — approved/ has the copies already
    if GENERATED_DIR.exists():
        _shutil.rmtree(str(GENERATED_DIR), ignore_errors=True)
        GENERATED_DIR.mkdir(parents=True, exist_ok=True)
        log("  Deleted generated/ images (approved/ copies kept)")

    _used = sum(f.stat().st_size for f in HF_CACHE.rglob("*") if f.is_file()) / 1e9
    log(f"  HF cache after cleanup: {_used:.1f}GB")

    save_checkpoint("phase2_posts", posts)
    log(f"PHASE 2 DONE — Kept: {len(posts)} | Deleted: {deleted}")
    log(f"  WrongSubject:{stats['wrong_subject']} WrongShape:{stats['wrong_shape']} "
        f"LowConf:{stats['low_confidence']} Deformed:{stats['deformed']} "
        f"ParseFail:{stats['parse_fail']}\n")
    return posts


def _fallback_desc(subject, category, prompt=""):
    ph = f' (prompt: "{prompt[:80]}")' if prompt else ""
    return f"""## About This {subject} PNG Image

A {subject} PNG image{ph} — free for download at UltraPNG.com with a fully transparent background. Whether you're designing flex banners, social media graphics, YouTube thumbnails, or Canva projects, this image integrates seamlessly into any layout. Background removal is done using RMBG-2.0 AI for clean, precise edges around every detail.

## Best Uses for This Image

Perfect for graphic designers, marketers, and content creators. Use this {subject} PNG in flex banner printing, invitation card designs, Instagram posts, WhatsApp status graphics, e-commerce product listings, and digital advertising. The transparent background works in Photoshop, Canva, CorelDRAW, and Figma without any extra editing.

## Technical Quality

Processed with RMBG-2.0 ONNX for pixel-perfect transparent edges. HD resolution stays sharp from small social media icons to large 4096px flex banner prints. Clean alpha channel with anti-aliased edges blends naturally on any color background.

## Design Ideas

- Flex banner and hoarding designs for shops and events
- Social media posts, Instagram stories, and WhatsApp status
- YouTube thumbnail and channel banner compositions
- Wedding invitation and event poster designs
- Restaurant menu cards and food delivery app graphics
- Birthday and celebration banners
- E-commerce product catalog listings
- PowerPoint and Canva presentation slides

## FAQ

**Is this {subject} PNG completely free?**
Yes — 100% free for personal and commercial use. No account, no signup, no watermark on downloaded file.

**Can I use this in Canva?**
Yes. Go to Canva → Uploads → upload this PNG → drag to your canvas. Transparent background works perfectly.

**Does the downloaded PNG have a watermark?**
No. The preview image shows a watermark for protection, but the downloaded file is completely clean.

**Can I print this on flex banners?**
Yes. The HD resolution is print-ready for large-format flex, vinyl, and hoarding printing.

## Why UltraPNG

UltraPNG.com is a free transparent PNG library updated daily with quality-verified AI-generated images. Every PNG features pixel-perfect RMBG-2.0 transparency. Completely free — no fees, no signup. Trusted by designers and marketers."""


def _fallback_post(item_data, subject, category, prompt, used_slugs, approved_path=""):
    item      = item_data["item"]
    slug      = slugify(f"{subject}-png-hd")
    base, sfx = slug, 1
    while f"{category}/{slug}" in used_slugs:
        slug = f"{base}-{sfx}"; sfx += 1
    used_slugs.add(f"{category}/{slug}")
    return {
        "category": category, "subcategory": item.get("subcategory", "general"),
        "subject_name": subject, "filename": item.get("filename", ""),
        "original_prompt": prompt, "slug": slug,
        "title": f"{subject} Transparent PNG HD Free Download | UltraPNG",
        "h1": f"{subject} PNG HD Image",
        "meta_desc": f"Download {subject} PNG transparent background free HD. UltraPNG.com.",
        "alt_text": f"{subject} PNG Transparent Background Free Download UltraPNG",
        "tags": f"{subject},png,transparent,free download,hd,{subject} PNG free,ultrapng",
        "description": _fallback_desc(subject, category, prompt),
        "word_count": 0, "ai_generated": False, "approved_path": approved_path,
        "png_file_id": "", "jpg_file_id": "", "webp_file_id": "",
        "download_url": "", "preview_url": "", "preview_url_small": "",
        "webp_preview_url": "", "preview_w": 800, "preview_h": 800,
        "date_added": datetime.now().strftime("%Y-%m-%d"),
    }

# ══════════════════════════════════════════════════════════════
# PHASE 3 — RMBG-2.0 ONNX  (downloads from HuggingFace)
# ══════════════════════════════════════════════════════════════
def phase3_bg_remove(posts):
    ckpt = load_checkpoint("phase3_transparent")
    if ckpt:
        return ckpt

    log("=" * 56)
    log("PHASE 3: BiRefNet_HR — 2048x2048 FP16 — Background Removal (GPU)")
    log(f"  Loading from HuggingFace: {RMBG_HF_ID}")
    log("=" * 56)

    if not posts:
        return []

    from torchvision import transforms
    from transformers import AutoModelForImageSegmentation

    rmbg_model = AutoModelForImageSegmentation.from_pretrained(
        RMBG_HF_ID,
        trust_remote_code=True,
        cache_dir=str(HF_CACHE),
    )
    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch.set_float32_matmul_precision("high")
    rmbg_model = rmbg_model.to(device).eval().half()  # FP16 official recommendation
    log(f"  BiRefNet_HR loaded on {device.upper()} | FP16 | 2048x2048\n")

    # Official inference code from ZhengPeng7/BiRefNet_HR HuggingFace page
    transform_img = transforms.Compose([
        transforms.Resize((2048, 2048)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406],
                             [0.229, 0.224, 0.225]),
    ])

    def remove_bg(pil_img):
        ow, oh   = pil_img.size
        inp      = transform_img(pil_img.convert("RGB")).unsqueeze(0).to(device).half()
        with torch.no_grad():
            preds = rmbg_model(inp)[-1].sigmoid().cpu()
        pred     = preds[0].squeeze()
        mask_pil = transforms.ToPILImage()(pred).resize((ow, oh), Image.LANCZOS)
        result   = pil_img.convert("RGBA")
        result.putalpha(mask_pil)
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

            img    = Image.open(str(path)).convert("RGB")
            result = remove_bg(img)
            result.save(str(out), "PNG", compress_level=0)
            result_posts.append({**post, "transparent_path": str(out)})

            if (i + 1) % 20 == 0:
                log(f"  BG done: {i+1}/{len(posts)} | {(i+1)/(time.time()-t0):.2f}/s")

        except Exception as e:
            log(f"  RMBG FAIL {path.name}: {e}")

    # ── DELETE model → free VRAM + disk for Phase 4 ──
    log("\n  Deleting RMBG-2.0 → freeing VRAM + disk cache...")
    del rmbg_model, transform_img
    free_memory()

    # Delete BiRefNet HF cache
    import shutil as _shutil
    for _cache_sub in HF_CACHE.iterdir():
        if _cache_sub.is_dir():
            _name = _cache_sub.name.lower()
            if "rmbg" in _name or "briaai" in _name or "birefnet" in _name:
                _shutil.rmtree(str(_cache_sub), ignore_errors=True)
                log(f"  Deleted BiRefNet cache: {_cache_sub.name}")

    # Delete APPROVED_DIR images — transparent/ has the final copies
    if APPROVED_DIR.exists():
        _shutil.rmtree(str(APPROVED_DIR), ignore_errors=True)
        APPROVED_DIR.mkdir(parents=True, exist_ok=True)
        log("  Deleted approved/ images (transparent/ copies kept)")

    _used = sum(f.stat().st_size for f in HF_CACHE.rglob("*") if f.is_file()) / 1e9
    log(f"  HF cache after cleanup: {_used:.1f}GB")

    save_checkpoint("phase3_transparent", result_posts)
    log(f"PHASE 3 DONE — Transparent PNGs: {len(result_posts)}\n")
    return result_posts


# ══════════════════════════════════════════════════════════════
# PHASE 4 — Google Drive Upload
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
            pr = drive_upload(token, fcache[f"p_{key}"], path.name, png_bytes)
            drive_share(token, pr["id"])

            # WebP preview with diagonal watermark + bottom footer bar.
            # JPG is intentionally skipped (lower cost + lower Drive API calls).
            _, webp_bytes, pw, ph = make_previews(path)
            wr = drive_upload(token, fcache[f"r_{key}"],
                              path.stem + ".webp", webp_bytes, "image/webp")
            drive_share(token, wr["id"])

            uploaded.append({
                **post,
                "png_file_id":       pr["id"],
                "jpg_file_id":       "",
                "webp_file_id":      wr["id"],
                "download_url":      download_url(pr["id"]),
                "webp_download_url": download_url(wr["id"]),
                # Website uses `preview_url` for the preview image.
                "preview_url":       preview_url(wr["id"], 800),
                "preview_url_small": preview_url(wr["id"], 400),
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
    log(f"PHASE 4 DONE — Uploaded: {len(uploaded)} in {(time.time()-t0)/60:.0f}min")

    # Delete transparent/ images — all uploaded to Drive already
    import shutil as _shutil
    if TRANSPARENT_DIR.exists():
        _shutil.rmtree(str(TRANSPARENT_DIR), ignore_errors=True)
        TRANSPARENT_DIR.mkdir(parents=True, exist_ok=True)
        log("  Deleted transparent/ images (uploaded to Drive)")
    log("")
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
               lambda m: '<ol>' + m.group(0).replace('<oli>','<li>').replace('</oli>','</li>') + '</ol>', o)
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

    if webp_img:
        img_tag = (f'<picture>'
                   f'<source srcset="{esc(webp_img)}" type="image/webp"/>'
                   f'<img src="{esc(img)}" alt="{esc(post.get("alt_text",""))}" '
                   f'width="{post.get("preview_w",800)}" height="{post.get("preview_h",800)}" '
                   f'fetchpriority="high" onerror="this.src=\'/img/placeholder.png\'"/>'
                   f'</picture>')
    else:
        img_tag = (f'<img src="{esc(img)}" alt="{esc(post.get("alt_text",""))}" '
                   f'width="{post.get("preview_w",800)}" height="{post.get("preview_h",800)}" '
                   f'fetchpriority="high" onerror="this.src=\'/img/placeholder.png\'"/>')

    rel_html = "".join(
        f'<a href="/png-library/{r["category"]}/{r["slug"]}/" class="png-related-card">'
        f'<div class="png-related-thumb">'
        f'<img src="{esc(r.get("preview_url_small", r.get("preview_url","")))} " '
        f'alt="{esc(r.get("h1",""))}" loading="lazy" width="300" height="300" '
        f'onerror="this.parentNode.style.display=\'none\'"/></div>'
        f'<span class="png-related-name">{esc(r.get("h1",""))}</span></a>\n'
        for r in related[:24]
    )

    schema = json.dumps({
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "ImageObject", "name": post.get("h1",""),
             "description": post.get("meta_desc",""),
             "contentUrl": post.get("download_url",""), "thumbnailUrl": img,
             "encodingFormat": "image/png", "isAccessibleForFree": True,
             "datePublished": post.get("date_added",""),
             "license": f"{SITE_URL}/pages/terms.html",
             "publisher": {"@type": "Organization", "name": "UltraPNG", "url": SITE_URL + "/"},
             "keywords": ", ".join(tags)},
            {"@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE_URL + "/"},
                {"@type": "ListItem", "position": 2, "name": "PNG Library", "item": f"{SITE_URL}/png-library/"},
                {"@type": "ListItem", "position": 3, "name": cat_label, "item": f"{SITE_URL}/png-library/{post['category']}/"},
                {"@type": "ListItem", "position": 4, "name": post.get("h1","")},
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

    def _card(idx, it):
        thumb = ""
        if it.get("preview_url_small") or it.get("preview_url"):
            sw = esc(it.get("webp_preview_url","") or it.get("preview_url_small",""))
            sj = esc(it.get("preview_url_small", it.get("preview_url","")))
            al = esc(it.get("h1",""))
            thumb = (f'<picture><source srcset="{sw}" type="image/webp"/>'
                     f'<img src="{sj}" alt="{al}" loading="lazy" width="400" height="400"/></picture>')
        pg  = idx // ITEMS_PER_PAGE
        return (f'<a href="/png-library/{it["category"]}/{it["slug"]}/" '
                f'class="mpng-item-card cat-item" data-pg="{pg}" title="{esc(it.get("h1",""))}">'
                f'<div class="mpng-item-thumb">{thumb}</div>'
                f'<div class="mpng-item-label">{esc(it.get("h1",""))}</div></a>\n')

    cards = "".join(_card(idx, it) for idx, it in enumerate(items))
    tp    = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    pag   = (f'<nav class="pg-nav">'
             f'<button class="pg-btn pg-btn-prev" id="cP" onclick="catPage(_cp-1)" disabled>&#8592; Previous</button>'
             f'<span class="pg-info" id="cI">Page 1 of {tp}</span>'
             f'<button class="pg-btn pg-btn-next" id="cN" onclick="catPage(_cp+1)">Next &#8594;</button>'
             f'</nav>') if tp > 1 else ""
    title = f"{label} PNG Images Free Download ({total}+) | UltraPNG"
    desc  = f"Download {total}+ free {label} transparent PNG. HD Photoshop Canva."
    return (f'{_head(title, desc, url, img)}\n</head><body>{_header()}\n'
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

    def _cat_card(cat):
        items = by_cat[cat]
        name  = esc(items[0].get("subject_name", cat).lower())
        tags  = esc(",".join(set(
            t.strip() for it in items[:3]
            for t in it.get("tags","").lower().split(",") if t.strip()
        ))[:200])
        previews = "".join(
            f'<img src="{esc(it.get("preview_url_small",it.get("preview_url","")))} " '
            f'alt="{esc(items[0].get("subject_name",cat))}" loading="lazy" '
            f'width="200" height="200" onerror="this.remove()"/>'
            for it in items[:4] if it.get("preview_url_small") or it.get("preview_url")
        )
        return (f'<a href="/png-library/{cat}/" class="mpng-cat-card" '
                f'data-cat="{name}" data-search="{tags}">'
                f'<div class="mpng-cat-previews">{previews}</div>'
                f'<div class="mpng-cat-footer">'
                f'<span class="mpng-cat-name">{esc(items[0].get("subject_name",cat))}</span>'
                f'<span class="mpng-cat-cnt">{len(items)} images</span>'
                f'</div></a>\n')

    cat_cards = "".join(_cat_card(cat) for cat in cats)

    recent = sorted(all_data, key=lambda x: x.get("date_added",""), reverse=True)[:ITEMS_PER_PAGE * 5]

    def _rec_card(idx, it):
        thumb = ""
        if it.get("preview_url_small") or it.get("preview_url"):
            src = esc(it.get("preview_url_small", it.get("preview_url","")))
            alt = esc(it.get("h1",""))
            thumb = f'<img src="{src}" alt="{alt}" loading="lazy" width="400" height="400"/>'
        return (f'<a href="/png-library/{it["category"]}/{it["slug"]}/" '
                f'class="mpng-item-card recent-item" data-rpg="{idx // ITEMS_PER_PAGE}">'
                f'<div class="mpng-item-thumb">{thumb}</div>'
                f'<div class="mpng-item-label">{esc(it.get("h1",""))}</div>'
                f'<div class="mpng-item-cat">{esc(it.get("subject_name",it["category"]))}</div></a>\n')

    rec_cards = "".join(_rec_card(idx, it) for idx, it in enumerate(recent))
    trp  = max(1, (len(recent) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    pag  = (f'<nav class="pg-nav">'
            f'<button class="pg-btn pg-btn-prev" id="rP" onclick="recentPage(_rcp-1)" disabled>&#8592; Previous</button>'
            f'<span class="pg-info" id="rI">Page 1 of {trp}</span>'
            f'<button class="pg-btn pg-btn-next" id="rN" onclick="recentPage(_rcp+1)">Next &#8594;</button>'
            f'</nav>') if trp > 1 else ""
    title = f"UltraPNG {ti}+ Free Transparent PNG Images HD"
    desc  = f"Download {ti}+ free HD transparent PNG. {tc} categories. No watermark no signup."
    img   = all_data[0].get("preview_url","") if all_data else ""
    return (f'{_head(title, desc, url, img)}\n</head><body>{_header()}\n'
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
    entries = [
        f'<url><loc>{SITE_URL}/png-library/</loc><lastmod>{today}</lastmod>'
        f'<changefreq>daily</changefreq><priority>0.9</priority></url>']
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
    ns     = ('xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
              'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"')
    chunks = [entries[i:i+SITEMAP_MAX_URL] for i in range(0, len(entries), SITEMAP_MAX_URL)]
    sm_files = []
    for idx, chunk in enumerate(chunks, 1):
        fname = f"sitemap-png-{idx}.xml"
        (out_dir / fname).write_text(
            f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset {ns}>\n' +
            "\n".join(chunk) + '\n</urlset>', "utf-8")
        sm_files.append(fname)
    index = "\n".join(
        f'<sitemap><loc>{SITE_URL}/{f}</loc><lastmod>{today}</lastmod></sitemap>'
        for f in sm_files)
    (out_dir / "sitemap-png.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'{index}\n</sitemapindex>', "utf-8")
    log(f"  Sitemaps: {len(sm_files)} files ({len(entries)} URLs)")

def build_robots_txt(out_dir):
    (out_dir / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n\n"
        "User-agent: GPTBot\nDisallow: /\n\n"
        "User-agent: ClaudeBot\nDisallow: /\n\n"
        "User-agent: CCBot\nDisallow: /\n\n"
        "User-agent: anthropic-ai\nDisallow: /\n\n"
        f"Sitemap: {SITE_URL}/sitemap-png.xml\n", "utf-8")

def build_llms_txt(out_dir):
    (out_dir / "llms.txt").write_text(
        f"# {SITE_NAME}\n\n> {SITE_URL} — Free Transparent PNG images\n\n"
        "## About\nFree HD transparent PNG images. Updated daily. No signup.\n\n"
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
# PHASE 5 — JSON-Only Git Push to REPO2  (V7.0: NO HTML build)
# ══════════════════════════════════════════════════════════════
def phase5_build_push(new_posts):
    log("=" * 56)
    log("PHASE 5: JSON-Only Push to REPO2/data/ (V7.0 — no HTML build)")
    log("=" * 56)

    if not GITHUB_TOKEN or not GITHUB_REPO2:
        log("  WARNING: GITHUB_REPO2 / GITHUB_TOKEN_REPO2 not set — skipping")
        return
    if not new_posts:
        log("No new posts"); return

    repo_url = f"https://x-access-token:{GITHUB_TOKEN}@github.com/{GITHUB_REPO2}.git"

    # ── Sparse checkout — only data/ folder (fast, no GB of HTML) ──
    if REPO2_DIR.exists() and (REPO2_DIR / ".git").exists():
        log("REPO2 exists — pulling data/ only...")
        try:
            subprocess.run(["git", "pull", "--rebase", "--autostash"],
                           cwd=str(REPO2_DIR), capture_output=True, check=True)
            subprocess.run(["git", "remote", "set-url", "origin", repo_url],
                           cwd=str(REPO2_DIR), capture_output=True)
        except Exception as e:
            log(f"  Pull failed ({e}) — re-cloning sparse...")
            shutil.rmtree(str(REPO2_DIR), ignore_errors=True)
            _sparse_clone(repo_url)
    else:
        log(f"Sparse-cloning REPO2 data/ only: {GITHUB_REPO2}...")
        _sparse_clone(repo_url)

    data_dir = REPO2_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # ── Merge new posts into existing JSON ──
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
    log(f"Merged: +{added} new | Total: {len(all_data)}")

    # ── Save JSON files only ──
    save_data_split(all_data, data_dir)
    log(f"  JSON files saved to data/")

    # ── Git push — only data/ folder changes ──
    today    = datetime.now().strftime("%Y-%m-%d")
    orig_dir = os.getcwd()
    try:
        os.chdir(str(REPO2_DIR))
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"],
                       check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email",
                        "github-actions[bot]@users.noreply.github.com"],
                       check=True, capture_output=True)
        subprocess.run(["git", "add", "data/"], check=True, capture_output=True)
        diff = subprocess.run(["git", "diff", "--staged", "--quiet"], capture_output=True)
        if diff.returncode != 0:
            msg = f"data: +{added} images ({len(all_data)} total) [{today}]"
            subprocess.run(["git", "commit", "-m", msg], check=True, capture_output=True)
            push = subprocess.run(["git", "push"], capture_output=True, text=True)
            if push.returncode == 0:
                log(f"REPO2 JSON pushed! +{added} new | Total: {len(all_data)} images")
            else:
                log(f"Push failed: {push.stderr[:300]}")
        else:
            log("Nothing to commit — data already up to date.")
    except subprocess.CalledProcessError as e:
        log(f"Git error: {e}")
    finally:
        os.chdir(orig_dir)

def _sparse_clone(repo_url):
    """Clone only the data/ folder using git sparse-checkout (fast)."""
    shutil.rmtree(str(REPO2_DIR), ignore_errors=True)
    REPO2_DIR.mkdir(parents=True, exist_ok=True)

    r = subprocess.run(
        ["git", "clone", "--depth", "1", "--filter=blob:none",
         "--sparse", repo_url, str(REPO2_DIR)],
        capture_output=True)

    if r.returncode != 0:
        # Sparse clone not supported — fall back to regular shallow clone
        log("  Sparse clone failed — falling back to regular shallow clone...")
        shutil.rmtree(str(REPO2_DIR), ignore_errors=True)
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(REPO2_DIR)],
            capture_output=True, check=True)
        return

    # Init cone mode then restrict to data/ only
    subprocess.run(
        ["git", "sparse-checkout", "init", "--cone"],
        cwd=str(REPO2_DIR), capture_output=True)
    subprocess.run(
        ["git", "sparse-checkout", "set", "data"],
        cwd=str(REPO2_DIR), capture_output=True)
    log("  Sparse clone OK — data/ folder only")



# ══════════════════════════════════════════════════════════════
# PHASE 6 — Save Run Logs to REPO1
# ══════════════════════════════════════════════════════════════
def phase6_save_logs(stats: dict):
    log("=" * 56)
    log("PHASE 6: Saving run logs to REPO1/logs/")
    log("=" * 56)

    token = GITHUB_TOKEN_REPO1 or GITHUB_TOKEN
    if not token or not GITHUB_REPO1:
        log("  No REPO1 token/repo — skipping")
        return

    repo_url = f"https://x-access-token:{token}@github.com/{GITHUB_REPO1}.git"
    try:
        if not REPO1_DIR.exists():
            subprocess.run(["git", "clone", "--depth", "1", repo_url, str(REPO1_DIR)],
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
            f"ULTRAPNG PIPELINE V6.0 — RUN REPORT\n"
            f"{'='*60}\n"
            f"Date       : {datetime.now().strftime('%Y-%m-%d %H:%M IST')}\n"
            f"Batch      : {START_INDEX} -> {END_INDEX}\n"
            f"Generated  : {stats.get('generated',0)}\n"
            f"Deleted    : {stats.get('deleted',0)}\n"
            f"Approved   : {stats.get('approved',0)}\n"
            f"Transparent: {stats.get('transparent',0)}\n"
            f"Uploaded   : {stats.get('uploaded',0)}\n"
            f"Posts      : {stats.get('posts',0)}\n"
            f"Duration   : {stats.get('duration','?')}\n"
            f"Status     : {stats.get('status','unknown')}\n"
            f"{'='*60}\n\nFULL LOG\n{'='*60}\n"
        )
        full_log = summary + "\n".join(_LOG_LINES)
        log_file.write_text(full_log, "utf-8")

        for old in sorted(logs_dir.glob("????-??-??_??-??.log"))[:-30]:
            old.unlink()
        (logs_dir / "latest.log").write_text(full_log, "utf-8")

        readme = logs_dir / "README.md"
        rows   = [l for l in (readme.read_text("utf-8").split("\n")
                               if readme.exists() else []) if l.startswith("| 20")]
        rows.insert(0, (f"| {now.replace('_',' ')} "
                        f"| {stats.get('generated',0)} | {stats.get('deleted',0)} "
                        f"| {stats.get('approved',0)} | {stats.get('uploaded',0)} "
                        f"| {stats.get('posts',0)} | {stats.get('duration','?')} "
                        f"| {stats.get('status','?')} |"))
        readme.write_text(
            "# UltraPNG Pipeline — Run History\n\n"
            "| Date & Time | Generated | Deleted | Approved | Uploaded | Posts | Duration | Status |\n"
            "|-------------|-----------|---------|----------|----------|-------|----------|--------|\n"
            + "\n".join(rows[:50]) + "\n", "utf-8")

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
                msg  = (f"[logs] {now} | gen={stats.get('generated',0)} "
                        f"del={stats.get('deleted',0)} posts={stats.get('posts',0)} "
                        f"| {stats.get('status','?')}")
                subprocess.run(["git", "commit", "-m", msg], check=True, capture_output=True)
                push = subprocess.run(["git", "push"], capture_output=True, text=True)
                if push.returncode == 0:
                    log(f"Logs pushed! View: https://github.com/{GITHUB_REPO1}/tree/main/logs")
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
             "approved": 0, "transparent": 0, "uploaded": 0, "posts": 0, "duration": "?"}

    print("╔══════════════════════════════════════════════════════╗")
    print("║  UltraPNG V7.0 — HuggingFace Direct Pipeline       ║")
    print("║  FLUX -> RMBG -> Drive -> ultradata.xlsx -> Git  ║")
    print("╚══════════════════════════════════════════════════════╝")
    print(f"  Batch : {START_INDEX} -> {END_INDEX} ({END_INDEX-START_INDEX} prompts)")
    print(f"  REPO2 : {GITHUB_REPO2}")
    print(f"  FLUX  : {FLUX_HF_ID}")
    print(f"  RMBG  : {RMBG_HF_ID} (2048x2048 — highest quality)")
    print(f"  Cache : {HF_CACHE}")
    if torch.cuda.is_available():
        p = torch.cuda.get_device_properties(0)
        print(f"  GPU   : {p.name} | VRAM: {p.total_memory/1e9:.0f}GB")
    print()

    try:
        prompts = load_prompts()
        if not prompts:
            raise Exception("No prompts loaded!")

        batch = prompts[START_INDEX:END_INDEX]
        log(f"Batch: {len(batch)} prompts\n")

        skip_set = load_skip_set_from_json()

        # PHASE 1
        generated = phase1_generate(batch, skip_set)
        stats["generated"] = len(generated)
        if not generated:
            log("No new images generated."); return

        # PHASE 2 (NO QWEN): prepare approved copies + subject names
        posts = phase2_prepare_posts_no_model(generated)
        stats["approved"] = len(posts)
        stats["deleted"]  = 0
        if not posts:
            log("No posts prepared."); return

        # PHASE 3
        transparent = phase3_bg_remove(posts)
        stats["transparent"] = len(transparent)
        if not transparent:
            log("BG removal produced no results."); return

        # PHASE 4
        uploaded = phase4_upload(transparent)
        stats["uploaded"] = len(uploaded)
        if not uploaded:
            log("Drive upload failed."); return

        # PHASE 5: append into ultradata.xlsx (no REPO2 JSON push in Section 1)
        update_ultradata_xlsx_from_uploaded(uploaded)
        stats["posts"] = len(uploaded)

        # Clear checkpoints on success
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

    except Exception as e:
        hrs = (time.time() - t0) / 3600
        stats["duration"] = f"{hrs:.1f}h"
        stats["status"]   = f"FAILED: {str(e)[:80]}"
        log(f"FATAL: {e}")
        raise
    finally:
        phase6_save_logs(stats)

if __name__ == "__main__":
    main()
