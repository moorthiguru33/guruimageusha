#!/usr/bin/env python3
"""
PIXAZO AI - HEADLESS IMAGE GENERATOR v8.0
──────────────────────────────────────────
Auto Token Refresh + Batch Upload (every 500 images)

FIXES vs v7.0:
  ✅ GoogleAuth class         — Token auto-refresh every 50 min (Google gives 60 min)
  ✅ Batch upload (500/batch) — Every 500 images → immediate Drive upload → continue
  ✅ Token never expires      — Works for 2000, 5000, 10000+ images
  ✅ Memory efficient         — Uploaded batch images cleared from local buffer
  ✅ All v7.0 fixes retained  — Verification, retry, debug, cleanup

FLOW:
  1.  Generate images (9 req/min rate limit, 1 worker)
  2.  Every UPLOAD_BATCH_SIZE images → upload batch to Drive (token auto-refreshed)
  3.  Final remaining images → upload last batch
  4.  Save JSON status

Environment Variables Required:
  PIXAZO_API_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
  GOOGLE_REFRESH_TOKEN, GOOGLE_DRIVE_FOLDER_ID

Optional:
  PIXAZO_MODEL, PIXAZO_WIDTH, PIXAZO_HEIGHT, PIXAZO_COUNT,
  PIXAZO_NUM_STEPS, PIXAZO_GUIDANCE, PIXAZO_PROMPTS_DIR,
  PIXAZO_DEBUG (set to "1" for verbose debug logs)
  PIXAZO_UPLOAD_BATCH_SIZE (default: 500)
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

MAX_REQUESTS_PER_MINUTE   = 9
RATE_WINDOW_SECONDS        = 60
APPS_SCRIPT_MAX_RETRIES    = 3
APPS_SCRIPT_RETRY_DELAY    = 10
VERIFY_WAIT_SECONDS        = 5
DEFAULT_UPLOAD_BATCH_SIZE  = 500   # Every 500 images upload to Drive


# ══════════════════════════════════════════════════════════════════════════════
# GOOGLE AUTH — AUTO REFRESH  ✅ NEW v8.0
# ══════════════════════════════════════════════════════════════════════════════

class GoogleAuth:
    """
    Google OAuth2 token manager with auto-refresh.
    Token 50 minute-க்கு ஒரு முறை auto-refresh பண்ணும்.
    (Google 60 min கொடுக்கும், 50 min-ல் refresh — safe margin)
    """
    TOKEN_TTL = 3000  # 50 minutes in seconds

    def __init__(self, client_id, client_secret, refresh_token):
        self.client_id     = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self._token        = None
        self._token_time   = 0

    def get_token(self):
        """Token expire ஆகிவிட்டால் auto-refresh பண்ணும்"""
        elapsed = time.time() - self._token_time
        if not self._token or elapsed > self.TOKEN_TTL:
            mins = int(elapsed // 60)
            if self._token:
                log.info(f"Token {mins}m old — refreshing (TTL={self.TOKEN_TTL//60}m)...")
            else:
                log.info("Getting Google OAuth2 token (first time)...")
            self._token      = _fetch_google_token(
                self.client_id, self.client_secret, self.refresh_token)
            self._token_time = time.time()
            log.ok("Google Access Token ready!")
        return self._token

    def token_age_str(self):
        elapsed = int(time.time() - self._token_time)
        return f"{elapsed//60}m{elapsed%60}s old"


def _fetch_google_token(client_id, client_secret, refresh_token):
    """Raw token fetch — use GoogleAuth.get_token() instead"""
    resp = requests.post(GOOGLE_TOKEN_URL, data={
        "client_id":     client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type":    "refresh_token",
    }, timeout=30)

    if not resp.ok:
        log.err(f"Token refresh failed: HTTP {resp.status_code} | {resp.text[:200]}")
        raise RuntimeError(f"Token refresh failed: {resp.status_code}")

    token = resp.json().get("access_token")
    if not token:
        raise RuntimeError("No access_token in response")
    return token


# Legacy function kept for compatibility
def get_google_access_token(client_id, client_secret, refresh_token):
    return _fetch_google_token(client_id, client_secret, refresh_token)


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
# LOGGER
# ══════════════════════════════════════════════════════════════════════════════
class Logger:
    debug_enabled = os.environ.get("PIXAZO_DEBUG", "0").strip() == "1"

    @staticmethod
    def _ts():
        return datetime.now().strftime("%H:%M:%S.%f")[:-3]

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
    """Drive subfolder files list. Returns: dict { filename -> file_id }"""
    log.debug(f"Listing files in Drive folder id={folder_id}")
    all_files  = {}
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

    size_mb  = file_path.stat().st_size / (1024 * 1024)
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
# GOOGLE DRIVE — DELETE FILE
# ══════════════════════════════════════════════════════════════════════════════

def delete_drive_file(file_id, file_name, access_token):
    log.debug(f"Deleting Drive file: '{file_name}' (id={file_id})")
    resp = requests.delete(
        f"{GOOGLE_DRIVE_API}/{file_id}",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30)

    if resp.status_code in (200, 204):
        log.ok(f"Drive file deleted: '{file_name}' (id={file_id})")
        return True
    else:
        log.err(f"Delete failed '{file_name}': HTTP {resp.status_code} | {resp.text[:200]}")
        return False


def delete_zip_from_drive(zip_name, folder_id, access_token, existing_files_dict=None):
    log.section(f"ZIP Cleanup: '{zip_name}'")
    if existing_files_dict is not None:
        file_id = existing_files_dict.get(zip_name)
    else:
        fresh   = list_drive_files(folder_id, access_token)
        file_id = fresh.get(zip_name)

    if not file_id:
        log.warn(f"ZIP '{zip_name}' not found in Drive — may already be deleted")
        return False
    return delete_drive_file(file_id, zip_name, access_token)


# ══════════════════════════════════════════════════════════════════════════════
# APPS SCRIPT — EXTRACT WITH RETRY
# ══════════════════════════════════════════════════════════════════════════════

def _is_apps_script_auth_error(resp):
    content_type = resp.headers.get("Content-Type", "")
    if "text/html" in content_type:
        body_lower = resp.text.lower()
        if any(phrase in body_lower for phrase in [
            "authorization needed", "sign in", "signin",
            "accounts.google.com", "oauth", "<title>auth",
        ]):
            return True
    return False


def trigger_apps_script_extract(apps_script_url, zip_file_id, folder_id,
                                 access_token=None,
                                 max_retries=APPS_SCRIPT_MAX_RETRIES,
                                 retry_delay=APPS_SCRIPT_RETRY_DELAY):
    payload = {
        "action":    "extract_and_cleanup",
        "zipFileId": zip_file_id,
        "folderId":  folder_id,
    }
    headers = {"Content-Type": "application/json"}

    for attempt in range(1, max_retries + 1):
        log.info(f"Apps Script call attempt {attempt}/{max_retries}...")
        try:
            t0   = time.time()
            resp = requests.post(apps_script_url, json=payload, headers=headers,
                                  timeout=300, allow_redirects=True)
            elapsed = time.time() - t0

            if resp.ok and _is_apps_script_auth_error(resp):
                log.err(
                    f"Apps Script → HTTP 200 but 'Authorization needed' HTML!\n"
                    f"  FIX: Deploy → 'Who has access' → 'Anyone, even anonymous'"
                )
            elif resp.ok:
                try:
                    result = resp.json()
                    log.ok(f"Apps Script SUCCESS: {json.dumps(result)[:300]}")
                    return result
                except Exception:
                    log.ok(f"Apps Script SUCCESS plain: {resp.text[:100]}")
                    return {"status": "ok", "raw": resp.text[:200]}
            elif resp.status_code == 403:
                log.err("Apps Script → HTTP 403 FORBIDDEN. Fix deployment settings.")
            else:
                log.warn(f"Apps Script attempt {attempt} FAILED: HTTP {resp.status_code}")

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
# EXTRACTION VERIFICATION
# ══════════════════════════════════════════════════════════════════════════════

def verify_extraction(expected_filenames, folder_id, access_token,
                      wait_seconds=VERIFY_WAIT_SECONDS):
    log.section("Extraction Verification")
    log.info(f"Waiting {wait_seconds}s for Apps Script to finish extraction...")
    time.sleep(wait_seconds)
    log.info(f"Verifying {len(expected_filenames)} image(s) in Drive...")

    current_files = list_drive_files(folder_id, access_token)
    verified = []
    missing  = []

    for fname in expected_filenames:
        if fname in current_files:
            verified.append(fname)
        else:
            missing.append(fname)

    if not missing:
        log.ok(f"Verification PASSED: {len(verified)}/{len(expected_filenames)} confirmed")
    else:
        log.err(f"Verification FAILED: {len(missing)} MISSING!")
        for m in missing:
            log.err(f"  MISSING: {m}")

    return {
        "verified":    verified,
        "missing":     missing,
        "success":     len(missing) == 0,
        "drive_files": current_files,
    }


# ══════════════════════════════════════════════════════════════════════════════
# ZIP HELPER
# ══════════════════════════════════════════════════════════════════════════════

def create_zip_from_files(file_paths, zip_path):
    zip_path = Path(zip_path)
    added    = 0
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fp in file_paths:
            fp = Path(fp)
            if fp.exists():
                zf.write(fp, fp.name)
                added += 1
            else:
                log.warn(f"  Skipped (not found): {fp}")

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    log.ok(f"ZIP created: '{zip_path.name}' ({added} files, {size_mb:.1f} MB)")
    return zip_path


# ══════════════════════════════════════════════════════════════════════════════
# BATCH UPLOAD TO DRIVE  ✅ NEW v8.0
# ══════════════════════════════════════════════════════════════════════════════

def upload_batch_to_drive(batch_images, sub_folder_id, auth, json_data, batch_num):
    """
    batch_images: list of Path objects (local image files)
    auth: GoogleAuth object — token auto-refresh included
    json_data: reference for status update
    batch_num: for logging

    Returns: (uploaded_count, failed_list)
    """
    total = len(batch_images)
    log.step(f"BATCH {batch_num} UPLOAD: {total} images → Google Drive")

    uploaded_list = []
    failed_list   = []

    for i, img_path in enumerate(batch_images, 1):
        fname = Path(img_path).name
        log.info(f"  [{i}/{total}] Uploading: {fname} | Token: {auth.token_age_str()}")

        # Token auto-refresh on every upload call
        access_token = auth.get_token()
        file_id      = upload_to_google_drive(img_path, sub_folder_id, access_token)

        if file_id:
            uploaded_list.append(fname)
            for item in json_data:
                if item.get("filename") == fname:
                    item["drive_uploaded"] = True
                    item["batch_num"]      = batch_num
                    break
            log.ok(f"  Uploaded: {fname}")
        else:
            failed_list.append(fname)
            log.err(f"  Upload FAILED: {fname}")

    log.info(
        f"Batch {batch_num} complete: "
        f"✅ {len(uploaded_list)} uploaded | ❌ {len(failed_list)} failed"
    )
    return len(uploaded_list), failed_list


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

    for key in ("output", "imageUrl", "image_url", "url", "image"):
        if key in data and data[key]:
            return data[key]
    if "images" in data and data["images"]:
        img = data["images"][0]
        url = img.get("url") or img.get("imageUrl") if isinstance(img, dict) else str(img)
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

    if not resp.ok:
        raise ValueError(f"HTTP {resp.status_code} | {resp.text[:600]}")

    data = resp.json()

    if "imageUrl" in data and data["imageUrl"]:
        return data["imageUrl"]
    for key in ("image_url", "output", "url", "image"):
        if key in data and data[key]:
            return data[key]
    if "images" in data and data["images"]:
        img = data["images"][0]
        url = img.get("url") or img.get("imageUrl") if isinstance(img, dict) else str(img)
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
    config   = {}
    required = {
        "PIXAZO_API_KEY":         "Pixazo API key",
        "GOOGLE_CLIENT_ID":       "Google OAuth Client ID",
        "GOOGLE_CLIENT_SECRET":   "Google OAuth Client Secret",
        "GOOGLE_REFRESH_TOKEN":   "Google OAuth Refresh Token",
        "GOOGLE_DRIVE_FOLDER_ID": "Google Drive Parent Folder ID",
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

    config["MODEL"]             = os.environ.get("PIXAZO_MODEL", "flux-schnell").strip()
    config["WIDTH"]             = int(os.environ.get("PIXAZO_WIDTH",  "1024"))
    config["HEIGHT"]            = int(os.environ.get("PIXAZO_HEIGHT", "1024"))
    config["WORKERS"]           = 1
    config["COUNT"]             = os.environ.get("PIXAZO_COUNT", "ALL").strip().upper()
    config["NUM_STEPS"]         = int(os.environ.get("PIXAZO_NUM_STEPS", str(SDXL_NUM_STEPS)))
    config["GUIDANCE"]          = int(os.environ.get("PIXAZO_GUIDANCE",  str(SDXL_GUIDANCE)))
    config["PROMPTS_DIR"]       = os.environ.get("PIXAZO_PROMPTS_DIR", "prompts").strip()
    config["UPLOAD_BATCH_SIZE"] = int(os.environ.get(
        "PIXAZO_UPLOAD_BATCH_SIZE", str(DEFAULT_UPLOAD_BATCH_SIZE)))

    if config["MODEL"] not in VALID_MODELS:
        log.err(f"Invalid model: '{config['MODEL']}'. Valid: {sorted(VALID_MODELS)}")
        sys.exit(1)

    log.debug(f"Config: MODEL={config['MODEL']} SIZE={config['WIDTH']}x{config['HEIGHT']} "
              f"COUNT={config['COUNT']} BATCH={config['UPLOAD_BATCH_SIZE']}")
    return config


# ══════════════════════════════════════════════════════════════════════════════
# PROCESS ONE JSON FILE  ✅ v8.0 — batch upload + auto token refresh
# ══════════════════════════════════════════════════════════════════════════════

def process_single_json(json_path, config, auth):
    """
    auth: GoogleAuth object — token auto-refresh பண்ணும்.
    ஒவ்வொரு UPLOAD_BATCH_SIZE images-க்கும் Drive-க்கு upload பண்ணும்.
    """
    json_path      = Path(json_path)
    subfolder_name = json_path.stem

    log.step(f"PROCESSING: {json_path.name} → Drive/{subfolder_name}/")

    # ── Load JSON ──
    with open(json_path, "r", encoding="utf-8") as f:
        raw = f.read()
    raw       = raw.replace('"status":\n  }',  '"status": "pending"\n  }')
    raw       = raw.replace('"status": \n  }', '"status": "pending"\n  }')
    json_data = json.loads(raw)

    total  = len(json_data)
    done_c = sum(1 for x in json_data if x.get("status") == "completed")
    log.info(f"JSON: {total} total | {done_c} done | {total - done_c} pending")

    # ── Config ──
    model_name        = config["MODEL"]
    api_key           = config["PIXAZO_API_KEY"]
    width, height     = config["WIDTH"], config["HEIGHT"]
    num_steps         = config["NUM_STEPS"]
    guidance          = config["GUIDANCE"]
    count_str         = config["COUNT"]
    parent_folder_id  = config["GOOGLE_DRIVE_FOLDER_ID"]
    upload_batch_size = config["UPLOAD_BATCH_SIZE"]

    # ── Local output ──
    local_out = Path("generated_images") / subfolder_name
    local_out.mkdir(parents=True, exist_ok=True)

    # ── Create/find Drive subfolder ──
    log.section("Step 1: Drive Subfolder")
    sub_folder_id = create_drive_folder(subfolder_name, parent_folder_id, auth.get_token())
    log.info(f"Drive subfolder id={sub_folder_id}")

    # ── List existing files in Drive ──
    log.section("Step 2: List Existing Drive Files")
    existing_in_drive = list_drive_files(sub_folder_id, auth.get_token())

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
            continue

        if fname in existing_in_drive:
            item["status"]         = "completed"
            item["drive_uploaded"] = True
            skipped_drive += 1
            continue

        truly_pending.append(item)

    if skipped_disk:
        log.info(f"Skipped {skipped_disk} — already on disk")
    if skipped_drive:
        log.info(f"Skipped {skipped_drive} — already in Google Drive")
    log.info(f"Truly pending: {len(truly_pending)}")

    if count_str != "ALL":
        try:
            truly_pending = truly_pending[:int(count_str)]
        except ValueError:
            pass

    total_gen = len(truly_pending)
    result = {
        "json":          json_path.name,
        "generated":     0,
        "failed":        0,
        "uploaded":      0,
        "upload_failed": 0,
        "drive_calls":   2,   # folder + list already done
        "batches":       0,
        "time_seconds":  0,
    }

    if total_gen == 0:
        log.warn(f"'{json_path.name}' — nothing to generate!")
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(json_data, fh, indent=2, ensure_ascii=False)
        return result

    # ═══════════════════════════════════════════════════════════════════════════
    # GENERATE + BATCH UPLOAD LOOP  ✅ KEY CHANGE in v8.0
    # ═══════════════════════════════════════════════════════════════════════════
    log.section(
        f"Step 4: Generate {total_gen} Images "
        f"(Batch upload every {upload_batch_size})"
    )
    log.info(f"Model={model_name} | Size={width}x{height} | Rate=9 req/min")

    done_count          = 0
    fail_count          = 0
    total_uploaded      = 0
    total_upload_failed = []
    start_t             = time.time()
    current_batch       = []   # accumulate until batch_size
    batch_num           = 0

    for idx, item in enumerate(truly_pending, 1):
        fname    = item.get("filename", f"img_{item.get('index', 0)}.png")
        out_path = local_out / fname
        prompt   = item.get("prompt", "")
        seed     = int(item.get("seed", SDXL_DEFAULT_SEED))

        log.info(
            f"[{idx}/{total_gen}] Generating: {fname} | "
            f"seed={seed} | {rate_limiter.status()} | "
            f"Token: {auth.token_age_str()}"
        )

        try:
            img_url = generate_image_api(
                prompt, seed, model_name, api_key, width, height,
                negative_prompt=DEFAULT_NEG_PROMPT,
                num_steps=num_steps, guidance_scale=guidance)

            download_file(img_url, out_path)

            item["status"]      = "completed"
            item["output_path"] = str(out_path)
            item["done_at"]     = datetime.now().isoformat()
            current_batch.append(out_path)
            done_count += 1
            log.ok(f"  Generated: {fname}")

        except Exception as e:
            item["status"] = "failed"
            fail_count    += 1
            log.err(f"  FAILED: {fname} — {str(e)[:300]}")

        # ── Progress ──
        processed = done_count + fail_count
        elapsed   = max(time.time() - start_t, 0.001)
        rate      = processed / elapsed * 60
        remaining = total_gen - processed
        eta_s     = int(remaining / (processed / elapsed)) if processed > 0 else 0
        print(
            f"  Progress: {processed}/{total_gen} ({processed/total_gen*100:.0f}%) "
            f"| OK:{done_count} FAIL:{fail_count} "
            f"| {rate:.1f} img/min | ETA:{eta_s//60}m{eta_s%60}s "
            f"| Batch queue: {len(current_batch)}/{upload_batch_size}",
            flush=True
        )

        # ── Trigger batch upload every upload_batch_size images ──
        if len(current_batch) >= upload_batch_size:
            batch_num += 1
            log.section(
                f"BATCH {batch_num} TRIGGERED "
                f"({len(current_batch)} images ready) — uploading to Drive now..."
            )

            # Save JSON before upload (crash safety)
            try:
                with open(json_path, "w", encoding="utf-8") as fh:
                    json.dump(json_data, fh, indent=2, ensure_ascii=False)
            except Exception:
                pass

            up_count, failed = upload_batch_to_drive(
                current_batch, sub_folder_id, auth, json_data, batch_num)
            total_uploaded      += up_count
            total_upload_failed += failed
            result["drive_calls"] += up_count + len(failed)
            current_batch = []   # reset batch buffer
            log.ok(f"Batch {batch_num} done. Resuming generation...")

        # Periodic crash-safe JSON save
        try:
            with open(json_path, "w", encoding="utf-8") as fh:
                json.dump(json_data, fh, indent=2, ensure_ascii=False)
        except Exception:
            pass

    # ── Final batch: upload remaining images ──
    if current_batch:
        batch_num += 1
        log.section(
            f"FINAL BATCH {batch_num} "
            f"({len(current_batch)} remaining images) — uploading..."
        )
        up_count, failed = upload_batch_to_drive(
            current_batch, sub_folder_id, auth, json_data, batch_num)
        total_uploaded      += up_count
        total_upload_failed += failed
        result["drive_calls"] += up_count + len(failed)
        current_batch = []

    # ── Upload JSON status file to Drive ──
    log.section("Upload JSON Status to Drive")
    upload_to_google_drive(json_path, sub_folder_id, auth.get_token(),
                           mime_type="application/json")
    result["drive_calls"] += 1

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
        "generated":     done_count,
        "failed":        fail_count,
        "uploaded":      total_uploaded,
        "upload_failed": len(total_upload_failed),
        "batches":       batch_num,
        "time_seconds":  elapsed,
    })

    if total_upload_failed:
        log.err(f"{len(total_upload_failed)} upload(s) failed:")
        for mf in total_upload_failed:
            log.err(f"  ❌ {mf}")
    else:
        log.ok(
            f"All {total_uploaded} images uploaded in "
            f"{batch_num} batch(es)!"
        )

    log.info(
        f"[{json_path.name}] Done {elapsed}s | "
        f"Gen:{done_count} Fail:{fail_count} | "
        f"Uploaded:{total_uploaded} UploadFail:{len(total_upload_failed)} | "
        f"Batches:{batch_num} | DriveAPICalls:{result['drive_calls']}"
    )
    return result


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE  ✅ v8.0 — GoogleAuth object
# ══════════════════════════════════════════════════════════════════════════════

def run_pipeline(config):
    log.step("PIXAZO AI - HEADLESS GENERATOR v8.0 (Token Auto-Refresh + Batch Upload)")
    log.info(f"Model: {config['MODEL']} | Size: {config['WIDTH']}x{config['HEIGHT']}")
    log.info(f"Rate limit: {MAX_REQUESTS_PER_MINUTE} req/min | Workers: 1")
    log.info(f"Upload batch size: every {config['UPLOAD_BATCH_SIZE']} images")
    log.info(f"Token auto-refresh: every {GoogleAuth.TOKEN_TTL//60} min")
    log.info(f"Debug logging: {'ON' if Logger.debug_enabled else 'OFF'}")

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

    # ── GoogleAuth — auto-refresh token ──
    log.step("Google Drive Authentication")
    auth = GoogleAuth(
        config["GOOGLE_CLIENT_ID"],
        config["GOOGLE_CLIENT_SECRET"],
        config["GOOGLE_REFRESH_TOKEN"]
    )
    auth.get_token()   # First token fetch + validate credentials

    # ── Process each JSON ──
    all_results = []
    total_start = time.time()

    for idx, jf in enumerate(json_files, 1):
        log.step(f"FILE {idx}/{len(json_files)}: {jf.name}")
        try:
            r = process_single_json(jf, config, auth)   # auth object, not token string
            all_results.append(r)
        except Exception as e:
            log.err(f"Error in {jf.name}: {e}")
            import traceback
            traceback.print_exc()
            all_results.append({
                "json":          jf.name,
                "generated":     0,
                "failed":        0,
                "uploaded":      0,
                "upload_failed": 0,
                "drive_calls":   0,
                "batches":       0,
                "error":         str(e),
            })

    # ── Final summary ──
    total_elapsed = int(time.time() - total_start)
    log.step("FINAL SUMMARY")

    t_gen = t_fail = t_up = t_uf = t_dc = t_bat = 0
    for r in all_results:
        g   = r.get("generated",     0)
        f   = r.get("failed",        0)
        u   = r.get("uploaded",      0)
        uf  = r.get("upload_failed", 0)
        dc  = r.get("drive_calls",   0)
        bat = r.get("batches",       0)
        t_gen += g; t_fail += f; t_up += u
        t_uf  += uf; t_dc  += dc; t_bat += bat

        st = "OK  " if (f == 0 and uf == 0 and "error" not in r) else "WARN"
        print(
            f"  [{st}] {r['json']:30s} | "
            f"Gen:{g} Fail:{f} | Up:{u} UpFail:{uf} | "
            f"Batches:{bat} DriveCalls:{dc}",
            flush=True)

    print(flush=True)
    log.info(f"TOTALS — Gen:{t_gen} Fail:{t_fail} | "
             f"Uploaded:{t_up} UpFail:{t_uf} | "
             f"Batches:{t_bat} DriveCalls:{t_dc}")
    log.info(f"Total time: {total_elapsed}s ({total_elapsed//60}m{total_elapsed%60}s)")

    if t_fail > 0 or t_uf > 0:
        log.warn(f"Completed with issues — GenFail:{t_fail} UploadFail:{t_uf}")
        sys.exit(1)
    else:
        log.ok("All images generated and uploaded successfully!")


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
