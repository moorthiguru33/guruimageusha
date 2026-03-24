"""
╔══════════════════════════════════════════════════════════════╗
║  UltraPNG — SEO Pipeline  (Trigger 2)                       ║
╠══════════════════════════════════════════════════════════════╣
║  Step 1 → manifest.csv       Download from Drive (1 call)   ║
║  Step 2 → Repo2 JSON         Load existing → skip done      ║
║  Step 3 → Drive check        PNG exists? WebP missing?      ║
║  Step 4 → Gemma 3 4B-IT      SEO: title/desc/tags/slug      ║
║  Step 5 → Repo2 push         Category-wise JSON             ║
╠══════════════════════════════════════════════════════════════╣
║  All pending at once  |  Kaggle GPU  |  Manual trigger      ║
║  AdSense-ready: 20+w titles, 350-400w unique descriptions   ║
╚══════════════════════════════════════════════════════════════╝
"""

import os, sys, json, time, gc, re, io, csv, shutil, subprocess
from pathlib import Path
from datetime import datetime

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

# ── HuggingFace cache ─────────────────────────────────────────
HF_CACHE = Path("/kaggle/working/hf_cache")
HF_CACHE.mkdir(parents=True, exist_ok=True)
os.environ["HF_HOME"]               = str(HF_CACHE)
os.environ["HUGGINGFACE_HUB_CACHE"] = str(HF_CACHE)
os.environ["TRANSFORMERS_CACHE"]    = str(HF_CACHE)
if os.environ.get("HF_TOKEN"):
    os.environ["HUGGINGFACE_HUB_TOKEN"] = os.environ["HF_TOKEN"]

# ── Model ─────────────────────────────────────────────────────
# Gemma 3 4B bfloat16 = ~8GB weights + ~2GB activations = ~10GB total
# P100 16GB VRAM → SAFE ✅
GEMMA_HF_ID = "google/gemma-3-4b-it"

# ── Install deps ──────────────────────────────────────────────
print("=" * 56)
print("Installing dependencies...")

# Check GPU capability — P100 = sm_60, not supported by latest torch
import subprocess as _sp, sys as _sys
_gpu_check = _sp.run(
    [_sys.executable, "-c",
     "import torch; c=torch.cuda.get_device_capability(0) if torch.cuda.is_available() else (0,0); print(f'{c[0]}.{c[1]}')"],
    capture_output=True, text=True
)
_gpu_cap = _gpu_check.stdout.strip()
print(f"  GPU compute capability: {_gpu_cap}")

# P100 (sm_60) → install compatible torch, and force float16 (P100 has no bfloat16)
_IS_P100 = _gpu_cap.startswith("6.")
if _IS_P100:
    print("  P100 detected (sm_60) — installing torch 2.1.2+cu118...")
    _sp.run([_sys.executable, "-m", "pip", "install", "-q",
             "torch==2.1.2", "torchvision==0.16.2",
             "--index-url", "https://download.pytorch.org/whl/cu118"],
            capture_output=True)
    print("  torch 2.1.2+cu118 installed ✅")

r = _sp.run(
    [_sys.executable, "-m", "pip", "install", "-q", "--no-warn-conflicts",
     # FIX: torchvision pinned for P100 — without pin, pip installs latest torchvision
     # which requires torch>=2.2 and silently overwrites the P100-compatible torch 2.1.2,
     # causing CUDA sm_60 errors on ALL operations.
     "transformers>=4.50.0", "accelerate>=0.28.0",
     "huggingface_hub>=0.23.0", "Pillow>=10.0",
     "requests", "torchvision==0.16.2" if _IS_P100 else "torchvision", "piexif"],
    capture_output=True, text=True)
print(f"  pip: {'OK' if r.returncode == 0 else 'WARN'}")
print("Done!\n")

import torch

# P100 does NOT support bfloat16 — use float16 instead
_TORCH_DTYPE = torch.float16 if _IS_P100 else torch.bfloat16
import requests as req
from PIL import Image, ImageDraw, ImageFont

# ── Paths ─────────────────────────────────────────────────────
WORKING_DIR = Path("/kaggle/working")
REPO2_DIR   = WORKING_DIR / "repo2"
REPO1_DIR   = WORKING_DIR / "repo1"
WEBP_TMP    = WORKING_DIR / "webp_tmp"
WEBP_TMP.mkdir(parents=True, exist_ok=True)

# ── Config ────────────────────────────────────────────────────
GOOGLE_CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN", "")
GITHUB_TOKEN_REPO2   = os.environ.get("GITHUB_TOKEN_REPO2", "")
GITHUB_REPO2         = os.environ.get("GITHUB_REPO2", "")
GITHUB_REPO1         = os.environ.get("GITHUB_REPO", "")
GITHUB_TOKEN_REPO1   = os.environ.get("GITHUB_TOKEN_REPO1", "")

SITE_URL       = "https://www.ultrapng.com"
SITE_NAME      = "UltraPNG"
WATERMARK_TEXT = "www.ultrapng.com"
WEBP_SIZE      = 800
MANIFEST_NAME  = "ultrapng_manifest.csv"

# ── SEO Run Options (injected via trigger_seo.yml) ────────────
SEO_CATEGORY_FILTER = os.environ.get("SEO_CATEGORY_FILTER", "").strip()
SEO_LIMIT           = int(os.environ.get("SEO_LIMIT", "0") or "0")
SEO_FORCE_REPROCESS = os.environ.get("SEO_FORCE_REPROCESS", "false").lower() == "true"

# ── LOG ───────────────────────────────────────────────────────
_LOG_LINES = []
def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    _LOG_LINES.append(line)

def free_memory():
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()

def slugify(s, max_len=70):
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:max_len]

def preview_url(fid, size=800):
    return f"https://drive.google.com/thumbnail?id={fid}&sz=w{size}"

def download_url(fid):
    return f"https://drive.google.com/uc?export=download&id={fid}"

# ══════════════════════════════════════════════════════════════
# GOOGLE DRIVE
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
        raise Exception(f"Drive token error: {d}")
    _token_cache.update({"value": d["access_token"], "expires": time.time() + 3200})
    return _token_cache["value"]

def drive_file_exists(token, file_id):
    """True if file exists and not trashed."""
    if not file_id:
        return False
    try:
        r = req.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}",
            headers={"Authorization": f"Bearer {token}"},
            params={"fields": "id,trashed"}, timeout=15)
        if r.status_code == 404:
            return False
        return r.ok and not r.json().get("trashed", False)
    except Exception:
        return False

def drive_download_file(token, file_id):
    """Download file bytes from Drive."""
    r = req.get(
        f"https://www.googleapis.com/drive/v3/files/{file_id}",
        headers={"Authorization": f"Bearer {token}"},
        params={"alt": "media"}, timeout=120)
    if r.ok:
        return r.content
    raise Exception(f"Download failed {file_id}: {r.status_code}")

def drive_find_file(token, name):
    h = {"Authorization": f"Bearer {token}"}
    q = f"name='{name}' and trashed=false"
    r = req.get("https://www.googleapis.com/drive/v3/files",
                headers=h, params={"q": q, "fields": "files(id,name)"}, timeout=30)
    files = r.json().get("files", [])
    return files[0]["id"] if files else None

def drive_upload(token, name, data, mime, folder_id=None, file_id=None, retries=3):
    for attempt in range(1, retries + 1):
        try:
            h = {"Authorization": f"Bearer {token}"}
            if file_id:
                r = req.patch(
                    f"https://www.googleapis.com/upload/drive/v3/files/{file_id}"
                    f"?uploadType=media",
                    headers={**h, "Content-Type": mime},
                    data=data, timeout=120)
                if r.ok:
                    return {"id": file_id}
                raise Exception(f"HTTP {r.status_code}: {r.text[:100]}")
            else:
                metadata = json.dumps({"name": name,
                                       **({"parents": [folder_id]} if folder_id else {})})
                b    = "UltraPNGSEOBound"
                body = (
                    f"--{b}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
                    f"{metadata}\r\n--{b}\r\nContent-Type: {mime}\r\n\r\n"
                ).encode() + data + f"\r\n--{b}--".encode()
                r = req.post(
                    "https://www.googleapis.com/upload/drive/v3/files"
                    "?uploadType=multipart&fields=id,name",
                    headers={**h, "Content-Type": f'multipart/related; boundary="{b}"'},
                    data=body, timeout=120)
                if r.ok:
                    return r.json()
                raise Exception(f"HTTP {r.status_code}: {r.text[:100]}")
        except Exception as e:
            if attempt < retries:
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

# ══════════════════════════════════════════════════════════════
# MANIFEST CSV
# ══════════════════════════════════════════════════════════════
def download_manifest(token):
    """Download manifest.csv → list of dicts."""
    fid = drive_find_file(token, MANIFEST_NAME)
    if not fid:
        log("  manifest.csv not found on Drive!")
        return [], None
    r = req.get(
        f"https://www.googleapis.com/drive/v3/files/{fid}",
        headers={"Authorization": f"Bearer {token}"},
        params={"alt": "media"}, timeout=60)
    if not r.ok:
        log(f"  manifest.csv download failed: {r.status_code}")
        return [], fid
    rows = list(csv.DictReader(io.StringIO(r.text)))
    log(f"  manifest.csv: {len(rows)} entries")
    return rows, fid

# ══════════════════════════════════════════════════════════════
# WEBP WATERMARK (for missing WebP case)
# ══════════════════════════════════════════════════════════════
_wm_cache = {}

def _watermark_layer(w, h):
    key = (w, h)
    if key not in _wm_cache:
        try:
            fnt = ImageFont.truetype(
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 13)
        except Exception:
            fnt = ImageFont.load_default()
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw  = ImageDraw.Draw(layer)
        for ry in range(-h, h + 110, 110):
            for cx in range(-w, w + 110, 110):
                draw.text((cx, ry), WATERMARK_TEXT, fill=(0, 0, 0, 42), font=fnt)
        _wm_cache[key] = (layer.rotate(-30, expand=False), fnt)
    return _wm_cache[key]

def make_webp_from_png_bytes(png_bytes):
    """PNG bytes → watermarked WebP bytes."""
    import io as _io
    with Image.open(_io.BytesIO(png_bytes)).convert("RGBA") as img:
        w, h = img.size
        if max(w, h) > WEBP_SIZE:
            ratio = WEBP_SIZE / max(w, h)
            img   = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        w, h = img.size

        bg  = Image.new("RGB", (w, h), (255, 255, 255))
        drw = ImageDraw.Draw(bg)
        for ry in range(0, h, 20):
            for cx in range(0, w, 20):
                if (ry // 20 + cx // 20) % 2 == 1:
                    drw.rectangle([cx, ry, cx + 20, ry + 20], fill=(232, 232, 232))
        bg.paste(img.convert("RGB"), mask=img.split()[3])

        wm_rot, fnt = _watermark_layer(w, h)
        bg_rgba = bg.convert("RGBA")
        bg_rgba.alpha_composite(wm_rot)
        bg = bg_rgba.convert("RGB")

        try:
            fnt2 = ImageFont.truetype(
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 15)
        except Exception:
            fnt2 = fnt
        drw2 = ImageDraw.Draw(bg)
        drw2.rectangle([0, h - 36, w, h], fill=(13, 13, 20))
        drw2.text((w // 2 - 72, h - 26), WATERMARK_TEXT, fill=(245, 166, 35), font=fnt2)

        buf = _io.BytesIO()
        bg.save(buf, "WEBP", quality=82, method=4)
    return buf.getvalue()

# ══════════════════════════════════════════════════════════════
# REPO2 HELPERS
# ══════════════════════════════════════════════════════════════
def clone_repo2():
    if REPO2_DIR.exists():
        shutil.rmtree(str(REPO2_DIR))
    url = f"https://x-access-token:{GITHUB_TOKEN_REPO2}@github.com/{GITHUB_REPO2}.git"
    subprocess.run(["git", "clone", "--depth=1", url, str(REPO2_DIR)],
                   check=True, capture_output=True)
    log(f"  Repo2 cloned: {GITHUB_REPO2}")

def load_published_slugs():
    """Load already-published filenames from Repo2 → skip set."""
    data_dir = REPO2_DIR / "data"
    published = set()
    if not data_dir.exists():
        return published
    for jf in data_dir.glob("*.json"):
        if jf.name.startswith("_"):
            continue
        try:
            for item in json.loads(jf.read_text("utf-8")):
                published.add(item.get("filename", ""))
        except Exception:
            pass
    log(f"  Repo2 already published: {len(published)} items")
    return published

def push_repo2(by_category, new_count):
    """Write category JSONs to Repo2 and push."""
    data_dir = REPO2_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    for cat, items in by_category.items():
        # Load existing items for this category
        fpath = data_dir / f"{cat}.json"
        existing = []
        if fpath.exists():
            try:
                existing = json.loads(fpath.read_text("utf-8"))
            except Exception:
                existing = []

        # Merge: existing first, then new (no duplicates by filename)
        existing_fnames = {i["filename"] for i in existing}
        merged = existing + [i for i in items if i["filename"] not in existing_fnames]
        merged.sort(key=lambda x: x.get("filename", ""))

        fpath.write_text(json.dumps(merged, ensure_ascii=False, indent=2), "utf-8")

    # Update _index.json
    total_by_cat = {}
    for jf in data_dir.glob("*.json"):
        if jf.name.startswith("_"):
            continue
        try:
            items = json.loads(jf.read_text("utf-8"))
            total_by_cat[jf.stem] = len(items)
        except Exception:
            pass

    (data_dir / "_index.json").write_text(json.dumps({
        "total":      sum(total_by_cat.values()),
        "categories": total_by_cat,
        "updated":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }, ensure_ascii=False, indent=2), "utf-8")

    env = {**os.environ,
           "GIT_AUTHOR_NAME": "UltraPNG Bot",
           "GIT_AUTHOR_EMAIL": "bot@ultrapng.com",
           "GIT_COMMITTER_NAME": "UltraPNG Bot",
           "GIT_COMMITTER_EMAIL": "bot@ultrapng.com"}
    subprocess.run(["git", "-C", str(REPO2_DIR), "add", "data/"],
                   check=True, env=env, capture_output=True)
    r = subprocess.run(["git", "-C", str(REPO2_DIR), "diff", "--cached", "--quiet"])
    if r.returncode != 0:
        subprocess.run(
            ["git", "-C", str(REPO2_DIR), "commit", "-m",
             f"SEO: +{new_count} items published [{datetime.now().strftime('%Y-%m-%d')}]"],
            check=True, env=env, capture_output=True)
        subprocess.run(["git", "-C", str(REPO2_DIR), "push"],
                       check=True, env=env, capture_output=True)
        log(f"  Repo2 pushed ✅ (+{new_count} new items)")
    else:
        log("  Repo2: nothing to commit")

# ══════════════════════════════════════════════════════════════
# GEMMA 3 4B — ADSENSE-QUALITY SEO GENERATOR
# ══════════════════════════════════════════════════════════════

SEO_SYSTEM = """You are a world-class SEO content writer for UltraPNG.com, a free transparent PNG image library.

Your content must be perfect for Google AdSense approval and high organic rankings.

CRITICAL RULES:
1. Title: MINIMUM 20 words. Natural sentence style. Include main keyword + secondary keywords. Make it compelling and unique.
2. Description: EXACTLY 350-400 words. Structured in 4 sections (see format). Rich with LSI keywords. Zero fluff.
3. Every piece of content must be 100% UNIQUE — no templates, no repeated phrases across images.
4. Write for HUMANS first, search engines second.
5. ALWAYS respond with ONLY valid JSON — no markdown, no explanation, no preamble.

JSON FORMAT (strict):
{
  "title": "minimum 20-word unique SEO title that describes this specific image naturally and compellingly",
  "slug": "seo-friendly-url-slug-max-65-chars",
  "meta_desc": "155-160 character meta description with main keyword and clear call to action for click-through",
  "alt_text": "50-60 character descriptive alt text for accessibility and image SEO",
  "h1": "H1 heading — different from title, 10-15 words, includes main keyword",
  "description": "EXACTLY 350-400 words structured as follows:\\n\\n## About This Image\\n[80-100 words: describe EXACTLY what is visible — color, style, angle, texture, background. Be specific to THIS image. Never start with generic phrases.]\\n\\n## Best Uses & Applications\\n[80-100 words: specific creative uses — flex banners, Canva projects, social media posts, invitations, product mockups, website headers. Be specific to the subject.]\\n\\n## Technical Specifications\\n[60-70 words: transparent background quality, BiRefNet AI processing, 1024x1024 resolution, PNG format benefits, clean alpha channel, print-ready quality.]\\n\\n## Frequently Asked Questions\\n**Is this [subject] PNG free to download?** [20-25 word answer]\\n**Can I use this PNG in Canva?** [20-25 word answer]\\n**What file format is this image?** [20-25 word answer]",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10"]
}"""

def build_user_prompt(row):
    subject  = row.get("subject_name", "")
    category = row.get("category", "").replace("_", " ")
    filename = row.get("filename", "")
    return f"""Image details:
- Subject: {subject}
- Category: {category}
- Filename: {filename}
- Website: UltraPNG.com (free transparent PNG library)
- Image type: Transparent PNG with clean AI-processed background removal

Write complete SEO content for this specific transparent PNG image of {subject}."""

def parse_gemma_json(raw_text, row):
    """Robust JSON parser for Gemma output."""
    text  = raw_text.strip()
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start == -1 or end == 0:
        return None

    json_str = text[start:end]
    json_str = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', ' ', json_str)
    json_str = re.sub(r',\s*([}\]])', r'\1', json_str)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        # Fallback: extract field by field
        def _get(key):
            m = re.search(rf'"{key}"\s*:\s*"(.*?)"(?=\s*,\s*"|\s*}})', json_str, re.DOTALL)
            return m.group(1).replace('\\"', '"').strip() if m else ""
        def _get_list(key):
            m = re.search(rf'"{key}"\s*:\s*\[(.*?)\]', json_str, re.DOTALL)
            if not m:
                return []
            return [t.strip().strip('"\'') for t in m.group(1).split(",") if t.strip().strip('"\'')]
        data = {
            "title":       _get("title"),
            "slug":        _get("slug"),
            "meta_desc":   _get("meta_desc"),
            "alt_text":    _get("alt_text"),
            "h1":          _get("h1"),
            "description": _get("description"),
            "tags":        _get_list("tags"),
        }

    # Validate required fields
    required = ["title", "slug", "description", "meta_desc"]
    if not all(data.get(k, "").strip() for k in required):
        return None

    # Enforce 20-word minimum title
    title_words = data["title"].split()
    if len(title_words) < 20:
        subj    = row.get("subject_name", "")
        cat     = row.get("category", "").replace("_", " ").title()
        padding = f"Download free high-quality {subj} transparent PNG image for {cat} design projects at UltraPNG"
        data["title"] = data["title"].rstrip(" .") + " — " + padding
        data["title"] = " ".join(data["title"].split()[:25])

    # Fix slug
    data["slug"] = slugify(data.get("slug") or data["title"])

    # Ensure 10 tags
    if not isinstance(data.get("tags"), list):
        data["tags"] = []
    while len(data["tags"]) < 5:
        subj = row.get("subject_name", "image")
        data["tags"].append(f"{subj} png")

    return data

def generate_seo(manifest_rows, published_fnames, token):
    """
    For each row in manifest that is not published:
    - PNG exists → process
    - PNG missing, WebP missing → skip (user deleted)
    - PNG missing, WebP exists → skip (user deleted PNG)
    - PNG exists, WebP missing → create WebP → upload → process
    Returns list of SEO result dicts.
    """
    log("=" * 56)
    log(f"Loading Gemma 3 4B — {GEMMA_HF_ID}")
    log("=" * 56)

    # ── Apply run options ─────────────────────────────────────
    if SEO_CATEGORY_FILTER:
        manifest_rows = [r for r in manifest_rows
                         if r.get("category", "").lower() == SEO_CATEGORY_FILTER.lower()]
        log(f"  Category filter: '{SEO_CATEGORY_FILTER}' → {len(manifest_rows)} rows")

    if SEO_FORCE_REPROCESS:
        pending = manifest_rows
        log(f"  Force reprocess ON → {len(pending)} rows (ignoring published)")
    else:
        pending = [r for r in manifest_rows if r.get("filename") not in published_fnames]
        log(f"  Pending: {len(pending)} | Already published: {len(published_fnames)}")

    if SEO_LIMIT and SEO_LIMIT > 0:
        pending = pending[:SEO_LIMIT]
        log(f"  Limit applied → processing {len(pending)} items")

    if not pending:
        log("  Nothing to process — all published!")
        return []

    # Drive check: classify each row
    to_process   = []   # rows to generate SEO for
    skip_deleted = []   # PNG gone, user deleted
    webp_fixed   = 0    # WebP was missing → we created + uploaded it

    log(f"\n  Drive checking {len(pending)} items...")
    checked = 0
    for row in pending:
        if checked > 0 and checked % 100 == 0:
            token = get_drive_token()

        png_id  = row.get("png_id", "")
        webp_id = row.get("webp_id", "")
        fname   = row.get("filename", "")

        png_ok  = drive_file_exists(token, png_id)
        webp_ok = drive_file_exists(token, webp_id)

        if not png_ok:
            # User deleted PNG → skip entirely
            skip_deleted.append(fname)
            log(f"  SKIP (PNG deleted): {fname}")
        elif not webp_ok:
            # PNG ok but WebP missing → recreate WebP from PNG
            try:
                log(f"  Fixing missing WebP: {fname}")
                png_bytes  = drive_download_file(token, png_id)
                webp_bytes = make_webp_from_png_bytes(png_bytes)
                # Find parent folder of the PNG to upload WebP alongside
                wbp_root = _get_or_create_webp_root(token, row)
                wr = drive_upload(token, Path(fname).stem + ".webp",
                                  webp_bytes, "image/webp", folder_id=wbp_root)
                drive_share(token, wr["id"])
                row["webp_id"]  = wr["id"]
                row["webp_url"] = preview_url(wr["id"], WEBP_SIZE)
                webp_fixed += 1
                to_process.append(row)
            except Exception as e:
                log(f"  WebP fix failed {fname}: {e} — processing anyway")
                to_process.append(row)
        else:
            # Both exist → process
            to_process.append(row)

        checked += 1

    log(f"\n  To process: {len(to_process)} | Skipped (deleted): {len(skip_deleted)} | WebP fixed: {webp_fixed}")

    if not to_process:
        return []

    # Load Gemma 3 4B
    from transformers import AutoTokenizer, AutoModelForCausalLM

    tokenizer = AutoTokenizer.from_pretrained(GEMMA_HF_ID, cache_dir=str(HF_CACHE))
    dtype_name = "float16" if _IS_P100 else "bfloat16"
    log(f"  Loading Gemma with {dtype_name} (GPU: {'P100' if _IS_P100 else 'modern'})")
    model = AutoModelForCausalLM.from_pretrained(
        GEMMA_HF_ID,
        torch_dtype=_TORCH_DTYPE,
        device_map="auto",
        cache_dir=str(HF_CACHE),
    )
    model.eval()
    device = next(model.parameters()).device
    log(f"  Gemma 3 4B loaded on {device} | {dtype_name}\n")

    results  = []
    total    = len(to_process)
    t0       = time.time()
    fail_cnt = 0

    for i, row in enumerate(to_process):
        fname = row.get("filename", "")
        try:
            messages = [
                {"role": "system", "content": SEO_SYSTEM},
                {"role": "user",   "content": build_user_prompt(row)},
            ]
            text   = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True)
            inputs = tokenizer(text, return_tensors="pt").to(device)

            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=900,
                    do_sample=False,
                    pad_token_id=tokenizer.eos_token_id,
                )

            new_tokens = outputs[0][inputs["input_ids"].shape[1]:]
            raw = tokenizer.decode(new_tokens, skip_special_tokens=True)

            seo = parse_gemma_json(raw, row)
            if seo:
                results.append({"row": row, "seo": seo})
                rate = (i + 1) / max(time.time() - t0, 1)
                eta  = (total - i - 1) / max(rate, 0.01) / 60
                log(f"  [{i+1}/{total}] OK {fname} | {len(seo['title'].split())}w title | ETA {eta:.0f}min")
            else:
                fail_cnt += 1
                log(f"  [{i+1}/{total}] PARSE FAIL {fname}")

            if (i + 1) % 50 == 0:
                free_memory()

        except torch.cuda.OutOfMemoryError:
            free_memory()
            fail_cnt += 1
            log(f"  OOM: {fname}")
        except Exception as e:
            fail_cnt += 1
            log(f"  FAIL {fname}: {e}")

    log(f"\n  Gemma done: {len(results)} OK | {fail_cnt} failed\n")

    # Unload Gemma
    del model, tokenizer
    free_memory()
    for c in HF_CACHE.iterdir():
        if c.is_dir() and "gemma" in c.name.lower():
            shutil.rmtree(str(c), ignore_errors=True)

    return results

def _get_or_create_webp_root(token, row):
    """Get/create webp folder for this row's category/subcategory."""
    cat = row.get("category", "general")
    sub = row.get("subcategory", "general")
    # FIX: lru_cache was imported inside this function but never applied to anything.
    # _find_or_make_folder was called fresh every time, making 3 Drive API calls per image.
    # Now using a simple dict cache so repeated cat/sub combos skip Drive API entirely.
    root = _find_or_make_folder_cached(token, "ultrapng_webp", None)
    croot = _find_or_make_folder_cached(token, cat, root)
    return _find_or_make_folder_cached(token, sub, croot)

_folder_cache = {}

def _find_or_make_folder_cached(token, name, parent):
    """Cached wrapper — avoids repeated Drive API calls for same folder."""
    key = (name, parent)
    if key in _folder_cache:
        return _folder_cache[key]
    fid = _find_or_make_folder(token, name, parent)
    _folder_cache[key] = fid
    return fid

def _find_or_make_folder(token, name, parent):
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

# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
def main():
    t0    = time.time()
    stats = {"status": "RUNNING", "manifest_rows": 0, "pending": 0,
             "published": 0, "skipped": 0, "parse_fail": 0}

    try:
        try:
            p = torch.cuda.get_device_properties(0)
            print(f"\n{'='*56}")
            print(f"  UltraPNG SEO Pipeline")
            print(f"  manifest.csv → Drive check → Gemma 3 4B → Repo2")
            print(f"  GPU: {p.name} | {p.total_memory/1e9:.0f}GB VRAM")
            print(f"{'='*56}\n")
        except Exception:
            pass

        # Step 1: Download manifest.csv
        log("Step 1: Downloading manifest.csv from Drive...")
        token = get_drive_token()
        manifest_rows, _ = download_manifest(token)
        stats["manifest_rows"] = len(manifest_rows)

        if not manifest_rows:
            log("  No manifest rows — run Trigger 1 first!")
            # FIX: stats status was left as "RUNNING" — now marked correctly
            hrs = (time.time() - t0) / 3600
            stats.update({"duration": f"{hrs:.1f}h", "status": "SUCCESS"})
            return

        # Step 2: Clone Repo2 + load published filenames
        log("\nStep 2: Loading Repo2 published items...")
        clone_repo2()
        published_fnames = load_published_slugs()

        # Step 3 + 4: Drive check + Gemma SEO generation
        log("\nStep 3+4: Drive check + SEO generation...")
        seo_results = generate_seo(manifest_rows, published_fnames, token)
        stats["published"]  = len(seo_results)
        stats["parse_fail"] = sum(1 for r in manifest_rows
                                  if r.get("filename") not in published_fnames) - len(seo_results)

        if not seo_results:
            log("  No SEO results to push.")
            # FIX: stats status was left as "RUNNING" — now marked correctly
            hrs = (time.time() - t0) / 3600
            stats.update({"duration": f"{hrs:.1f}h", "status": "SUCCESS"})
            return

        # Step 5: Build category JSONs + push to Repo2
        log("\nStep 5: Building Repo2 JSON + pushing...")
        used_slugs  = set()
        by_category = {}

        for result in seo_results:
            row = result["row"]
            seo = result["seo"]

            # Unique slug guarantee
            base_slug = seo["slug"]
            slug = base_slug
            suffix = 2
            while slug in used_slugs:
                slug = f"{base_slug}-{suffix}"
                suffix += 1
            used_slugs.add(slug)

            cat = row.get("category", "general")
            item = {
                "filename":     row["filename"],
                "subject_name": row.get("subject_name", ""),
                "category":     cat,
                "subcategory":  row.get("subcategory", "general"),
                "png_id":       row.get("png_id", ""),
                "webp_id":      row.get("webp_id", ""),
                "png_url":      row.get("png_url", ""),
                "webp_url":     row.get("webp_url", ""),
                "title":        seo.get("title", ""),
                "h1":           seo.get("h1", ""),
                "slug":         slug,
                "meta_desc":    seo.get("meta_desc", ""),
                "alt_text":     seo.get("alt_text", ""),
                "description":  seo.get("description", ""),
                "tags":         seo.get("tags", []),
                "page_url":     f"{SITE_URL}/png-library/{cat}/{slug}/",
                "date_added":   row.get("date_added", datetime.now().strftime("%Y-%m-%d")),
                "seo_date":     datetime.now().strftime("%Y-%m-%d"),
            }
            by_category.setdefault(cat, []).append(item)

        push_repo2(by_category, len(seo_results))

        hrs = (time.time() - t0) / 3600
        stats.update({"duration": f"{hrs:.1f}h", "status": "SUCCESS"})
        print(f"\n{'='*56}")
        print(f"  SEO DONE in {hrs:.1f}h")
        print(f"  Published: {len(seo_results)} | ParseFail: {stats['parse_fail']}")
        print(f"{'='*56}")

    except Exception as e:
        stats.update({"duration": f"{(time.time()-t0)/3600:.1f}h",
                      "status": f"FAILED: {str(e)[:80]}"})
        log(f"FATAL: {e}")
        raise
    finally:
        # Save logs to Repo1
        try:
            if REPO1_DIR.exists():
                shutil.rmtree(str(REPO1_DIR))
            url = f"https://x-access-token:{GITHUB_TOKEN_REPO1}@github.com/{GITHUB_REPO1}.git"
            subprocess.run(["git", "clone", "--depth=1", url, str(REPO1_DIR)],
                           check=True, capture_output=True)
            logs_dir = REPO1_DIR / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            date_str = datetime.now().strftime("%Y-%m-%d_%H%M")
            (logs_dir / f"seo_{date_str}.txt").write_text("\n".join(_LOG_LINES), "utf-8")
            (logs_dir / f"seo_{date_str}_stats.json").write_text(
                json.dumps(stats, ensure_ascii=False, indent=2), "utf-8")
            env = {**os.environ,
                   "GIT_AUTHOR_NAME": "UltraPNG Bot",
                   "GIT_AUTHOR_EMAIL": "bot@ultrapng.com",
                   "GIT_COMMITTER_NAME": "UltraPNG Bot",
                   "GIT_COMMITTER_EMAIL": "bot@ultrapng.com"}
            subprocess.run(["git", "-C", str(REPO1_DIR), "add", "-A"],
                           check=True, env=env, capture_output=True)
            r2 = subprocess.run(["git", "-C", str(REPO1_DIR), "diff", "--cached", "--quiet"])
            if r2.returncode != 0:
                subprocess.run(
                    ["git", "-C", str(REPO1_DIR), "commit", "-m", f"SEO log {date_str}"],
                    check=True, env=env, capture_output=True)
                subprocess.run(["git", "-C", str(REPO1_DIR), "push"],
                               check=True, env=env, capture_output=True)
            log("  Logs pushed to Repo1 ✅")
        except Exception as le:
            log(f"  Log push failed (non-fatal): {le}")

if __name__ == "__main__":
    main()
