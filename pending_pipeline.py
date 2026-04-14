"""
╔══════════════════════════════════════════════════════════════════╗
║   Pending Drive Pipeline  V3.0                                   ║
╠══════════════════════════════════════════════════════════════════╣
║  PHASE 1 → Discovery     List pending folder + subfolders        ║
║  PHASE 2 → Download      Batch download JPG/PNG from Drive       ║
║  PHASE 3 → rembg 2       BRIA birefnet-general bg removal (HF)  ║
║  PHASE 4 → Preview       WebP <80KB + diagonal watermark         ║
║  PHASE 5 → Drive Upload  Original PNG → png_library_images/      ║
║  PHASE 6 → GitHub Upload Preview WebP → guruimageusha/preview_png║
║  PHASE 7 → Move          Original → pending/finished/{subfolder} ║
║  PHASE 8 → ultradata     Append rows → ultrapng/ultradata.xlsx   ║
╚══════════════════════════════════════════════════════════════════╝

inject_creds_pending.py prepends:
  GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REFRESH_TOKEN
  GH_TOKEN / GH_OWNER
os.environ lines before this file.
"""

import os, sys, json, time, gc, io, subprocess, math, base64
from pathlib import Path
from datetime import datetime

try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except AttributeError:
    pass

HF_CACHE = Path("/kaggle/working/hf_cache")
HF_CACHE.mkdir(parents=True, exist_ok=True)
os.environ["HF_HOME"]               = str(HF_CACHE)
os.environ["HUGGINGFACE_HUB_CACHE"] = str(HF_CACHE)
os.environ["TRANSFORMERS_CACHE"]    = str(HF_CACHE)

# ══════════════════════════════════════════════════════════════════
#  ✏️  USER CONFIG  — edit these values directly
# ══════════════════════════════════════════════════════════════════
RUN_ITEMS_COUNT     = 50                  # Images to process per run
WATERMARK_TEXT      = "www.ultrapng.com"  # Watermark & footer text
PENDING_FOLDER_NAME = "pending"           # Source Drive folder name
REMBG_MODEL         = "birefnet-general"  # BRIA AI — best quality in rembg 2
BATCH_SIZE          = 50                  # Upload batch size

PREVIEW_MAX_SIDE    = 800                 # Max side (px) for preview WebP
PREVIEW_MAX_BYTES   = 80 * 1024          # 80 KB hard limit for preview WebP

PREVIEW_REPO        = "guruimageusha"     # GitHub repo for preview WebPs
PREVIEW_BRANCH      = "main"
PREVIEW_FOLDER      = "preview_png"       # Folder inside guruimageusha repo

ULTRADATA_REPO      = "ultrapng"          # GitHub repo that holds ultradata.xlsx
ULTRADATA_FILE      = "ultradata.xlsx"    # xlsx path in ultrapng repo
ULTRADATA_BRANCH    = "main"
# ══════════════════════════════════════════════════════════════════

# Drive credentials — injected by inject_creds_pending.py
GOOGLE_CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN", "")

# GitHub credentials — injected by inject_creds_pending.py
GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_OWNER = os.environ.get("GH_OWNER", "")

WORKING_DIR     = Path("/kaggle/working")
DOWNLOAD_DIR    = WORKING_DIR / "downloads"
TRANSPARENT_DIR = WORKING_DIR / "transparent"
PREVIEW_DIR     = WORKING_DIR / "previews"

for d in [DOWNLOAD_DIR, TRANSPARENT_DIR, PREVIEW_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ══════════════════════════════════════════════════════════════════
# INSTALL DEPENDENCIES
# ══════════════════════════════════════════════════════════════════
print("=" * 64)
print("Installing dependencies...")
PKGS = [
    "Pillow>=10.0",
    "numpy",
    "requests",
    "openpyxl",
    "rembg[gpu]>=2.0.0",       # rembg v2 — birefnet-general from HuggingFace
    "onnxruntime-gpu",
]
for pkg in PKGS:
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "--no-warn-script-location", pkg],
        capture_output=True, text=True
    )
    print(f"  {'OK  ' if r.returncode == 0 else 'WARN'} {pkg}")
print("Done!\n")

import torch
from PIL import Image, ImageDraw, ImageFont
import requests as req

# ══════════════════════════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════════════════════════
_LOG_LINES = []

def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    _LOG_LINES.append(line)

def log_section(title):
    log("=" * 64)
    log(title)
    log("=" * 64)

# ══════════════════════════════════════════════════════════════════
# GPU UTILITIES
# ══════════════════════════════════════════════════════════════════
def free_memory():
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
    used = torch.cuda.memory_allocated(0) / 1e9 if torch.cuda.is_available() else 0
    log(f"  GPU freed → {used:.2f} GB remaining")

def gpu_info():
    if torch.cuda.is_available():
        name  = torch.cuda.get_device_name(0)
        total = torch.cuda.get_device_properties(0).total_memory / 1e9
        used  = torch.cuda.memory_allocated(0) / 1e9
        log(f"  GPU: {name} | {used:.1f}/{total:.1f} GB")
    else:
        log("  GPU: not available — running on CPU")

# ══════════════════════════════════════════════════════════════════
# GOOGLE DRIVE API
# ══════════════════════════════════════════════════════════════════
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
        raise RuntimeError(f"Drive token error: {d}")
    _token_cache.update({"value": d["access_token"], "expires": time.time() + 3200})
    return _token_cache["value"]

def _h(token):
    return {"Authorization": f"Bearer {token}"}

def _gh(token):
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

def drive_list(token, folder_id, mime_filter=None):
    q = f"'{folder_id}' in parents and trashed=false"
    if mime_filter:
        q += f" and mimeType='{mime_filter}'"
    results, page_token = [], None
    while True:
        params = {"q": q, "pageSize": 1000,
                  "fields": "nextPageToken,files(id,name,mimeType,parents)"}
        if page_token:
            params["pageToken"] = page_token
        r = req.get("https://www.googleapis.com/drive/v3/files",
                    headers=_h(token), params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        results.extend(data.get("files", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return results

def drive_list_images(token, folder_id):
    q = (
        f"'{folder_id}' in parents and trashed=false and "
        "(mimeType='image/jpeg' or mimeType='image/png' or "
        " name contains '.jpg' or name contains '.jpeg' or name contains '.png')"
    )
    results, page_token = [], None
    while True:
        params = {"q": q, "pageSize": 1000,
                  "fields": "nextPageToken,files(id,name,mimeType,parents)"}
        if page_token:
            params["pageToken"] = page_token
        r = req.get("https://www.googleapis.com/drive/v3/files",
                    headers=_h(token), params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        results.extend(data.get("files", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return results

def drive_folder_get_or_create(token, name, parent_id=None):
    q = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        q += f" and '{parent_id}' in parents"
    r = req.get("https://www.googleapis.com/drive/v3/files",
                headers=_h(token),
                params={"q": q, "fields": "files(id)", "pageSize": 1},
                timeout=30)
    files = r.json().get("files", [])
    if files:
        return files[0]["id"]
    meta = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        meta["parents"] = [parent_id]
    r2 = req.post("https://www.googleapis.com/drive/v3/files",
                  headers={**_h(token), "Content-Type": "application/json"},
                  json=meta, timeout=30)
    r2.raise_for_status()
    return r2.json()["id"]

def drive_upload(token, folder_id, name, data: bytes, mime="image/png", retries=3):
    for attempt in range(1, retries + 1):
        try:
            metadata = json.dumps({"name": name, "parents": [folder_id]})
            boundary = "----PendingPipe3"
            body = (
                f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
                f"{metadata}\r\n--{boundary}\r\nContent-Type: {mime}\r\n\r\n"
            ).encode() + data + f"\r\n--{boundary}--".encode()
            r = req.post(
                "https://www.googleapis.com/upload/drive/v3/files"
                "?uploadType=multipart&fields=id,name",
                headers={**_h(token), "Content-Type": f'multipart/related; boundary="{boundary}"'},
                data=body, timeout=180)
            if r.ok:
                return r.json()
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:
            if attempt < retries:
                log(f"    Upload retry {attempt}/{retries}: {e}")
                time.sleep(6 * attempt)
            else:
                raise

def drive_share(token, fid):
    try:
        req.post(
            f"https://www.googleapis.com/drive/v3/files/{fid}/permissions",
            headers={**_h(token), "Content-Type": "application/json"},
            json={"role": "reader", "type": "anyone"}, timeout=30)
    except Exception:
        pass

def drive_move(token, fid, add_parent_id, remove_parent_id):
    r = req.patch(
        f"https://www.googleapis.com/drive/v3/files/{fid}",
        headers=_h(token),
        params={"addParents": add_parent_id, "removeParents": remove_parent_id,
                "fields": "id,parents"},
        timeout=30)
    r.raise_for_status()
    return r.json()

def drive_download_bytes(token, fid):
    r = req.get(f"https://www.googleapis.com/drive/v3/files/{fid}",
                headers=_h(token), params={"alt": "media"}, timeout=180)
    r.raise_for_status()
    return r.content

# ══════════════════════════════════════════════════════════════════
# GITHUB API
# ══════════════════════════════════════════════════════════════════
def github_get_sha(token, owner, repo, path, branch="main"):
    """Return existing file SHA (needed for update), or None if new file."""
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    r = req.get(url, headers=_gh(token), params={"ref": branch}, timeout=30)
    if r.status_code == 200:
        return r.json().get("sha")
    return None

def github_upload_file(token, owner, repo, path, content_bytes, message,
                       branch="main", retries=3):
    """Create or update a file in a GitHub repo via Contents API."""
    url  = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    sha  = github_get_sha(token, owner, repo, path, branch)
    body = {
        "message": message,
        "content": base64.b64encode(content_bytes).decode(),
        "branch":  branch,
    }
    if sha:
        body["sha"] = sha
    for attempt in range(1, retries + 1):
        try:
            r = req.put(url,
                        headers={**_gh(token), "Content-Type": "application/json"},
                        json=body, timeout=90)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt < retries:
                log(f"    GH retry {attempt}/{retries}: {e}")
                time.sleep(5 * attempt)
            else:
                raise

def jsdelivr_url(owner, repo, branch, path):
    """Return a jsDelivr CDN URL for a GitHub file."""
    return f"https://cdn.jsdelivr.net/gh/{owner}/{repo}@{branch}/{path}"

# ══════════════════════════════════════════════════════════════════
# PNG PREVIEW  (checkered BG + diagonal watermark + footer, <80 KB)
# ══════════════════════════════════════════════════════════════════
def _get_font(size=13):
    for path in [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()

def _render_preview(img_rgba: Image.Image) -> Image.Image:
    """Compose checkered bg + RGBA image + diagonal watermark + footer bar."""
    w, h = img_rgba.size

    # ── Checkered background ──────────────────────────────────────
    cs  = 20
    bg  = Image.new("RGB", (w, h), (255, 255, 255))
    drw = ImageDraw.Draw(bg)
    for ry in range(0, h, cs):
        for cx in range(0, w, cs):
            if (ry // cs + cx // cs) % 2 == 1:
                drw.rectangle([cx, ry, cx + cs, ry + cs], fill=(232, 232, 232))
    bg.paste(img_rgba.convert("RGB"), mask=img_rgba.split()[3])

    # ── Diagonal watermark ────────────────────────────────────────
    fnt_wm   = _get_font(12)
    wm_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    wm_draw  = ImageDraw.Draw(wm_layer)
    for ry in range(-h, h + 120, 120):
        for cx in range(-w, w + 120, 120):
            wm_draw.text((cx, ry), WATERMARK_TEXT, fill=(0, 0, 0, 42), font=fnt_wm)
    wm_rot  = wm_layer.rotate(-30, expand=False)
    bg_rgba = bg.convert("RGBA")
    bg_rgba.alpha_composite(wm_rot)
    bg = bg_rgba.convert("RGB")

    # ── Footer bar ────────────────────────────────────────────────
    fnt_ft = _get_font(14)
    drw2   = ImageDraw.Draw(bg)
    drw2.rectangle([0, h - 32, w, h], fill=(13, 13, 20))
    try:
        bbox = drw2.textbbox((0, 0), WATERMARK_TEXT, font=fnt_ft)
        tx   = (w - (bbox[2] - bbox[0])) // 2
    except Exception:
        tx = w // 2 - 72
    drw2.text((tx, h - 22), WATERMARK_TEXT, fill=(245, 166, 35), font=fnt_ft)
    return bg

def make_webp_preview(img_rgba: Image.Image,
                      max_side: int = PREVIEW_MAX_SIDE,
                      max_bytes: int = PREVIEW_MAX_BYTES):
    """
    Render a WebP preview image under max_bytes (80 KB).
    Uses binary-search on WebP quality for maximum quality within the limit.
    Falls back to dimension reduction if quality=5 still exceeds limit.
    Returns (webp_bytes, width, height).
    """
    img_rgba = img_rgba.convert("RGBA")
    ow, oh   = img_rgba.size

    # Initial resize to fit within max_side
    scale = min(1.0, max_side / max(ow, oh, 1))
    rw    = max(int(ow * scale), 60)
    rh    = max(int(oh * scale), 60)
    resized = img_rgba.resize((rw, rh), Image.LANCZOS)
    preview = _render_preview(resized)

    # Binary-search WebP quality → best quality that fits under max_bytes
    lo, hi, best = 5, 92, None
    while lo <= hi:
        mid = (lo + hi) // 2
        buf = io.BytesIO()
        preview.save(buf, "WEBP", quality=mid, method=6)
        if buf.tell() <= max_bytes:
            best = buf.getvalue()
            lo   = mid + 1
        else:
            hi   = mid - 1

    if best is not None:
        return best, preview.width, preview.height

    # Quality=5 still too large → shrink dimensions progressively
    while max(rw, rh) > 80:
        scale *= 0.88
        rw = max(int(ow * scale), 60)
        rh = max(int(oh * scale), 60)
        resized = img_rgba.resize((rw, rh), Image.LANCZOS)
        preview = _render_preview(resized)
        buf = io.BytesIO()
        preview.save(buf, "WEBP", quality=5, method=6)
        if buf.tell() <= max_bytes:
            return buf.getvalue(), preview.width, preview.height

    # Last resort — return whatever we have
    buf = io.BytesIO()
    preview.save(buf, "WEBP", quality=5, method=6)
    return buf.getvalue(), preview.width, preview.height

# ══════════════════════════════════════════════════════════════════
# PHASE 1: DISCOVERY
# ══════════════════════════════════════════════════════════════════
def phase1_discovery():
    log_section("PHASE 1: Discovery")
    token = get_drive_token()

    pending_id = drive_folder_get_or_create(token, PENDING_FOLDER_NAME)
    log(f"  '{PENDING_FOLDER_NAME}' folder ID: {pending_id}")

    subfolders = drive_list(token, pending_id,
                            mime_filter="application/vnd.google-apps.folder")
    subfolders = [sf for sf in subfolders if sf["name"].lower() != "finished"]
    log(f"  Subfolders: {len(subfolders)}")

    all_items = []
    for sf in subfolders:
        if len(all_items) >= RUN_ITEMS_COUNT:
            break
        images = drive_list_images(token, sf["id"])
        log(f"  └─ '{sf['name']}': {len(images)} image(s)")
        for img in images:
            all_items.append({
                "fid":            img["id"],
                "name":           img["name"],
                "stem":           Path(img["name"]).stem,
                "subfolder_id":   sf["id"],
                "subfolder_name": sf["name"],
                "pending_id":     pending_id,
            })
            if len(all_items) >= RUN_ITEMS_COUNT:
                break

    log(f"  Items selected: {len(all_items)}")
    return all_items, pending_id

# ══════════════════════════════════════════════════════════════════
# PHASE 2: DOWNLOAD
# ══════════════════════════════════════════════════════════════════
def phase2_download(items):
    log_section("PHASE 2: Download images from Drive")
    token      = get_drive_token()
    downloaded = []
    for i, item in enumerate(items):
        try:
            token = get_drive_token()
            log(f"  [{i+1:>3}/{len(items)}] {item['name']}")
            data  = drive_download_bytes(token, item["fid"])
            ext   = Path(item["name"]).suffix.lower()
            if ext not in (".jpg", ".jpeg", ".png"):
                ext = ".jpg"
            local = DOWNLOAD_DIR / f"{item['stem']}{ext}"
            local.write_bytes(data)
            item["local_path"] = str(local)
            downloaded.append(item)
        except Exception as e:
            log(f"  FAIL: {item['name']}: {e}")
    log(f"  Downloaded: {len(downloaded)}/{len(items)}")
    return downloaded

# ══════════════════════════════════════════════════════════════════
# PHASE 3: REMBG 2  —  BRIA birefnet-general (HuggingFace)
# ══════════════════════════════════════════════════════════════════
def phase3_remove_bg(items):
    log_section(f"PHASE 3: rembg 2  [{REMBG_MODEL}]  (HuggingFace)")
    gpu_info()

    try:
        from rembg import remove, new_session
    except ImportError as e:
        log(f"  rembg import error: {e}")
        for item in items:
            item["transparent_path"] = item["local_path"]
        return items

    log(f"  Loading session: {REMBG_MODEL} ...")
    session = new_session(REMBG_MODEL)
    log("  Session ready")

    result = []
    for i, item in enumerate(items):
        try:
            # Read directly from original downloaded file — no upscale
            img_bytes = Path(item["local_path"]).read_bytes()
            log(f"  [{i+1:>3}/{len(items)}] {item['name']}")

            out_bytes = remove(img_bytes, session=session)

            dst = TRANSPARENT_DIR / f"{item['stem']}.png"
            dst.write_bytes(out_bytes)
            item["transparent_path"] = str(dst)

            chk  = Image.open(io.BytesIO(out_bytes))
            w, h = chk.size
            log(f"    → {w}×{h} | {len(out_bytes)//1024} KB (transparent PNG)")
            result.append(item)
        except Exception as e:
            log(f"  FAIL rembg [{item['name']}]: {e}")
            item["transparent_path"] = item["local_path"]
            result.append(item)

    del session
    free_memory()
    log(f"  Done: {len(result)}/{len(items)}")
    return result

# ══════════════════════════════════════════════════════════════════
# PHASE 4: PNG PREVIEWS  (<80 KB)
# ══════════════════════════════════════════════════════════════════
def phase4_make_previews(items):
    log_section(f"PHASE 4: WebP previews (<{PREVIEW_MAX_BYTES//1024} KB + watermark)")
    result = []
    for i, item in enumerate(items):
        try:
            img_rgba   = Image.open(item["transparent_path"]).convert("RGBA")
            webp_bytes, pw, ph = make_webp_preview(img_rgba)
            img_rgba.close()

            # Save preview locally
            prev_path = PREVIEW_DIR / f"{item['stem']}.webp"
            prev_path.write_bytes(webp_bytes)

            item["preview_bytes"] = webp_bytes
            item["preview_path"]  = str(prev_path)
            item["preview_w"]     = pw
            item["preview_h"]     = ph
            log(f"  [{i+1:>3}/{len(items)}] {item['name']} → {len(webp_bytes)//1024} KB ({pw}×{ph})")
            result.append(item)
        except Exception as e:
            log(f"  FAIL preview [{item['name']}]: {e}")
    return result

# ══════════════════════════════════════════════════════════════════
# PHASE 5: DRIVE UPLOAD  (original transparent PNG → Google Drive)
# ══════════════════════════════════════════════════════════════════
def phase5_drive_upload(items):
    log_section(f"PHASE 5: Drive upload — original PNG (batch={BATCH_SIZE})")
    token = get_drive_token()

    png_root = drive_folder_get_or_create(token, "png_library_images")
    log(f"  png_library_images → {png_root}")

    _png_cache = {}

    def png_sub(sf):
        if sf not in _png_cache:
            _png_cache[sf] = drive_folder_get_or_create(token, sf, png_root)
        return _png_cache[sf]

    uploaded  = []
    n_batches = math.ceil(len(items) / BATCH_SIZE)

    for b in range(n_batches):
        batch = items[b * BATCH_SIZE : (b + 1) * BATCH_SIZE]
        log(f"\n  ── Batch {b+1}/{n_batches}  ({len(batch)} items) ──")
        for j, item in enumerate(batch):
            try:
                token     = get_drive_token()
                sf        = item["subfolder_name"]
                stem      = item["stem"]

                png_bytes = Path(item["transparent_path"]).read_bytes()
                png_res   = drive_upload(token, png_sub(sf),
                                         f"{stem}.png", png_bytes, "image/png")
                drive_share(token, png_res["id"])

                item["png_drive_id"] = png_res["id"]
                uploaded.append(item)
                log(f"    [{j+1:>2}/{len(batch)}] ✓ {stem}.png → Drive")
            except Exception as e:
                log(f"    FAIL Drive upload [{item['name']}]: {e}")

    log(f"\n  Uploaded to Drive: {len(uploaded)}/{len(items)}")
    return uploaded

# ══════════════════════════════════════════════════════════════════
# PHASE 6: GITHUB UPLOAD  (preview PNG → guruimageusha/preview_png)
# ══════════════════════════════════════════════════════════════════
def phase6_github_upload(items):
    log_section(
        f"PHASE 6: GitHub upload — preview WebP → "
        f"{GH_OWNER}/{PREVIEW_REPO}/{PREVIEW_FOLDER}/"
    )

    if not GH_TOKEN or not GH_OWNER:
        log("  SKIP — GH_TOKEN or GH_OWNER not set")
        for item in items:
            item["preview_cdn_url"] = ""
        return items

    result = []
    for i, item in enumerate(items):
        try:
            stem       = item["stem"]
            gh_path    = f"{PREVIEW_FOLDER}/{stem}.webp"
            webp_bytes = item["preview_bytes"]

            log(f"  [{i+1:>3}/{len(items)}] {stem}.webp "
                f"({len(webp_bytes)//1024} KB) → {PREVIEW_REPO}/{gh_path}")

            github_upload_file(
                token         = GH_TOKEN,
                owner         = GH_OWNER,
                repo          = PREVIEW_REPO,
                path          = gh_path,
                content_bytes = webp_bytes,
                message       = f"preview: add {stem}.webp",
                branch        = PREVIEW_BRANCH,
            )

            cdn_url = jsdelivr_url(GH_OWNER, PREVIEW_REPO, PREVIEW_BRANCH, gh_path)
            item["preview_cdn_url"] = cdn_url
            log(f"    CDN: {cdn_url}")
            result.append(item)

            time.sleep(0.4)   # Gentle rate-limit buffer for GitHub API

        except Exception as e:
            log(f"  FAIL GitHub upload [{item['name']}]: {e}")
            item["preview_cdn_url"] = ""
            result.append(item)

    log(f"  Uploaded to GitHub: {len([x for x in result if x.get('preview_cdn_url')])}/{len(items)}")
    return result

# ══════════════════════════════════════════════════════════════════
# PHASE 7: MOVE ORIGINALS  (pending → pending/finished/{subfolder})
# ══════════════════════════════════════════════════════════════════
def phase7_move_originals(uploaded_items, pending_id):
    log_section("PHASE 7: Move originals → pending/finished/{subfolder}/")
    token       = get_drive_token()
    finished_id = drive_folder_get_or_create(token, "finished", pending_id)
    log(f"  finished/ → {finished_id}")

    _fin_cache = {}

    def fin_sub(sf):
        if sf not in _fin_cache:
            _fin_cache[sf] = drive_folder_get_or_create(token, sf, finished_id)
        return _fin_cache[sf]

    moved = 0
    for item in uploaded_items:
        try:
            token = get_drive_token()
            sf    = item["subfolder_name"]
            drive_move(token, item["fid"], fin_sub(sf), item["subfolder_id"])
            log(f"  ✓ {item['name']} → finished/{sf}/")
            moved += 1
        except Exception as e:
            log(f"  FAIL move [{item['name']}]: {e}")

    log(f"  Moved: {moved}/{len(uploaded_items)}")

# ══════════════════════════════════════════════════════════════════
# PHASE 8: UPDATE ultradata.xlsx  (ultrapng repo)
# ══════════════════════════════════════════════════════════════════
def phase8_update_ultradata(items):
    log_section(
        f"PHASE 8: Update {ULTRADATA_FILE} → "
        f"{GH_OWNER}/{ULTRADATA_REPO}"
    )

    if not GH_TOKEN or not GH_OWNER:
        log("  SKIP — GH_TOKEN or GH_OWNER not set")
        return

    import openpyxl

    # ── Download existing xlsx from ultrapng repo ─────────────────
    url = (
        f"https://api.github.com/repos/{GH_OWNER}/{ULTRADATA_REPO}"
        f"/contents/{ULTRADATA_FILE}"
    )
    r   = req.get(url, headers=_gh(GH_TOKEN),
                  params={"ref": ULTRADATA_BRANCH}, timeout=30)

    if r.status_code == 200:
        data       = r.json()
        file_sha   = data.get("sha")
        xlsx_bytes = base64.b64decode(data["content"].replace("\n", ""))
        wb         = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
        log(f"  Loaded existing {ULTRADATA_FILE} (SHA: {file_sha[:8]}...)")
    else:
        log(f"  {ULTRADATA_FILE} not found — creating new workbook")
        wb       = openpyxl.Workbook()
        file_sha = None

    ws = wb.active

    # ── Detect or create headers ──────────────────────────────────
    HEADERS = ["stem", "category", "drive_id", "preview_cdn", "width", "height", "date"]

    if ws.max_row == 0 or ws.cell(row=1, column=1).value is None:
        ws.append(HEADERS)
        log("  Headers written (new sheet)")
    else:
        existing_headers = [ws.cell(row=1, column=c).value
                            for c in range(1, ws.max_column + 1)]
        log(f"  Existing headers: {existing_headers}")

        # If existing headers differ, map what we have; use our standard order
        # by appending new header columns if missing
        for col_name in HEADERS:
            if col_name not in existing_headers:
                next_col = ws.max_column + 1
                ws.cell(row=1, column=next_col, value=col_name)
                existing_headers.append(col_name)
                log(f"  Added missing column: {col_name}")

        # Re-read headers after possible additions
        HEADERS = [ws.cell(row=1, column=c).value
                   for c in range(1, ws.max_column + 1)]

    # ── Append one row per processed item ────────────────────────
    today = datetime.now().strftime("%Y-%m-%d")
    added = 0
    for item in items:
        row_data = {
            "stem":        item.get("stem", ""),
            "category":    item.get("subfolder_name", ""),
            "drive_id":    item.get("png_drive_id", ""),
            "preview_cdn": item.get("preview_cdn_url", ""),
            "width":       item.get("preview_w", ""),
            "height":      item.get("preview_h", ""),
            "date":        today,
        }
        ws.append([row_data.get(h, "") for h in HEADERS])
        added += 1

    log(f"  Rows appended: {added}")

    # ── Save xlsx to bytes ────────────────────────────────────────
    buf = io.BytesIO()
    wb.save(buf)
    new_xlsx_bytes = buf.getvalue()

    # ── Push back to ultrapng repo ────────────────────────────────
    body = {
        "message": f"ultradata: +{added} images [{today}]",
        "content": base64.b64encode(new_xlsx_bytes).decode(),
        "branch":  ULTRADATA_BRANCH,
    }
    if file_sha:
        body["sha"] = file_sha

    r2 = req.put(url,
                 headers={**_gh(GH_TOKEN), "Content-Type": "application/json"},
                 json=body, timeout=90)
    r2.raise_for_status()
    log(f"  ✓ {ULTRADATA_FILE} updated in {GH_OWNER}/{ULTRADATA_REPO}")

# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════
def main():
    log_section("Pending Drive Pipeline V3.0 — START")
    log(f"  RUN_ITEMS_COUNT  : {RUN_ITEMS_COUNT}")
    log(f"  REMBG_MODEL      : {REMBG_MODEL}  (rembg v2 / HuggingFace)")
    log(f"  PREVIEW_MAX_BYTES: {PREVIEW_MAX_BYTES//1024} KB  WebP")
    log(f"  WATERMARK        : {WATERMARK_TEXT}")
    log(f"  PENDING FOLDER   : {PENDING_FOLDER_NAME}")
    log(f"  PREVIEW_REPO     : {GH_OWNER}/{PREVIEW_REPO}/{PREVIEW_FOLDER}/")
    log(f"  ULTRADATA        : {GH_OWNER}/{ULTRADATA_REPO}/{ULTRADATA_FILE}")
    gpu_info()

    t0 = time.time()

    # ── Phase 1: Discover ──────────────────────────────────────────
    items, pending_id = phase1_discovery()
    if not items:
        log("No items found. Done.")
        return

    # ── Phase 2: Download ─────────────────────────────────────────
    items = phase2_download(items)
    if not items:
        log("Download failed for all items.")
        return

    # ── Phase 3: rembg 2 bg removal ──────────────────────────────
    items = phase3_remove_bg(items)

    # ── Phase 4: PNG previews <80KB ──────────────────────────────
    items = phase4_make_previews(items)

    # ── Phase 5: Upload original PNG → Google Drive ───────────────
    uploaded = phase5_drive_upload(items)

    if not uploaded:
        log("No items uploaded to Drive. Stopping.")
        return

    # ── Phase 6: Upload preview PNG → GitHub guruimageusha ────────
    uploaded = phase6_github_upload(uploaded)

    # ── Phase 7: Move originals in Drive ─────────────────────────
    phase7_move_originals(uploaded, pending_id)

    # ── Phase 8: Update ultradata.xlsx in ultrapng repo ──────────
    phase8_update_ultradata(uploaded)

    elapsed = time.time() - t0
    log_section("DONE")
    log(f"  Processed  : {len(uploaded)}/{len(items)} images")
    log(f"  Time       : {elapsed/60:.1f} min  ({elapsed/max(len(uploaded),1):.0f} sec/image)")


if __name__ == "__main__":
    main()
