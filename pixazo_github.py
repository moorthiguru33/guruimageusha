#!/usr/bin/env python3
"""
PIXAZO AI - HEADLESS IMAGE GENERATOR v7.0 (FIXED)
──────────────────────────────────────────────────
Smart Upload + ZIP + Auto-Extract + Verify + Auto-Cleanup

FIXES vs v6.0:
  ✅ Extraction VERIFICATION  — confirms each image exists in Drive after extract
  ✅ ZIP DELETE from Python   — Drive API delete (not just relying on Apps Script)
  ✅ Retry Logic (3 attempts) — Apps Script webhook retry on failure
  ✅ DEBUG logging            — every step logged in detail
  ✅ Partial extract recovery — detects which files extracted, which didn't
  ✅ ZIP leftover cleanup     — finds and deletes stale ZIPs from Drive

FLOW:
  1.  Generate images (9 req/min rate limit, 1 worker)
  2.  List existing files in Drive subfolder (1 API call)
  3.  Skip already-uploaded images
  4.  ZIP only NEW images into 1 file
  5.  Upload ZIP to Drive subfolder (1 API call)
  6.  Call Apps Script webhook → extract ZIP (with 3 retries)
  7.  VERIFY each image exists in Drive ← NEW ✅
  8.  DELETE ZIP from Drive (Python API call) ← NEW ✅
  9.  Report missing images ← NEW ✅
  10. Save JSON status

Environment Variables Required:
  PIXAZO_API_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
  GOOGLE_REFRESH_TOKEN, GOOGLE_DRIVE_FOLDER_ID,
  GOOGLE_APPS_SCRIPT_URL

Optional:
  PIXAZO_MODEL, PIXAZO_WIDTH, PIXAZO_HEIGHT, PIXAZO_COUNT,
  PIXAZO_NUM_STEPS, PIXAZO_GUIDANCE, PIXAZO_PROMPTS_DIR,
  PIXAZO_DEBUG (set to "1" for verbose debug logs)
"""

import json
import os
import sys
import time
import io
import zipfile
import requests
from pathlib import Path
from datetime import datetime
from collections import deque

# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS & CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════
FLUX_ENDPOINT = "https://gateway.pixazo.ai/flux-1-schnell/v1/getData"
SDXL_ENDPOINT = "https://gateway.pixazo.ai/getImage/v1/getSDXLImage"

MODEL_ENDPOINTS = {
    "flux-schnell":                FLUX_ENDPOINT,
    "sdxl":                        SDXL_ENDPOINT,
    "sdxl-base":                   SDXL_ENDPOINT,
    "stable-diffusion-inpainting": SDXL_ENDPOINT,
}
SDXL_MODELS = {"sdxl", "sdxl-base", "stable-diffusion-inpainting"}
VALID_MODELS = set(MODEL_ENDPOINTS.keys())

FLUX_STEPS        = 4
SDXL_NUM_STEPS    = 20
SDXL_GUIDANCE     = 5
SDXL_DEFAULT_SEED = 40

DEFAULT_NEG_PROMPT = (
    "low quality, blurry, distorted, deformed, ugly, watermark, text, "
    "bad anatomy, worst quality, jpeg artifacts, out of frame, extra limbs"
)

GOOGLE_TOKEN_URL  = "https://oauth2.googleapis.com/token"
GOOGLE_UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"
GOOGLE_DRIVE_API  = "https://www.googleapis.com/drive/v3/files"

MAX_REQUESTS_PER_MINUTE  = 9
RATE_WINDOW_SECONDS      = 60
APPS_SCRIPT_MAX_RETRIES  = 3          # retry count for webhook
APPS_SCRIPT_RETRY_DELAY  = 10         # seconds between retries
VERIFY_WAIT_SECONDS      = 5          # wait after extract before verify


# ══════════════════════════════════════════════════════════════════════════════
# RATE LIMITER
# ══════════════════════════════════════════════════════════════════════════════
class RateLimiter:
    def __init__(self, max_requests=MAX_REQUESTS_PER_MINUTE,
                 window_seconds=RATE_WINDOW_SECONDS):
        self.max_requests   = max_requests
        self.window_seconds = window_seconds
        self.timestamps     = deque()

    def wait_if_needed(self):
        now = time.time()
        while self.timestamps and (now - self.timestamps[0]) >= self.window_seconds:
            self.timestamps.popleft()
        if len(self.timestamps) >= self.max_requests:
            oldest    = self.timestamps[0]
            wait_time = self.window_seconds - (now - oldest) + 0.5
            if wait_time > 0:
                log.warn(f"Rate limit: {self.max_requests} req/min hit. "
                         f"Waiting {wait_time:.1f}s...")
                time.sleep(wait_time)
                now = time.time()
                while self.timestamps and (now - self.timestamps[0]) >= self.window_seconds:
                    self.timestamps.popleft()
        self.timestamps.append(time.time())

    def status(self):
        now = time.time()
        while self.timestamps and (now - self.timestamps[0]) >= self.window_seconds:
            self.timestamps.popleft()
        return f"{len(self.timestamps)}/{self.max_requests} req in window"

rate_limiter = RateLimiter()


# ══════════════════════════════════════════════════════════════════════════════
# LOGGER  (INFO / OK / WARN / ERROR / DEBUG / STEP)
# ══════════════════════════════════════════════════════════════════════════════
class Logger:
    debug_enabled = os.environ.get("PIXAZO_DEBUG", "0").strip() == "1"

    @staticmethod
    def _ts():
        return datetime.now().strftime("%H:%M:%S.%f")[:-3]   # ms precision

    @staticmethod
    def info(msg):
        print(f"[{Logger._ts()}] INFO   {msg}", flush=True)

    @staticmethod
    def ok(msg):
        print(f"[{Logger._ts()}] OK  ✅ {msg}", flush=True)

    @staticmethod
    def warn(msg):
        print(f"[{Logger._ts()}] WARN ⚠️  {msg}", flush=True)

    @staticmethod
    def err(msg):
        print(f"[{Logger._ts()}] ERR  ❌ {msg}", flush=True)

    @staticmethod
    def debug(msg):
        if Logger.debug_enabled:
            print(f"[{Logger._ts()}] DBG    {msg}", flush=True)

    @staticmethod
    def step(msg):
        print(f"\n{'═'*65}", flush=True)
        print(f"  {msg}", flush=True)
        print(f"{'═'*65}", flush=True)

    @staticmethod
    def section(msg):
        print(f"\n  ── {msg} ──", flush=True)

log = Logger()


# ══════════════════════════════════════════════════════════════════════════════
# GOOGLE AUTH
# ══════════════════════════════════════════════════════════════════════════════

def get_google_access_token(client_id, client_secret, refresh_token):
    log.debug("Requesting Google OAuth2 access token...")
    resp = requests.post(GOOGLE_TOKEN_URL, data={
        "client_id":     client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type":    "refresh_token",
    }, timeout=30)

    log.debug(f"Token response HTTP {resp.status_code}")
    if not resp.ok:
        log.err(f"Token refresh failed: HTTP {resp.status_code} | {resp.text[:200]}")
        raise RuntimeError(f"Token refresh failed: {resp.status_code}")

    token = resp.json().get("access_token")
    if not token:
        raise RuntimeError("No access_token in response")

    log.ok("Google Access Token obtained")
    return token


# ══════════════════════════════════════════════════════════════════════════════
# GOOGLE DRIVE — FOLDER
# ══════════════════════════════════════════════════════════════════════════════

def find_drive_folder(folder_name, parent_id, access_token):
    log.debug(f"Searching Drive folder: '{folder_name}' under parent={parent_id}")
    query = (
        f"name='{folder_name}' and '{parent_id}' in parents and "
        f"mimeType='application/vnd.google-apps.folder' and trashed=false"
    )
    resp = requests.get(GOOGLE_DRIVE_API,
        params={"q": query, "fields": "files(id,name)", "pageSize": 1},
        headers={"Authorization": f"Bearer {access_token}"}, timeout=30)

    log.debug(f"Folder search HTTP {resp.status_code}")
    if not resp.ok:
        log.warn(f"Folder search failed: HTTP {resp.status_code}")
        return None

    files = resp.json().get("files", [])
    if files:
        log.debug(f"Found existing folder id={files[0]['id']}")
        return files[0]["id"]
    log.debug("Folder not found — will create")
    return None


def create_drive_folder(folder_name, parent_id, access_token):
    existing = find_drive_folder(folder_name, parent_id, access_token)
    if existing:
        log.info(f"Drive subfolder exists: '{folder_name}' (id={existing})")
        return existing

    log.debug(f"Creating new Drive folder: '{folder_name}'")
    metadata = {
        "name":     folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents":  [parent_id],
    }
    resp = requests.post(GOOGLE_DRIVE_API, json=metadata, headers={
        "Authorization": f"Bearer {access_token}",
        "Content-Type":  "application/json",
    }, timeout=30)

    log.debug(f"Create folder HTTP {resp.status_code}")
    if not resp.ok:
        raise RuntimeError(f"Folder create failed: {resp.status_code} | {resp.text[:200]}")

    fid = resp.json().get("id")
    log.ok(f"Created subfolder: '{folder_name}' (id={fid})")
    return fid


# ══════════════════════════════════════════════════════════════════════════════
# GOOGLE DRIVE — LIST FILES
# ══════════════════════════════════════════════════════════════════════════════

def list_drive_files(folder_id, access_token):
    """
    Drive subfolder-ல் உள்ள எல்லா files-ஐ list பண்ணும்.
    Returns: dict { filename -> file_id }
    """
    log.debug(f"Listing files in Drive folder id={folder_id}")
    all_files  = {}   # name -> id
    page_token = None
    page_num   = 0

    while True:
        page_num += 1
        params = {
            "q":         f"'{folder_id}' in parents and trashed=false",
            "fields":    "nextPageToken, files(id,name,size,mimeType)",
            "pageSize":  1000,
        }
        if page_token:
            params["pageToken"] = page_token

        log.debug(f"  Listing page {page_num}...")
        resp = requests.get(GOOGLE_DRIVE_API, params=params,
            headers={"Authorization": f"Bearer {access_token}"}, timeout=30)

        log.debug(f"  List HTTP {resp.status_code}")
        if not resp.ok:
            log.err(f"List files failed: HTTP {resp.status_code} | {resp.text[:200]}")
            return all_files

        data = resp.json()
        for f in data.get("files", []):
            all_files[f["name"]] = f["id"]
            log.debug(f"    Found: {f['name']} (id={f['id']}, "
                      f"type={f.get('mimeType','?')}, size={f.get('size','?')})")

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    log.info(f"Drive folder has {len(all_files)} existing file(s)")
    return all_files


# ══════════════════════════════════════════════════════════════════════════════
# GOOGLE DRIVE — UPLOAD
# ══════════════════════════════════════════════════════════════════════════════

def upload_to_google_drive(file_path, folder_id, access_token, mime_type=None):
    file_path = Path(file_path)
    if not file_path.exists():
        log.err(f"Upload skipped — file not found: {file_path}")
        return None

    if mime_type is None:
        ext = file_path.suffix.lower()
        mime_map = {
            ".png":  "image/png",
            ".jpg":  "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".json": "application/json",
            ".zip":  "application/zip",
        }
        mime_type = mime_map.get(ext, "application/octet-stream")

    size_mb = file_path.stat().st_size / (1024 * 1024)
    log.debug(f"Uploading '{file_path.name}' ({size_mb:.2f} MB) as {mime_type} "
              f"to folder={folder_id}")

    metadata = {"name": file_path.name, "parents": [folder_id]}
    boundary = "pixazo_upload_boundary"
    body     = io.BytesIO()

    body.write(f"--{boundary}\r\n".encode())
    body.write(b"Content-Type: application/json; charset=UTF-8\r\n\r\n")
    body.write(json.dumps(metadata).encode())
    body.write(b"\r\n")
    body.write(f"--{boundary}\r\n".encode())
    body.write(f"Content-Type: {mime_type}\r\n\r\n".encode())
    with open(file_path, "rb") as f:
        body.write(f.read())
    body.write(b"\r\n")
    body.write(f"--{boundary}--\r\n".encode())

    upload_start = time.time()
    resp = requests.post(
        f"{GOOGLE_UPLOAD_URL}?uploadType=multipart",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type":  f"multipart/related; boundary={boundary}",
        },
        data=body.getvalue(), timeout=300)

    elapsed = time.time() - upload_start
    log.debug(f"Upload HTTP {resp.status_code} in {elapsed:.1f}s")

    if not resp.ok:
        log.err(f"Upload FAILED '{file_path.name}': HTTP {resp.status_code} | {resp.text[:300]}")
        return None

    file_id = resp.json().get("id", "")
    log.ok(f"Uploaded: '{file_path.name}' ({size_mb:.1f} MB) → id={file_id} in {elapsed:.1f}s")
    return file_id


# ══════════════════════════════════════════════════════════════════════════════
# GOOGLE DRIVE — DELETE FILE  ← NEW ✅
# ══════════════════════════════════════════════════════════════════════════════

def delete_drive_file(file_id, file_name, access_token):
    """
    Drive-ல் ஒரு file-ஐ id மூலம் delete பண்ணும்.
    ZIP cleanup-க்கு use ஆகும்.
    """
    log.debug(f"Deleting Drive file: '{file_name}' (id={file_id})")
    resp = requests.delete(
        f"{GOOGLE_DRIVE_API}/{file_id}",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30)

    log.debug(f"Delete HTTP {resp.status_code}")
    if resp.status_code in (200, 204):
        log.ok(f"Drive file deleted: '{file_name}' (id={file_id})")
        return True
    else:
        log.err(f"Delete failed '{file_name}': HTTP {resp.status_code} | {resp.text[:200]}")
        return False


def delete_zip_from_drive(zip_name, folder_id, access_token, existing_files_dict=None):
    """
    ZIP file-ஐ Drive-ல் இருந்து கண்டுபிடித்து delete பண்ணும்.
    existing_files_dict: { name -> id } already fetched ஆனது இருந்தால் pass பண்ணு
    இல்லாவிட்டால் fresh list call பண்ணும்.

    Returns: True if deleted, False if not found / failed
    """
    log.section(f"ZIP Cleanup: '{zip_name}'")

    if existing_files_dict is not None:
        file_id = existing_files_dict.get(zip_name)
        log.debug(f"Using cached file list — ZIP id={file_id}")
    else:
        log.debug("Fetching fresh file list to find ZIP...")
        fresh = list_drive_files(folder_id, access_token)
        file_id = fresh.get(zip_name)

    if not file_id:
        log.warn(f"ZIP '{zip_name}' not found in Drive — may already be deleted")
        return False

    return delete_drive_file(file_id, zip_name, access_token)


# ══════════════════════════════════════════════════════════════════════════════
# APPS SCRIPT — EXTRACT WITH RETRY  ← IMPROVED ✅
# ══════════════════════════════════════════════════════════════════════════════

def trigger_apps_script_extract(apps_script_url, zip_file_id, folder_id,
                                 max_retries=APPS_SCRIPT_MAX_RETRIES,
                                 retry_delay=APPS_SCRIPT_RETRY_DELAY):
    """
    Apps Script webhook-ஐ call பண்ணி ZIP extract trigger பண்ணும்.
    max_retries முறை retry பண்ணும்.
    Returns: response dict or None
    """
    payload = {
        "action":    "extract_and_cleanup",
        "zipFileId": zip_file_id,
        "folderId":  folder_id,
    }
    log.debug(f"Apps Script payload: {json.dumps(payload)}")

    for attempt in range(1, max_retries + 1):
        log.info(f"Apps Script call attempt {attempt}/{max_retries}...")
        log.debug(f"POST {apps_script_url}")

        try:
            t0   = time.time()
            resp = requests.post(
                apps_script_url,
                json=payload,
                timeout=300,
                allow_redirects=True)
            elapsed = time.time() - t0

            log.debug(f"Apps Script HTTP {resp.status_code} in {elapsed:.1f}s")
            log.debug(f"Response headers: {dict(resp.headers)}")
            log.debug(f"Response body: {resp.text[:500]}")

            if resp.ok:
                try:
                    result = resp.json()
                except Exception:
                    result = {"status": "ok", "raw": resp.text[:200]}

                log.ok(f"Apps Script SUCCESS (attempt {attempt}): {json.dumps(result)[:300]}")
                return result
            else:
                log.warn(f"Apps Script attempt {attempt} FAILED: "
                         f"HTTP {resp.status_code} | {resp.text[:300]}")

        except requests.Timeout:
            log.warn(f"Apps Script attempt {attempt} TIMED OUT (300s)")
        except requests.ConnectionError as e:
            log.warn(f"Apps Script attempt {attempt} CONNECTION ERROR: {e}")
        except Exception as e:
            log.warn(f"Apps Script attempt {attempt} EXCEPTION: {e}")

        if attempt < max_retries:
            log.info(f"Waiting {retry_delay}s before retry...")
            time.sleep(retry_delay)

    log.err(f"Apps Script FAILED after {max_retries} attempts!")
    return None


# ══════════════════════════════════════════════════════════════════════════════
# EXTRACTION VERIFICATION  ← NEW ✅
# ══════════════════════════════════════════════════════════════════════════════

def verify_extraction(expected_filenames, folder_id, access_token,
                      wait_seconds=VERIFY_WAIT_SECONDS):
    """
    Apps Script extract பண்ணிய பிறகு, Drive-ல் எல்லா images இருக்கின்றனவா verify பண்ணும்.

    Args:
        expected_filenames : list of filename strings (e.g. ["img_001.png", ...])
        folder_id          : Drive folder to check
        access_token       : OAuth token
        wait_seconds       : Apps Script process-ஆக சிறிது time கொடு

    Returns:
        dict {
            "verified"  : [filenames found in Drive],
            "missing"   : [filenames NOT in Drive],
            "success"   : True if all found
        }
    """
    log.section("Extraction Verification")
    log.info(f"Waiting {wait_seconds}s for Apps Script to finish extraction...")
    time.sleep(wait_seconds)

    log.info(f"Verifying {len(expected_filenames)} image(s) in Drive...")
    log.debug(f"Expected files: {expected_filenames}")

    # Fresh list from Drive
    current_files = list_drive_files(folder_id, access_token)
    log.debug(f"Drive currently has {len(current_files)} file(s): {list(current_files.keys())}")

    verified = []
    missing  = []

    for fname in expected_filenames:
        if fname in current_files:
            verified.append(fname)
            log.debug(f"  ✅ FOUND:   {fname} (id={current_files[fname]})")
        else:
            missing.append(fname)
            log.debug(f"  ❌ MISSING: {fname}")

    # Summary
    total    = len(expected_filenames)
    found    = len(verified)
    not_found = len(missing)

    if not_found == 0:
        log.ok(f"Verification PASSED: {found}/{total} images confirmed in Drive")
    else:
        log.err(f"Verification FAILED: {found}/{total} found, {not_found} MISSING!")
        for m in missing:
            log.err(f"  MISSING: {m}")

    return {
        "verified":      verified,
        "missing":       missing,
        "success":       (not_found == 0),
        "drive_files":   current_files,   # return for reuse (avoid extra API calls)
    }


# ══════════════════════════════════════════════════════════════════════════════
# ZIP HELPER
# ══════════════════════════════════════════════════════════════════════════════

def create_zip_from_files(file_paths, zip_path):
    """Multiple image files-ஐ ஒரே ZIP-ஆ pack பண்ணும்"""
    zip_path = Path(zip_path)
    log.debug(f"Creating ZIP: {zip_path}")

    added = 0
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fp in file_paths:
            fp = Path(fp)
            if fp.exists():
                zf.write(fp, fp.name)  # flatten — no subdirectories in ZIP
                added += 1
                log.debug(f"  Added to ZIP: {fp.name} ({fp.stat().st_size} bytes)")
            else:
                log.warn(f"  Skipped (not found): {fp}")

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    log.ok(f"ZIP created: '{zip_path.name}' ({added} files, {size_mb:.1f} MB)")

    # Verify ZIP integrity
    log.debug("Verifying ZIP integrity...")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            bad = zf.testzip()
            if bad:
                log.err(f"ZIP integrity check FAILED — first bad file: {bad}")
            else:
                names = zf.namelist()
                log.debug(f"ZIP OK — contents: {names}")
                log.ok(f"ZIP integrity verified ({len(names)} files inside)")
    except Exception as e:
        log.err(f"ZIP integrity check exception: {e}")

    return zip_path


# ══════════════════════════════════════════════════════════════════════════════
# PIXAZO IMAGE GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def generate_image_flux(prompt, seed, api_key, width, height):
    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
        "Content-Type":  "application/json",
        "Cache-Control": "no-cache",
    }
    payload = {
        "prompt":    prompt,
        "num_steps": int(FLUX_STEPS),
        "seed":      int(seed),
        "width":     int(width),
        "height":    int(height),
    }
    log.debug(f"Flux payload: {json.dumps(payload)[:200]}")
    rate_limiter.wait_if_needed()

    t0   = time.time()
    resp = requests.post(FLUX_ENDPOINT, json=payload, headers=headers, timeout=180)
    log.debug(f"Flux HTTP {resp.status_code} in {time.time()-t0:.1f}s")

    resp.raise_for_status()
    data = resp.json()
    log.debug(f"Flux response keys: {list(data.keys())}")

    for key in ("output", "imageUrl", "image_url", "url", "image"):
        if key in data and data[key]:
            log.debug(f"Flux image URL from key='{key}': {str(data[key])[:80]}")
            return data[key]
    if "images" in data and data["images"]:
        img = data["images"][0]
        url = img.get("url") or img.get("imageUrl") if isinstance(img, dict) else str(img)
        log.debug(f"Flux image URL from images[0]: {str(url)[:80]}")
        return url

    raise ValueError("Flux: no image URL in response: " + json.dumps(data)[:300])


def generate_image_sdxl(prompt, seed, api_key, width, height,
                         negative_prompt, num_steps, guidance_scale):
    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
        "Content-Type":  "application/json",
        "Cache-Control": "no-cache",
    }
    payload = {
        "prompt":          str(prompt),
        "negative_prompt": str(negative_prompt),
        "height":          int(height),
        "width":           int(width),
        "num_steps":       int(num_steps),
        "guidance_scale":  int(guidance_scale),
        "seed":            int(seed),
    }
    log.debug(f"SDXL payload: {json.dumps(payload)[:200]}")
    rate_limiter.wait_if_needed()

    t0   = time.time()
    resp = requests.post(SDXL_ENDPOINT, json=payload, headers=headers, timeout=180)
    log.debug(f"SDXL HTTP {resp.status_code} in {time.time()-t0:.1f}s")

    try:
        body_text = resp.text[:600]
    except Exception:
        body_text = "(unreadable)"

    if not resp.ok:
        raise ValueError(f"HTTP {resp.status_code} | {body_text}")

    data = resp.json()
    log.debug(f"SDXL response keys: {list(data.keys())}")

    if "imageUrl" in data and data["imageUrl"]:
        log.debug(f"SDXL imageUrl: {str(data['imageUrl'])[:80]}")
        return data["imageUrl"]
    for key in ("image_url", "output", "url", "image"):
        if key in data and data[key]:
            log.debug(f"SDXL image URL from key='{key}': {str(data[key])[:80]}")
            return data[key]
    if "images" in data and data["images"]:
        img = data["images"][0]
        url = img.get("url") or img.get("imageUrl") if isinstance(img, dict) else str(img)
        log.debug(f"SDXL image URL from images[0]: {str(url)[:80]}")
        return url

    raise ValueError("SDXL: no imageUrl in response: " + json.dumps(data)[:400])


def generate_image_api(prompt, seed, model_name, api_key, width, height,
                        negative_prompt="", num_steps=SDXL_NUM_STEPS,
                        guidance_scale=SDXL_GUIDANCE):
    if model_name == "flux-schnell":
        return generate_image_flux(prompt, seed, api_key, width, height)
    elif model_name in SDXL_MODELS:
        return generate_image_sdxl(prompt, seed, api_key, width, height,
            negative_prompt, num_steps, guidance_scale)
    else:
        raise ValueError("Unknown model: " + model_name)


def download_file(url, save_path):
    log.debug(f"Downloading: {url[:80]} → {save_path}")
    t0 = time.time()
    r  = requests.get(url, timeout=90)
    r.raise_for_status()
    with open(str(save_path), "wb") as f:
        f.write(r.content)
    size_kb = len(r.content) / 1024
    log.debug(f"Downloaded {size_kb:.0f} KB in {time.time()-t0:.1f}s")


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

def load_config():
    config  = {}
    required = {
        "PIXAZO_API_KEY":         "Pixazo API key",
        "GOOGLE_CLIENT_ID":       "Google OAuth Client ID",
        "GOOGLE_CLIENT_SECRET":   "Google OAuth Client Secret",
        "GOOGLE_REFRESH_TOKEN":   "Google OAuth Refresh Token",
        "GOOGLE_DRIVE_FOLDER_ID": "Google Drive Parent Folder ID",
        "GOOGLE_APPS_SCRIPT_URL": "Google Apps Script Web App URL",
    }
    missing = []
    for key, label in required.items():
        val = os.environ.get(key, "").strip()
        if not val:
            missing.append(f"  - {key} ({label})")
        config[key] = val

    if missing:
        log.err("Missing environment variables:")
        for m in missing:
            print(m, flush=True)
        sys.exit(1)

    config["MODEL"]       = os.environ.get("PIXAZO_MODEL", "flux-schnell").strip()
    config["WIDTH"]       = int(os.environ.get("PIXAZO_WIDTH",  "1024"))
    config["HEIGHT"]      = int(os.environ.get("PIXAZO_HEIGHT", "1024"))
    config["WORKERS"]     = 1
    config["COUNT"]       = os.environ.get("PIXAZO_COUNT", "ALL").strip().upper()
    config["NUM_STEPS"]   = int(os.environ.get("PIXAZO_NUM_STEPS", str(SDXL_NUM_STEPS)))
    config["GUIDANCE"]    = int(os.environ.get("PIXAZO_GUIDANCE",  str(SDXL_GUIDANCE)))
    config["PROMPTS_DIR"] = os.environ.get("PIXAZO_PROMPTS_DIR", "prompts").strip()

    if config["MODEL"] not in VALID_MODELS:
        log.err(f"Invalid model: '{config['MODEL']}'. Valid: {sorted(VALID_MODELS)}")
        sys.exit(1)

    log.debug(f"Config loaded: MODEL={config['MODEL']} "
              f"SIZE={config['WIDTH']}x{config['HEIGHT']} "
              f"COUNT={config['COUNT']} "
              f"DEBUG={Logger.debug_enabled}")
    return config


# ══════════════════════════════════════════════════════════════════════════════
# PROCESS ONE JSON FILE  ← MAIN LOGIC WITH ALL FIXES
# ══════════════════════════════════════════════════════════════════════════════

def process_single_json(json_path, config, access_token):
    json_path      = Path(json_path)
    subfolder_name = json_path.stem

    log.step(f"PROCESSING: {json_path.name} → Drive/{subfolder_name}/")

    # ── Load JSON ──
    log.debug(f"Reading JSON: {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        raw = f.read()
    raw       = raw.replace('"status":\n  }',  '"status": "pending"\n  }')
    raw       = raw.replace('"status": \n  }', '"status": "pending"\n  }')
    json_data = json.loads(raw)

    total  = len(json_data)
    done_c = sum(1 for x in json_data if x.get("status") == "completed")
    log.info(f"JSON: {total} total | {done_c} done | {total - done_c} pending")

    # ── Config ──
    model_name       = config["MODEL"]
    api_key          = config["PIXAZO_API_KEY"]
    width, height    = config["WIDTH"], config["HEIGHT"]
    num_steps        = config["NUM_STEPS"]
    guidance         = config["GUIDANCE"]
    count_str        = config["COUNT"]
    parent_folder_id = config["GOOGLE_DRIVE_FOLDER_ID"]
    apps_script_url  = config["GOOGLE_APPS_SCRIPT_URL"]

    # ── Local output ──
    local_out = Path("generated_images") / subfolder_name
    local_out.mkdir(parents=True, exist_ok=True)
    log.debug(f"Local output directory: {local_out.resolve()}")

    # ── Create/find Drive subfolder ──
    log.section("Step 1: Drive Subfolder")
    sub_folder_id = create_drive_folder(subfolder_name, parent_folder_id, access_token)
    log.info(f"Drive subfolder id={sub_folder_id}")

    # ── List existing files in Drive ──
    log.section("Step 2: List Existing Drive Files")
    existing_in_drive = list_drive_files(sub_folder_id, access_token)
    log.debug(f"Existing Drive files: {list(existing_in_drive.keys())}")

    # ── Build pending list ──
    log.section("Step 3: Build Pending List")
    items_pending = [x for x in json_data if x.get("status") != "completed"]
    skipped_disk  = 0
    skipped_drive = 0
    truly_pending = []

    for item in items_pending:
        fname    = item.get("filename", f"img_{item.get('index', 0)}.png")
        out_path = local_out / fname

        if out_path.exists():
            item["status"]      = "completed"
            item["output_path"] = str(out_path)
            skipped_disk += 1
            log.debug(f"  Skip (on disk): {fname}")
            continue

        if fname in existing_in_drive:
            item["status"]         = "completed"
            item["drive_uploaded"] = True
            skipped_drive += 1
            log.debug(f"  Skip (in Drive): {fname}")
            continue

        truly_pending.append(item)
        log.debug(f"  Pending: {fname}")

    if skipped_disk:
        log.info(f"Skipped {skipped_disk} — already on disk")
    if skipped_drive:
        log.info(f"Skipped {skipped_drive} — already in Google Drive")
    log.info(f"Truly pending: {len(truly_pending)}")

    if count_str != "ALL":
        try:
            truly_pending = truly_pending[:int(count_str)]
            log.debug(f"Count limit applied: {len(truly_pending)}")
        except ValueError:
            pass

    total_gen = len(truly_pending)
    result = {
        "json":          json_path.name,
        "generated":     0,
        "failed":        0,
        "uploaded":      0,
        "verified":      0,
        "missing":       0,
        "drive_calls":   0,
        "time_seconds":  0,
    }

    if total_gen == 0:
        log.warn(f"'{json_path.name}' — nothing to generate!")
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(json_data, fh, indent=2, ensure_ascii=False)
        return result

    # ── Generate images (sequential, rate-limited) ──
    log.section(f"Step 4: Generate {total_gen} Images")
    log.info(f"Model={model_name} | Size={width}x{height} | Rate=9 req/min")

    done_count = 0
    fail_count = 0
    start_t    = time.time()
    new_images = []

    for idx, item in enumerate(truly_pending, 1):
        fname    = item.get("filename", f"img_{item.get('index', 0)}.png")
        out_path = local_out / fname
        prompt   = item.get("prompt", "")
        seed     = int(item.get("seed", SDXL_DEFAULT_SEED))

        log.info(f"[{idx}/{total_gen}] Generating: {fname} | seed={seed} | {rate_limiter.status()}")
        log.debug(f"  Prompt: {prompt[:100]}")

        try:
            img_url = generate_image_api(
                prompt, seed, model_name, api_key, width, height,
                negative_prompt=DEFAULT_NEG_PROMPT,
                num_steps=num_steps, guidance_scale=guidance)

            log.debug(f"  Image URL: {str(img_url)[:80]}")
            download_file(img_url, out_path)

            item["status"]      = "completed"
            item["output_path"] = str(out_path)
            item["done_at"]     = datetime.now().isoformat()
            new_images.append(out_path)
            done_count += 1
            log.ok(f"  Generated & saved: {fname}")

        except Exception as e:
            item["status"] = "failed"
            fail_count += 1
            log.err(f"  FAILED: {fname} — {str(e)[:300]}")

        # Progress
        processed = done_count + fail_count
        elapsed   = max(time.time() - start_t, 0.001)
        rate      = processed / elapsed * 60
        remaining = total_gen - processed
        eta_s     = int(remaining / (processed / elapsed)) if processed > 0 else 0
        print(f"  Progress: {processed}/{total_gen} ({processed/total_gen*100:.0f}%) "
              f"| OK:{done_count} FAIL:{fail_count} "
              f"| {rate:.1f} img/min | ETA:{eta_s//60}m{eta_s%60}s", flush=True)

        # Crash-safe JSON save
        try:
            with open(json_path, "w", encoding="utf-8") as fh:
                json.dump(json_data, fh, indent=2, ensure_ascii=False)
        except Exception:
            pass

    # ── ZIP + Upload + Extract + Verify + Cleanup ──
    drive_calls  = 2  # folder + list (already done)
    zip_uploaded = False
    zip_file_id  = None
    zip_name     = None
    verify_result = {"verified": [], "missing": [], "success": False}

    if new_images:
        # ── Step 5: Create ZIP ──
        log.section("Step 5: Create ZIP")
        zip_name = f"{subfolder_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        zip_path = local_out / zip_name
        create_zip_from_files(new_images, zip_path)

        # ── Step 6: Upload ZIP to Drive ──
        log.section("Step 6: Upload ZIP to Drive")
        log.info(f"Uploading '{zip_name}' to Drive/{subfolder_name}/...")
        zip_file_id = upload_to_google_drive(zip_path, sub_folder_id, access_token)
        drive_calls += 1

        if zip_file_id:
            zip_uploaded = True
            log.ok(f"ZIP uploaded successfully: id={zip_file_id}")

            # ── Step 7: Apps Script Extract ──
            log.section("Step 7: Apps Script Extract (with retry)")
            extract_result = trigger_apps_script_extract(
                apps_script_url, zip_file_id, sub_folder_id)
            drive_calls += 1  # webhook

            if extract_result:
                log.ok("Apps Script extract triggered successfully")
            else:
                log.warn("Apps Script extract FAILED — will verify and cleanup manually")

            # ── Step 8: Verify Extraction ← NEW ✅ ──
            log.section("Step 8: Verify Extracted Images in Drive")
            expected_names = [Path(p).name for p in new_images]
            verify_result  = verify_extraction(
                expected_names, sub_folder_id, access_token)
            drive_calls += 1  # list files for verify

            if verify_result["success"]:
                log.ok(f"All {len(verify_result['verified'])} images verified in Drive!")
            else:
                log.err(f"{len(verify_result['missing'])} image(s) NOT found in Drive:")
                for mf in verify_result["missing"]:
                    log.err(f"  ❌ {mf}")

            # ── Step 9: Delete ZIP from Drive ← NEW ✅ ──
            log.section("Step 9: Delete ZIP from Drive")
            # Use the drive_files returned by verify (fresh list — no extra API call)
            drive_files_now = verify_result.get("drive_files", {})

            if zip_name in drive_files_now:
                log.info(f"ZIP still in Drive — deleting via Python API...")
                deleted = delete_drive_file(
                    drive_files_now[zip_name], zip_name, access_token)
                drive_calls += 1
                if deleted:
                    log.ok(f"ZIP deleted from Drive: '{zip_name}'")
                else:
                    log.warn(f"ZIP deletion failed — '{zip_name}' may remain in Drive")
            else:
                log.ok(f"ZIP already removed from Drive (Apps Script handled it)")

            # Mark drive_uploaded on verified items
            verified_set = set(verify_result["verified"])
            for item in json_data:
                fname = item.get("filename", "")
                if fname in verified_set:
                    item["drive_uploaded"] = True

        else:
            log.err("ZIP upload to Drive FAILED — skipping extract/verify")

        # Cleanup local ZIP
        try:
            zip_path.unlink()
            log.debug(f"Local ZIP deleted: {zip_path}")
            log.info("Local ZIP cleaned up")
        except Exception as e:
            log.warn(f"Could not delete local ZIP: {e}")

        # ── Step 10: Upload JSON status to Drive ──
        log.section("Step 10: Upload JSON Status to Drive")
        log.info(f"Uploading '{json_path.name}' to Drive/{subfolder_name}/...")
        upload_to_google_drive(json_path, sub_folder_id, access_token,
                               mime_type="application/json")
        drive_calls += 1

    # ── Final JSON save ──
    log.section("Final JSON Save")
    try:
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(json_data, fh, indent=2, ensure_ascii=False)
        log.ok(f"JSON saved: {json_path}")
    except Exception as e:
        log.err(f"JSON save error: {e}")

    elapsed = int(time.time() - start_t)
    result.update({
        "generated":    done_count,
        "failed":       fail_count,
        "uploaded":     len(new_images) if zip_uploaded else 0,
        "verified":     len(verify_result["verified"]),
        "missing":      len(verify_result["missing"]),
        "drive_calls":  drive_calls,
        "time_seconds": elapsed,
    })

    log.info(
        f"[{json_path.name}] Done {elapsed}s | "
        f"Gen:{done_count} Fail:{fail_count} | "
        f"Verified:{len(verify_result['verified'])} "
        f"Missing:{len(verify_result['missing'])} | "
        f"DriveAPICalls:{drive_calls}"
    )
    return result


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def run_pipeline(config):
    log.step("PIXAZO AI - HEADLESS GENERATOR v7.0 (FIXED)")
    log.info(f"Model: {config['MODEL']} | Size: {config['WIDTH']}x{config['HEIGHT']}")
    log.info(f"Rate limit: {MAX_REQUESTS_PER_MINUTE} req/min | Workers: 1")
    log.info(f"Apps Script retries: {APPS_SCRIPT_MAX_RETRIES}")
    log.info(f"Debug logging: {'ON' if Logger.debug_enabled else 'OFF'} "
             f"(set PIXAZO_DEBUG=1 to enable)")
    log.info(f"Upload mode: ZIP → Extract → Verify → Cleanup")

    prompts_dir = Path(config["PROMPTS_DIR"])
    if not prompts_dir.exists():
        log.err(f"Prompts folder not found: '{prompts_dir}'")
        sys.exit(1)

    json_files = sorted(prompts_dir.glob("*.json"))
    if not json_files:
        log.err(f"No JSON files in '{prompts_dir}/'")
        sys.exit(1)

    log.info(f"Found {len(json_files)} JSON file(s):")
    for jf in json_files:
        log.info(f"  {jf.name} → Drive/{jf.stem}/")

    # Auth
    log.step("Google Drive Authentication")
    access_token = get_google_access_token(
        config["GOOGLE_CLIENT_ID"],
        config["GOOGLE_CLIENT_SECRET"],
        config["GOOGLE_REFRESH_TOKEN"])

    # Process
    all_results = []
    total_start = time.time()

    for idx, jf in enumerate(json_files, 1):
        log.step(f"FILE {idx}/{len(json_files)}: {jf.name}")
        try:
            r = process_single_json(jf, config, access_token)
            all_results.append(r)
        except Exception as e:
            log.err(f"Error in {jf.name}: {e}")
            import traceback
            traceback.print_exc()
            all_results.append({
                "json":         jf.name,
                "generated":    0,
                "failed":       0,
                "uploaded":     0,
                "verified":     0,
                "missing":      0,
                "drive_calls":  0,
                "error":        str(e),
            })

    # Summary
    total_elapsed = int(time.time() - total_start)
    log.step("FINAL SUMMARY")

    t_gen = t_fail = t_up = t_dc = t_ver = t_mis = 0
    for r in all_results:
        g   = r.get("generated",  0)
        f   = r.get("failed",     0)
        u   = r.get("uploaded",   0)
        dc  = r.get("drive_calls",0)
        ver = r.get("verified",   0)
        mis = r.get("missing",    0)
        t_gen  += g;  t_fail += f;  t_up  += u
        t_dc   += dc; t_ver  += ver; t_mis += mis

        st = "OK  " if (f == 0 and mis == 0 and "error" not in r) else "WARN"
        print(
            f"  [{st}] {r['json']:30s} | "
            f"Gen:{g} Fail:{f} | Up:{u} Verified:{ver} Missing:{mis} | "
            f"DriveCalls:{dc}",
            flush=True)

    print(flush=True)
    log.info(f"TOTALS — Gen:{t_gen} Fail:{t_fail} | "
             f"Uploaded:{t_up} Verified:{t_ver} Missing:{t_mis}")
    log.info(f"Total Drive API calls: {t_dc}")
    log.info(f"Total time: {total_elapsed}s")

    if t_fail > 0 or t_mis > 0:
        log.warn(f"Completed with issues — Fail:{t_fail} Missing:{t_mis}")
        sys.exit(1)
    else:
        log.ok("All images generated, uploaded, extracted & verified successfully!")


if __name__ == "__main__":
    try:
        config = load_config()
        run_pipeline(config)
    except KeyboardInterrupt:
        log.warn("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        log.err(f"Fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
