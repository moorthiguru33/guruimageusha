#!/usr/bin/env python3
"""
PIXAZO AI - HEADLESS IMAGE GENERATOR v10.0 (ModelScope Edition)
────────────────────────────────────────────────────────────────
ModelScope Async API + Google Drive Batch Upload
Auto Model Rotation when per-model quota (500/day) is exhausted

MODELS (Cloud Inference - Free API):
  ✅ Tongyi-MAI/Z-Image-Turbo  — Ultra-fast turbo (9 steps)      [500/day]
  ✅ Tongyi-MAI/Z-Image        — Full quality Z-Image model       [500/day]
  ✅ Qwen/Qwen-Image           — Alibaba 20B model (best quality) [500/day]
  ✅ Qwen/Qwen-Image-2512      — Latest Dec 2025 update           [500/day]
  ✅ MusePublic/Qwen-image     — MusePublic variant               [500/day]

  Total possible per day (all 5 models): 2000+ images

API FLOW (Async):
  1.  POST /v1/images/generations  → task_id
  2.  GET  /v1/tasks/{task_id}     → poll every 5s
  3.  status=SUCCEED → image URL download

Environment Variables Required:
  SCOPE, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
  GOOGLE_REFRESH_TOKEN, GOOGLE_DRIVE_FOLDER_ID

Optional:
  PIXAZO_MODELS          — comma-separated model rotation list
                           e.g. "z-image-turbo,z-image,qwen-image"
                           default: "z-image-turbo,z-image,qwen-image,qwen-image-2512,muse-qwen"
  PIXAZO_MODEL           — single model (overrides PIXAZO_MODELS if set alone)
  PIXAZO_WIDTH           — image width  (default: 1024)
  PIXAZO_HEIGHT          — image height (default: 1024)
  PIXAZO_COUNT           — images per JSON (number or ALL)
  PIXAZO_PROMPTS_DIR     — prompts folder (default: prompts)
  PIXAZO_UPLOAD_BATCH_SIZE — upload batch size (default: 500)
  PIXAZO_DEBUG           — set to "1" for verbose debug logs
"""

import base64
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

MODELSCOPE_BASE_URL   = "https://api-inference.modelscope.ai/"
MODELSCOPE_SUBMIT_URL = f"{MODELSCOPE_BASE_URL}v1/images/generations"
MODELSCOPE_TASK_URL   = f"{MODELSCOPE_BASE_URL}v1/tasks/{{task_id}}"

# ── All available ModelScope AIGC image models ──
MODELSCOPE_MODEL_IDS = {
    "z-image-turbo":   "Tongyi-MAI/Z-Image-Turbo",   # fastest, 9 steps
    "z-image":         "Tongyi-MAI/Z-Image",           # full quality
    "qwen-image":      "Qwen/Qwen-Image",              # 20B best quality
    "qwen-image-2512": "Qwen/Qwen-Image-2512",         # Dec 2025 update
    "muse-qwen":       "MusePublic/Qwen-image",        # MusePublic variant
}

# ── Per-model generation defaults ──
MODEL_DEFAULTS = {
    "z-image-turbo":   {"steps": 9,  "guidance": 0.0, "neg_prompt": False},
    "z-image":         {"steps": 30, "guidance": 2.0, "neg_prompt": True},
    "qwen-image":      {"steps": 50, "guidance": 4.0, "neg_prompt": True},
    "qwen-image-2512": {"steps": 50, "guidance": 4.0, "neg_prompt": True},
    "muse-qwen":       {"steps": 50, "guidance": 4.0, "neg_prompt": True},
}

# Official per-model daily limit (from ModelScope docs)
MODEL_DAILY_LIMIT = 500

VALID_MODELS      = set(MODELSCOPE_MODEL_IDS.keys())
SDXL_DEFAULT_SEED = 40

DEFAULT_NEG_PROMPT = (
    "low quality, blurry, distorted, deformed, ugly, watermark, text, "
    "bad anatomy, worst quality, jpeg artifacts, out of frame, extra limbs"
)

GOOGLE_TOKEN_URL  = "https://oauth2.googleapis.com/token"
GOOGLE_UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"
GOOGLE_DRIVE_API  = "https://www.googleapis.com/drive/v3/files"

MAX_REQUESTS_PER_MINUTE   = 9
RATE_WINDOW_SECONDS       = 60
APPS_SCRIPT_MAX_RETRIES   = 3
APPS_SCRIPT_RETRY_DELAY   = 10
VERIFY_WAIT_SECONDS       = 5
DEFAULT_UPLOAD_BATCH_SIZE = 500

TASK_POLL_INTERVAL = 5    # seconds between polls
TASK_MAX_WAIT      = 300  # max 5 minutes per task


# ══════════════════════════════════════════════════════════════════════════════
# MODEL QUOTA TRACKER  ✅ NEW v10.0
# ══════════════════════════════════════════════════════════════════════════════

class ModelQuotaTracker:
    """
    Tracks per-model remaining quota from ModelScope response headers.
    Auto-switches to next model when current model quota is exhausted.

    Headers used:
      modelscope-ratelimit-model-requests-limit     → model daily limit
      modelscope-ratelimit-model-requests-remaining → model remaining quota
      modelscope-ratelimit-requests-limit           → user total daily limit
      modelscope-ratelimit-requests-remaining       → user total remaining quota
    """

    def __init__(self, model_rotation: list):
        if not model_rotation:
            raise ValueError("model_rotation list cannot be empty")

        self.rotation        = model_rotation         # ordered list of model keys
        self.current_idx     = 0                      # index into rotation
        self.model_remaining = {}                     # model_key → remaining count
        self.user_remaining  = None                   # total user remaining
        self.exhausted       = set()                  # models with 0 remaining

        # Initialize all models as having full quota
        for m in model_rotation:
            self.model_remaining[m] = MODEL_DAILY_LIMIT

        log.info(f"Model rotation: {' → '.join(rotation_display(model_rotation))}")

    @property
    def current_model(self) -> str:
        return self.rotation[self.current_idx]

    def update_from_headers(self, headers: dict, model_key: str):
        """Parse ModelScope quota headers and update internal state."""
        try:
            model_limit = int(headers.get(
                "modelscope-ratelimit-model-requests-limit", MODEL_DAILY_LIMIT))
            model_rem   = int(headers.get(
                "modelscope-ratelimit-model-requests-remaining",
                self.model_remaining.get(model_key, MODEL_DAILY_LIMIT)))
            user_rem    = int(headers.get(
                "modelscope-ratelimit-requests-remaining", 9999))

            self.model_remaining[model_key] = model_rem
            self.user_remaining             = user_rem

            log.debug(
                f"Quota headers → model={model_key} "
                f"remaining={model_rem}/{model_limit} | "
                f"user_total_remaining={user_rem}"
            )

            if model_rem <= 0:
                log.warn(f"Model '{model_key}' quota EXHAUSTED (0 remaining)")
                self.exhausted.add(model_key)

        except (ValueError, TypeError):
            pass  # headers absent — ignore

    def should_switch(self) -> bool:
        """Returns True if current model is exhausted."""
        return self.current_model in self.exhausted

    def switch_to_next(self) -> bool:
        """
        Advance to next non-exhausted model in rotation.
        Returns True if a valid model was found, False if all exhausted.
        """
        original = self.current_idx
        for _ in range(len(self.rotation)):
            self.current_idx = (self.current_idx + 1) % len(self.rotation)
            if self.current_model not in self.exhausted:
                log.ok(
                    f"Switched to model: '{self.current_model}' "
                    f"({MODELSCOPE_MODEL_IDS[self.current_model]})"
                )
                return True
        # All exhausted — stay at original
        self.current_idx = original
        return False

    def status_line(self) -> str:
        parts = []
        for m in self.rotation:
            rem = self.model_remaining.get(m, "?")
            tag = "✅" if m not in self.exhausted else "❌"
            parts.append(f"{tag}{m}:{rem}")
        user_str = f" | user_total:{self.user_remaining}" if self.user_remaining is not None else ""
        return "  ".join(parts) + user_str


def rotation_display(rotation):
    return [f"{k}({MODELSCOPE_MODEL_IDS[k]})" for k in rotation]


# ══════════════════════════════════════════════════════════════════════════════
# GOOGLE AUTH — AUTO REFRESH
# ══════════════════════════════════════════════════════════════════════════════

class GoogleAuth:
    TOKEN_TTL = 3000  # 50 minutes

    def __init__(self, client_id, client_secret, refresh_token):
        self.client_id     = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self._token        = None
        self._token_time   = 0

    def get_token(self):
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
    resp = requests.post(GOOGLE_TOKEN_URL, data={
        "client_id":     client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type":    "refresh_token",
    }, timeout=30)
    if not resp.ok:
        raise RuntimeError(f"Token refresh failed: {resp.status_code} | {resp.text[:200]}")
    token = resp.json().get("access_token")
    if not token:
        raise RuntimeError("No access_token in response")
    return token


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
    log.debug(f"Listing files in Drive folder id={folder_id}")
    all_files  = {}
    page_token = None
    page_num   = 0
    while True:
        page_num += 1
        params = {
            "q":        f"'{folder_id}' in parents and trashed=false",
            "fields":   "nextPageToken, files(id,name,size,mimeType)",
            "pageSize": 1000,
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
        mime_map = {
            ".png":  "image/png",
            ".jpg":  "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".json": "application/json",
            ".zip":  "application/zip",
        }
        mime_type = mime_map.get(file_path.suffix.lower(), "application/octet-stream")
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
# GOOGLE DRIVE — DELETE
# ══════════════════════════════════════════════════════════════════════════════

def delete_drive_file(file_id, file_name, access_token):
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
# BATCH UPLOAD TO DRIVE
# ══════════════════════════════════════════════════════════════════════════════

def upload_batch_to_drive(batch_images, sub_folder_id, auth, json_data, batch_num):
    total = len(batch_images)
    log.step(f"BATCH {batch_num} UPLOAD: {total} images → Google Drive")
    uploaded_list = []
    failed_list   = []
    for i, img_path in enumerate(batch_images, 1):
        fname        = Path(img_path).name
        log.info(f"  [{i}/{total}] Uploading: {fname} | Token: {auth.token_age_str()}")
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
    log.info(f"Batch {batch_num} complete: ✅ {len(uploaded_list)} uploaded | ❌ {len(failed_list)} failed")
    return len(uploaded_list), failed_list


# ══════════════════════════════════════════════════════════════════════════════
# IMAGE GENERATION — MODELSCOPE ASYNC API  ✅ v10.0
# ══════════════════════════════════════════════════════════════════════════════

def generate_image_modelscope(prompt, seed, api_key, width, height,
                               model_name="z-image-turbo",
                               negative_prompt="",
                               num_steps=None,
                               guidance_scale=None,
                               quota_tracker=None):
    """
    ModelScope Async API.
    Returns: (image_url: str, response_headers: dict)

    quota_tracker: ModelQuotaTracker — updated from response headers automatically.
    """
    model_id  = MODELSCOPE_MODEL_IDS[model_name]
    model_cfg = MODEL_DEFAULTS[model_name]

    steps    = num_steps      if num_steps      is not None else model_cfg["steps"]
    guidance = guidance_scale if guidance_scale is not None else model_cfg["guidance"]
    use_neg  = model_cfg["neg_prompt"]

    submit_headers = {
        "Authorization":           f"Bearer {api_key}",
        "Content-Type":            "application/json",
        "X-ModelScope-Async-Mode": "true",
    }
    poll_headers = {
        "Authorization":          f"Bearer {api_key}",
        "Content-Type":           "application/json",
        "X-ModelScope-Task-Type": "image_generation",
    }

    payload = {
        "model":               model_id,
        "prompt":              prompt,
        "size":                f"{int(width)}x{int(height)}",
        "n":                   1,
        "seed":                int(seed) % 2147483647,
        "num_inference_steps": int(steps),
        "guidance_scale":      float(guidance),
    }
    if use_neg and negative_prompt:
        payload["negative_prompt"] = negative_prompt

    log.debug(f"ModelScope submit: model={model_id} size={width}x{height} "
              f"steps={steps} guidance={guidance}")

    rate_limiter.wait_if_needed()

    # ── STEP 1: Submit Task ──
    t0 = time.time()
    resp = requests.post(
        MODELSCOPE_SUBMIT_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=submit_headers,
        timeout=60,
    )
    log.debug(f"Submit HTTP {resp.status_code} in {time.time()-t0:.1f}s")

    # ── Read quota headers from submit response ──
    if quota_tracker is not None:
        quota_tracker.update_from_headers(dict(resp.headers), model_name)

    if not resp.ok:
        raise ValueError(f"Submit failed: HTTP {resp.status_code} | {resp.text[:600]}")

    submit_data = resp.json()
    task_id     = submit_data.get("task_id")
    if not task_id:
        raise ValueError(f"task_id missing in response: {json.dumps(submit_data)[:300]}")

    log.info(f"Task submitted: {task_id} | Polling every {TASK_POLL_INTERVAL}s...")

    # ── STEP 2: Poll Task Status ──
    poll_url   = MODELSCOPE_TASK_URL.format(task_id=task_id)
    deadline   = time.time() + TASK_MAX_WAIT
    poll_count = 0

    while time.time() < deadline:
        time.sleep(TASK_POLL_INTERVAL)
        poll_count += 1
        poll_resp  = requests.get(poll_url, headers=poll_headers, timeout=30)
        log.debug(f"Poll #{poll_count} HTTP {poll_resp.status_code}")
        if not poll_resp.ok:
            log.warn(f"Poll failed: HTTP {poll_resp.status_code} — retrying...")
            continue

        task_data   = poll_resp.json()
        task_status = task_data.get("task_status", "")
        log.debug(f"task_status: {task_status}")

        if task_status == "SUCCEED":
            output_images = task_data.get("output_images", [])
            if output_images:
                img_url = output_images[0]
                elapsed = int(time.time() - t0)
                log.ok(f"Image ready in {elapsed}s | {img_url[:80]}...")
                return img_url, dict(resp.headers)
            raise ValueError(f"SUCCEED but no output_images: {json.dumps(task_data)[:400]}")

        elif task_status == "FAILED":
            err = task_data.get("error") or task_data.get("message", "Unknown")
            raise ValueError(f"Task FAILED: {err}")

        elapsed = int(time.time() - t0)
        log.info(f"  {task_status} ... {elapsed}s elapsed")

    raise TimeoutError(f"Task {task_id} timed out after {TASK_MAX_WAIT}s")


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

DEFAULT_MODEL_ROTATION = [
    "z-image-turbo",
    "z-image",
    "qwen-image",
    "qwen-image-2512",
    "muse-qwen",
]


def load_config():
    config   = {}
    required = {
        "SCOPE":                  "ModelScope API Key",
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

    # ── Model rotation (v10.0) ──
    # PIXAZO_MODELS = "z-image-turbo,z-image,qwen-image"  (comma-separated)
    # PIXAZO_MODEL  = "z-image-turbo"  (single model, for backwards compat)
    models_env  = os.environ.get("PIXAZO_MODELS", "").strip()
    model_single = os.environ.get("PIXAZO_MODEL", "").strip()

    if models_env:
        rotation = [m.strip() for m in models_env.split(",") if m.strip()]
    elif model_single:
        rotation = [model_single]
    else:
        rotation = DEFAULT_MODEL_ROTATION

    # Validate
    invalid = [m for m in rotation if m not in VALID_MODELS]
    if invalid:
        log.err(f"Invalid model(s) in rotation: {invalid}")
        log.err(f"Valid models: {sorted(VALID_MODELS)}")
        sys.exit(1)

    config["MODEL_ROTATION"]    = rotation
    config["MODEL"]             = rotation[0]   # primary (for display)
    config["WIDTH"]             = int(os.environ.get("PIXAZO_WIDTH",  "1024"))
    config["HEIGHT"]            = int(os.environ.get("PIXAZO_HEIGHT", "1024"))
    config["COUNT"]             = os.environ.get("PIXAZO_COUNT", "ALL").strip().upper()
    config["NUM_STEPS"]         = None
    config["GUIDANCE"]          = None
    config["PROMPTS_DIR"]       = os.environ.get("PIXAZO_PROMPTS_DIR", "prompts").strip()
    config["UPLOAD_BATCH_SIZE"] = int(os.environ.get(
        "PIXAZO_UPLOAD_BATCH_SIZE", str(DEFAULT_UPLOAD_BATCH_SIZE)))

    log.debug(f"Config: ROTATION={rotation} SIZE={config['WIDTH']}x{config['HEIGHT']} "
              f"COUNT={config['COUNT']} BATCH={config['UPLOAD_BATCH_SIZE']}")
    return config


# ══════════════════════════════════════════════════════════════════════════════
# PROCESS ONE JSON FILE  ✅ v10.0 — Auto model rotation
# ══════════════════════════════════════════════════════════════════════════════

def process_single_json(json_path, config, auth, quota_tracker):
    """
    quota_tracker: ModelQuotaTracker shared across all JSON files.
    Auto-switches model when per-model 500/day quota is exhausted.
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

    api_key           = config["SCOPE"]
    width, height     = config["WIDTH"], config["HEIGHT"]
    num_steps         = config["NUM_STEPS"]
    guidance          = config["GUIDANCE"]
    count_str         = config["COUNT"]
    parent_folder_id  = config["GOOGLE_DRIVE_FOLDER_ID"]
    upload_batch_size = config["UPLOAD_BATCH_SIZE"]

    local_out = Path("generated_images") / subfolder_name
    local_out.mkdir(parents=True, exist_ok=True)

    log.section("Step 1: Drive Subfolder")
    sub_folder_id = create_drive_folder(subfolder_name, parent_folder_id, auth.get_token())
    log.info(f"Drive subfolder id={sub_folder_id}")

    log.section("Step 2: List Existing Drive Files")
    existing_in_drive = list_drive_files(sub_folder_id, auth.get_token())

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
        "drive_calls":   2,
        "batches":       0,
        "time_seconds":  0,
    }

    if total_gen == 0:
        log.warn(f"'{json_path.name}' — nothing to generate!")
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(json_data, fh, indent=2, ensure_ascii=False)
        return result

    # ══════════════════════════════════════════════════════════════════════
    # GENERATE + BATCH UPLOAD LOOP with Auto Model Rotation  ✅ v10.0
    # ══════════════════════════════════════════════════════════════════════
    log.section(
        f"Step 4: Generate {total_gen} Images "
        f"(Batch upload every {upload_batch_size})"
    )
    log.info(f"Model rotation: {quota_tracker.rotation}")
    log.info(f"Active model: {quota_tracker.current_model} "
             f"({MODELSCOPE_MODEL_IDS[quota_tracker.current_model]})")
    log.info(f"Size={width}x{height} | Rate=9 req/min")

    done_count          = 0
    fail_count          = 0
    total_uploaded      = 0
    total_upload_failed = []
    start_t             = time.time()
    current_batch       = []
    batch_num           = 0

    for idx, item in enumerate(truly_pending, 1):
        fname    = item.get("filename", f"img_{item.get('index', 0)}.png")
        out_path = local_out / fname
        prompt   = item.get("prompt", "")
        seed     = int(item.get("seed", SDXL_DEFAULT_SEED))

        # ── Auto model switch check ──
        if quota_tracker.should_switch():
            log.warn(
                f"Model '{quota_tracker.current_model}' quota exhausted! "
                f"Switching to next model..."
            )
            if not quota_tracker.switch_to_next():
                log.err("ALL models quota exhausted for today! Stopping generation.")
                log.err(f"Quota status: {quota_tracker.status_line()}")
                break

        active_model = quota_tracker.current_model

        log.info(
            f"[{idx}/{total_gen}] Generating: {fname} | "
            f"model={active_model} | seed={seed} | "
            f"{rate_limiter.status()} | Token: {auth.token_age_str()}"
        )
        log.debug(f"Quota: {quota_tracker.status_line()}")

        try:
            model_cfg = MODEL_DEFAULTS[active_model]
            neg_p     = DEFAULT_NEG_PROMPT if model_cfg["neg_prompt"] else ""

            img_url, resp_headers = generate_image_modelscope(
                prompt, seed, api_key, width, height,
                model_name=active_model,
                negative_prompt=neg_p,
                num_steps=num_steps,
                guidance_scale=guidance,
                quota_tracker=quota_tracker,
            )

            download_file(img_url, out_path)

            item["status"]      = "completed"
            item["output_path"] = str(out_path)
            item["done_at"]     = datetime.now().isoformat()
            item["model_used"]  = active_model   # track which model generated it
            current_batch.append(out_path)
            done_count += 1
            log.ok(f"  Generated: {fname} [model={active_model}]")

        except Exception as e:
            err_str = str(e)[:300]
            item["status"] = "failed"
            fail_count    += 1
            log.err(f"  FAILED: {fname} — {err_str}")

            # If Task FAILED, this model might be quota-exhausted on AIGC side
            # Force quota check on next iteration
            if "Task FAILED" in err_str:
                log.warn(
                    f"Task FAILED detected on model '{active_model}'. "
                    f"Marking as potentially exhausted and switching..."
                )
                quota_tracker.exhausted.add(active_model)

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
            f"| Model:{quota_tracker.current_model} "
            f"| Batch queue: {len(current_batch)}/{upload_batch_size}",
            flush=True
        )

        # ── Trigger batch upload ──
        if len(current_batch) >= upload_batch_size:
            batch_num += 1
            log.section(
                f"BATCH {batch_num} TRIGGERED "
                f"({len(current_batch)} images ready) — uploading to Drive now..."
            )
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
            current_batch = []
            log.ok(f"Batch {batch_num} done. Resuming generation...")

        # Periodic crash-safe JSON save
        try:
            with open(json_path, "w", encoding="utf-8") as fh:
                json.dump(json_data, fh, indent=2, ensure_ascii=False)
        except Exception:
            pass

    # ── Final batch upload ──
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

    # ── Upload JSON status file ──
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
        log.ok(f"All {total_uploaded} images uploaded in {batch_num} batch(es)!")

    log.info(
        f"[{json_path.name}] Done {elapsed}s | "
        f"Gen:{done_count} Fail:{fail_count} | "
        f"Uploaded:{total_uploaded} UploadFail:{len(total_upload_failed)} | "
        f"Batches:{batch_num} | DriveAPICalls:{result['drive_calls']}"
    )
    return result


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE  ✅ v10.0
# ══════════════════════════════════════════════════════════════════════════════

def run_pipeline(config):
    rotation = config["MODEL_ROTATION"]
    max_day  = len(rotation) * MODEL_DAILY_LIMIT

    log.step(
        "PIXAZO AI - HEADLESS GENERATOR v10.0 "
        "(ModelScope API + Multi-Model Rotation + Auto Quota Switch)"
    )
    log.info(f"Model rotation ({len(rotation)} models): {rotation}")
    log.info(f"Max images today (all models): ~{max_day}")
    log.info(f"Size: {config['WIDTH']}x{config['HEIGHT']}")
    log.info(f"Rate limit: {MAX_REQUESTS_PER_MINUTE} req/min")
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

    # ── Google Auth ──
    log.step("Google Drive Authentication")
    auth = GoogleAuth(
        config["GOOGLE_CLIENT_ID"],
        config["GOOGLE_CLIENT_SECRET"],
        config["GOOGLE_REFRESH_TOKEN"]
    )
    auth.get_token()

    # ── Shared quota tracker (persists across all JSON files) ──
    quota_tracker = ModelQuotaTracker(rotation)

    # ── Process each JSON ──
    all_results = []
    total_start = time.time()

    for idx, jf in enumerate(json_files, 1):
        log.step(f"FILE {idx}/{len(json_files)}: {jf.name}")
        log.info(f"Quota status: {quota_tracker.status_line()}")
        try:
            r = process_single_json(jf, config, auth, quota_tracker)
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

    # ── Final Summary ──
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
    log.info(f"Final quota: {quota_tracker.status_line()}")

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
