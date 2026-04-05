"""
╔══════════════════════════════════════════════════════════════════╗
║   Pending Drive Pipeline  V2.0                                   ║
╠══════════════════════════════════════════════════════════════════╣
║  PHASE 1 → Discovery     List pending folder + subfolders        ║
║  PHASE 2 → Download      Batch download JPG/PNG from Drive       ║
║  PHASE 3 → Real-ESRGAN   2× upscale (GPU, tile-safe P100)       ║
║  PHASE 4 → rembg 2       BRIA birefnet-general bg removal        ║
║  PHASE 5 → Preview       WebP <100KB + diagonal watermark        ║
║  PHASE 6 → Upload        Batch 50 → png_library_images/previews  ║
║  PHASE 7 → Move          Original → pending/finished/{subfolder} ║
╚══════════════════════════════════════════════════════════════════╝

inject_creds_pending.py prepends GOOGLE_CLIENT_ID/SECRET/REFRESH_TOKEN
os.environ lines before this file.
"""

import os, sys, json, time, gc, io, shutil, subprocess, math
from pathlib import Path
from datetime import datetime

try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except AttributeError:
    pass

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

HF_CACHE = Path("/kaggle/working/hf_cache")
HF_CACHE.mkdir(parents=True, exist_ok=True)
os.environ["HF_HOME"]               = str(HF_CACHE)
os.environ["HUGGINGFACE_HUB_CACHE"] = str(HF_CACHE)
os.environ["TRANSFORMERS_CACHE"]    = str(HF_CACHE)

# ══════════════════════════════════════════════════════════════════
#  ✏️  USER CONFIG  — edit these values directly
# ══════════════════════════════════════════════════════════════════
RUN_ITEMS_COUNT     = 50                    # Images to process per run
UPSCALE_FACTOR      = 2                     # 2 or 4
MAX_INPUT_SIZE      = 1200                  # Skip upscale if image already >= this px
WATERMARK_TEXT      = "www.ultrapng.com"    # Watermark & footer text
PENDING_FOLDER_NAME = "pending"             # Source Drive folder name
REMBG_MODEL         = "birefnet-general"    # BRIA AI — best quality in rembg 2
BATCH_SIZE          = 50                    # Upload batch size (keep 50)
# ══════════════════════════════════════════════════════════════════

# Drive credentials — injected by inject_creds_pending.py
GOOGLE_CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN", "")

WORKING_DIR     = Path("/kaggle/working")
DOWNLOAD_DIR    = WORKING_DIR / "downloads"
UPSCALED_DIR    = WORKING_DIR / "upscaled"
TRANSPARENT_DIR = WORKING_DIR / "transparent"
MODEL_DIR       = HF_CACHE / "realesrgan_models"

for d in [DOWNLOAD_DIR, UPSCALED_DIR, TRANSPARENT_DIR, MODEL_DIR]:
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
    "piexif",
    "basicsr",
    "realesrgan",
    "rembg[gpu]",
    "onnxruntime-gpu",
    "opencv-python-headless",
    "torchvision",
]
for pkg in PKGS:
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "--no-warn-script-location", pkg],
        capture_output=True, text=True
    )
    print(f"  {'OK  ' if r.returncode == 0 else 'WARN'} {pkg}")
print("Done!\n")

import torch
import numpy as np
import cv2
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
            boundary = "----PendingPipe2024"
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
# WEBP PREVIEW  (checkered BG + diagonal watermark + footer)
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

def make_webp_preview(img_rgba: Image.Image, max_side=800, max_bytes=100*1024):
    img_rgba = img_rgba.convert("RGBA")
    w, h     = img_rgba.size
    if max(w, h) > max_side:
        scale    = max_side / max(w, h)
        img_rgba = img_rgba.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    w, h = img_rgba.size

    # Checkered background
    cs  = 20
    bg  = Image.new("RGB", (w, h), (255, 255, 255))
    drw = ImageDraw.Draw(bg)
    for ry in range(0, h, cs):
        for cx in range(0, w, cs):
            if (ry // cs + cx // cs) % 2 == 1:
                drw.rectangle([cx, ry, cx + cs, ry + cs], fill=(232, 232, 232))
    bg.paste(img_rgba.convert("RGB"), mask=img_rgba.split()[3])

    # Diagonal watermark
    fnt_wm   = _get_font(13)
    wm_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    wm_draw  = ImageDraw.Draw(wm_layer)
    for ry in range(-h, h + 120, 120):
        for cx in range(-w, w + 120, 120):
            wm_draw.text((cx, ry), WATERMARK_TEXT, fill=(0, 0, 0, 42), font=fnt_wm)
    wm_rot  = wm_layer.rotate(-30, expand=False)
    bg_rgba = bg.convert("RGBA")
    bg_rgba.alpha_composite(wm_rot)
    bg = bg_rgba.convert("RGB")

    # Footer bar
    fnt_ft = _get_font(15)
    drw2   = ImageDraw.Draw(bg)
    drw2.rectangle([0, h - 36, w, h], fill=(13, 13, 20))
    try:
        bbox = drw2.textbbox((0, 0), WATERMARK_TEXT, font=fnt_ft)
        tx   = (w - (bbox[2] - bbox[0])) // 2
    except Exception:
        tx = w // 2 - 72
    drw2.text((tx, h - 26), WATERMARK_TEXT, fill=(245, 166, 35), font=fnt_ft)

    # Binary-search quality → fit under max_bytes
    lo, hi, best = 5, 92, None
    while lo <= hi:
        mid = (lo + hi) // 2
        buf = io.BytesIO()
        bg.save(buf, "WEBP", quality=mid, method=6)
        if buf.tell() <= max_bytes:
            best = buf.getvalue()
            lo   = mid + 1
        else:
            hi   = mid - 1

    if best is None:
        buf = io.BytesIO()
        bg.save(buf, "WEBP", quality=5, method=6)
        best = buf.getvalue()

    return best, w, h

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
# PHASE 3: REAL-ESRGAN UPSCALE
# ══════════════════════════════════════════════════════════════════
def _download_model(url, dest: Path):
    if dest.exists():
        return
    log(f"  Downloading model weights: {dest.name} ...")
    r = req.get(url, stream=True, timeout=300)
    r.raise_for_status()
    tmp = str(dest) + ".tmp"
    with open(tmp, "wb") as f:
        for chunk in r.iter_content(1024 * 1024):
            f.write(chunk)
    os.replace(tmp, str(dest))
    log(f"  Saved: {dest}")

def phase3_upscale(items):
    log_section(f"PHASE 3: Real-ESRGAN {UPSCALE_FACTOR}× upscale")
    gpu_info()

    try:
        from basicsr.archs.rrdbnet_arch import RRDBNet
        from realesrgan import RealESRGANer
    except ImportError as e:
        log(f"  Import error: {e} — using originals")
        for item in items:
            item["upscaled_path"] = item["local_path"]
        return items

    device = "cuda" if torch.cuda.is_available() else "cpu"

    if UPSCALE_FACTOR == 4:
        url  = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth"
        name = "RealESRGAN_x4plus.pth"
        arch = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64,
                       num_block=23, num_grow_ch=32, scale=4)
    else:
        url  = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth"
        name = "RealESRGAN_x2plus.pth"
        arch = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64,
                       num_block=23, num_grow_ch=32, scale=2)

    _download_model(url, MODEL_DIR / name)

    upsampler = RealESRGANer(
        scale=UPSCALE_FACTOR,
        model_path=str(MODEL_DIR / name),
        model=arch,
        tile=400,
        tile_pad=10,
        pre_pad=0,
        half=(device == "cuda"),
        device=device,
    )
    log(f"  Loaded on {device.upper()} | tile=400 | half={'yes' if device=='cuda' else 'no'}")

    upscaled = []
    for i, item in enumerate(items):
        try:
            src     = Path(item["local_path"])
            img_bgr = cv2.imread(str(src), cv2.IMREAD_COLOR)
            if img_bgr is None:
                pil     = Image.open(str(src)).convert("RGB")
                img_bgr = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

            h0, w0   = img_bgr.shape[:2]
            out_path = UPSCALED_DIR / f"{item['stem']}_up.png"
            log(f"  [{i+1:>3}/{len(items)}] {item['name']}  ({w0}×{h0})")

            if max(h0, w0) >= MAX_INPUT_SIZE:
                log(f"    Already large — skip upscale")
                pil = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
                pil.save(str(out_path), "PNG")
            else:
                output, _ = upsampler.enhance(img_bgr, outscale=UPSCALE_FACTOR)
                h1, w1    = output.shape[:2]
                cv2.imwrite(str(out_path), output)
                log(f"    → {w1}×{h1}")

            item["upscaled_path"] = str(out_path)
            upscaled.append(item)
        except Exception as e:
            log(f"  FAIL upscale [{item['name']}]: {e}")
            item["upscaled_path"] = item["local_path"]
            upscaled.append(item)

    del upsampler, arch
    free_memory()
    log(f"  Done: {len(upscaled)}/{len(items)}")
    return upscaled

# ══════════════════════════════════════════════════════════════════
# PHASE 4: REMBG 2  —  BRIA birefnet-general
# ══════════════════════════════════════════════════════════════════
def phase4_remove_bg(items):
    log_section(f"PHASE 4: rembg 2  [{REMBG_MODEL}]")
    gpu_info()

    try:
        from rembg import remove, new_session
    except ImportError as e:
        log(f"  rembg import error: {e}")
        for item in items:
            item["transparent_path"] = item["upscaled_path"]
        return items

    log(f"  Loading session: {REMBG_MODEL} ...")
    session = new_session(REMBG_MODEL)
    log("  Session ready")

    result = []
    for i, item in enumerate(items):
        try:
            img_bytes = Path(item["upscaled_path"]).read_bytes()
            log(f"  [{i+1:>3}/{len(items)}] {item['name']}")

            out_bytes = remove(img_bytes, session=session)

            dst = TRANSPARENT_DIR / f"{item['stem']}.png"
            dst.write_bytes(out_bytes)
            item["transparent_path"] = str(dst)

            chk  = Image.open(io.BytesIO(out_bytes))
            w, h = chk.size
            log(f"    → {w}×{h} | {len(out_bytes)//1024} KB")
            result.append(item)
        except Exception as e:
            log(f"  FAIL rembg [{item['name']}]: {e}")
            item["transparent_path"] = item["upscaled_path"]
            result.append(item)

    del session
    free_memory()
    log(f"  Done: {len(result)}/{len(items)}")
    return result

# ══════════════════════════════════════════════════════════════════
# PHASE 5: WEBP PREVIEWS
# ══════════════════════════════════════════════════════════════════
def phase5_make_previews(items):
    log_section("PHASE 5: WebP previews (<100 KB + watermark)")
    result = []
    for i, item in enumerate(items):
        try:
            img_rgba = Image.open(item["transparent_path"]).convert("RGBA")
            webp_bytes, pw, ph = make_webp_preview(img_rgba)
            img_rgba.close()
            item["webp_bytes"] = webp_bytes
            item["preview_w"]  = pw
            item["preview_h"]  = ph
            log(f"  [{i+1:>3}/{len(items)}] {item['name']} → {len(webp_bytes)//1024} KB ({pw}×{ph})")
            result.append(item)
        except Exception as e:
            log(f"  FAIL preview [{item['name']}]: {e}")
    return result

# ══════════════════════════════════════════════════════════════════
# PHASE 6: UPLOAD  (batch 50)
# ══════════════════════════════════════════════════════════════════
def phase6_upload(items):
    log_section(f"PHASE 6: Upload to Google Drive (batch={BATCH_SIZE})")
    token = get_drive_token()

    png_root  = drive_folder_get_or_create(token, "png_library_images")
    prev_root = drive_folder_get_or_create(token, "png_library_previews")
    log(f"  png_library_images   → {png_root}")
    log(f"  png_library_previews → {prev_root}")

    _png_cache  = {}
    _prev_cache = {}

    def png_sub(sf):
        if sf not in _png_cache:
            _png_cache[sf] = drive_folder_get_or_create(token, sf, png_root)
        return _png_cache[sf]

    def prev_sub(sf):
        if sf not in _prev_cache:
            _prev_cache[sf] = drive_folder_get_or_create(token, sf, prev_root)
        return _prev_cache[sf]

    uploaded  = []
    n_batches = math.ceil(len(items) / BATCH_SIZE)

    for b in range(n_batches):
        batch = items[b * BATCH_SIZE : (b + 1) * BATCH_SIZE]
        log(f"\n  ── Batch {b+1}/{n_batches}  ({len(batch)} items) ──")
        for j, item in enumerate(batch):
            try:
                token = get_drive_token()
                sf    = item["subfolder_name"]
                stem  = item["stem"]

                png_bytes = Path(item["transparent_path"]).read_bytes()
                png_res   = drive_upload(token, png_sub(sf), f"{stem}.png", png_bytes, "image/png")
                drive_share(token, png_res["id"])

                webp_res  = drive_upload(token, prev_sub(sf), f"{stem}.webp",
                                         item["webp_bytes"], "image/webp")
                drive_share(token, webp_res["id"])

                item["png_file_id"]  = png_res["id"]
                item["webp_file_id"] = webp_res["id"]
                uploaded.append(item)
                log(f"    [{j+1:>2}/{len(batch)}] ✓ {stem}.png + {stem}.webp")
            except Exception as e:
                log(f"    FAIL upload [{item['name']}]: {e}")

    log(f"\n  Uploaded: {len(uploaded)}/{len(items)}")
    return uploaded

# ══════════════════════════════════════════════════════════════════
# PHASE 7: MOVE ORIGINALS
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
# MAIN
# ══════════════════════════════════════════════════════════════════
def main():
    log_section("Pending Drive Pipeline V2.0 — START")
    log(f"  RUN_ITEMS_COUNT : {RUN_ITEMS_COUNT}")
    log(f"  UPSCALE_FACTOR  : {UPSCALE_FACTOR}×  (skip if ≥ {MAX_INPUT_SIZE}px)")
    log(f"  REMBG_MODEL     : {REMBG_MODEL}")
    log(f"  WATERMARK       : {WATERMARK_TEXT}")
    log(f"  PENDING FOLDER  : {PENDING_FOLDER_NAME}")
    gpu_info()

    t0 = time.time()

    items, pending_id = phase1_discovery()
    if not items:
        log("No items found. Done.")
        return

    items = phase2_download(items)
    if not items:
        log("Download failed for all items.")
        return

    items    = phase3_upscale(items)
    items    = phase4_remove_bg(items)
    items    = phase5_make_previews(items)
    uploaded = phase6_upload(items)

    if uploaded:
        phase7_move_originals(uploaded, pending_id)

    elapsed = time.time() - t0
    log_section("DONE")
    log(f"  Processed : {len(uploaded)}/{len(items)} images")
    log(f"  Time      : {elapsed/60:.1f} min  ({elapsed/max(len(uploaded),1):.0f} sec/image)")


if __name__ == "__main__":
    main()
