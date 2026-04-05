#!/usr/bin/env python3
"""
PIXAZO AI - HEADLESS IMAGE GENERATOR v5.1  (GitHub Actions + Google Drive)
──────────────────────────────────────────────────────────────────────────
• prompts/ folder-ல் உள்ள எல்லா JSON files-ஐயும் process பண்ணும்
• JSON filename = Google Drive subfolder name
• RATE LIMIT: 9 requests per minute (1 worker only)

Environment Variables Required (GitHub Secrets):
  PIXAZO_API_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
  GOOGLE_REFRESH_TOKEN, GOOGLE_DRIVE_FOLDER_ID

Optional:
  PIXAZO_MODEL, PIXAZO_WIDTH, PIXAZO_HEIGHT, PIXAZO_COUNT,
  PIXAZO_NUM_STEPS, PIXAZO_GUIDANCE, PIXAZO_PROMPTS_DIR
"""

import json
import os
import sys
import time
import io
import requests
from pathlib import Path
from datetime import datetime
from collections import deque
import threading

# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
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

# ── RATE LIMIT CONFIG ──
MAX_REQUESTS_PER_MINUTE = 9
RATE_WINDOW_SECONDS     = 60


# ══════════════════════════════════════════════════════════════════════════════
# RATE LIMITER — 9 requests per minute
# ══════════════════════════════════════════════════════════════════════════════
class RateLimiter:
    """
    Sliding window rate limiter.
    9 requests per 60 seconds — 10th request will wait until oldest expires.
    """
    def __init__(self, max_requests=MAX_REQUESTS_PER_MINUTE,
                 window_seconds=RATE_WINDOW_SECONDS):
        self.max_requests   = max_requests
        self.window_seconds = window_seconds
        self.timestamps     = deque()

    def wait_if_needed(self):
        """Call this BEFORE each API request."""
        now = time.time()

        # Remove timestamps older than the window
        while self.timestamps and (now - self.timestamps[0]) >= self.window_seconds:
            self.timestamps.popleft()

        # If we've hit the limit, wait
        if len(self.timestamps) >= self.max_requests:
            oldest    = self.timestamps[0]
            wait_time = self.window_seconds - (now - oldest) + 0.5  # +0.5s safety
            if wait_time > 0:
                log.warn(f"Rate limit: {self.max_requests} req/min reached. "
                         f"Waiting {wait_time:.1f}s...")
                time.sleep(wait_time)
                # Clean up again after waiting
                now = time.time()
                while self.timestamps and (now - self.timestamps[0]) >= self.window_seconds:
                    self.timestamps.popleft()

        # Record this request
        self.timestamps.append(time.time())

    def status(self):
        """Current usage info"""
        now = time.time()
        while self.timestamps and (now - self.timestamps[0]) >= self.window_seconds:
            self.timestamps.popleft()
        used = len(self.timestamps)
        return f"{used}/{self.max_requests} req used in current minute window"


# Global rate limiter instance
rate_limiter = RateLimiter()


# ══════════════════════════════════════════════════════════════════════════════
# LOGGER
# ══════════════════════════════════════════════════════════════════════════════
class Logger:
    @staticmethod
    def _ts():
        return datetime.now().strftime("%H:%M:%S")

    @staticmethod
    def info(msg):
        print(f"[{Logger._ts()}] INFO  {msg}", flush=True)

    @staticmethod
    def ok(msg):
        print(f"[{Logger._ts()}] OK    {msg}", flush=True)

    @staticmethod
    def warn(msg):
        print(f"[{Logger._ts()}] WARN  {msg}", flush=True)

    @staticmethod
    def err(msg):
        print(f"[{Logger._ts()}] ERROR {msg}", flush=True)

    @staticmethod
    def step(msg):
        print(f"\n{'='*60}", flush=True)
        print(f"  {msg}", flush=True)
        print(f"{'='*60}", flush=True)


log = Logger()


# ══════════════════════════════════════════════════════════════════════════════
# GOOGLE DRIVE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_google_access_token(client_id, client_secret, refresh_token):
    resp = requests.post(GOOGLE_TOKEN_URL, data={
        "client_id":     client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type":    "refresh_token",
    }, timeout=30)
    if not resp.ok:
        raise RuntimeError(
            f"Google token refresh failed ({resp.status_code}): {resp.text[:300]}"
        )
    token = resp.json().get("access_token")
    if not token:
        raise RuntimeError("No access_token in Google response")
    log.ok("Google Access Token obtained")
    return token


def find_drive_folder(folder_name, parent_id, access_token):
    query = (
        f"name='{folder_name}' and "
        f"'{parent_id}' in parents and "
        f"mimeType='application/vnd.google-apps.folder' and "
        f"trashed=false"
    )
    resp = requests.get(
        GOOGLE_DRIVE_API,
        params={"q": query, "fields": "files(id,name)", "pageSize": 1},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    if not resp.ok:
        log.err(f"Drive search failed: {resp.status_code} - {resp.text[:200]}")
        return None
    files = resp.json().get("files", [])
    return files[0]["id"] if files else None


def create_drive_folder(folder_name, parent_id, access_token):
    existing_id = find_drive_folder(folder_name, parent_id, access_token)
    if existing_id:
        log.info(f"Drive subfolder exists: '{folder_name}' (id: {existing_id})")
        return existing_id

    metadata = {
        "name":     folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents":  [parent_id],
    }
    resp = requests.post(
        GOOGLE_DRIVE_API,
        json=metadata,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type":  "application/json",
        },
        timeout=30,
    )
    if not resp.ok:
        raise RuntimeError(
            f"Failed to create folder '{folder_name}': "
            f"{resp.status_code} - {resp.text[:300]}"
        )
    fid = resp.json().get("id")
    log.ok(f"Created Drive subfolder: '{folder_name}' (id: {fid})")
    return fid


def upload_to_google_drive(file_path, folder_id, access_token, mime_type=None):
    file_path = Path(file_path)
    if not file_path.exists():
        log.err(f"Upload skipped - file not found: {file_path}")
        return None

    if mime_type is None:
        ext = file_path.suffix.lower()
        mime_map = {
            ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".webp": "image/webp", ".json": "application/json",
        }
        mime_type = mime_map.get(ext, "application/octet-stream")

    metadata = {"name": file_path.name, "parents": [folder_id]}
    boundary = "pixazo_upload_boundary"
    body = io.BytesIO()

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

    resp = requests.post(
        f"{GOOGLE_UPLOAD_URL}?uploadType=multipart",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type":  f"multipart/related; boundary={boundary}",
        },
        data=body.getvalue(),
        timeout=120,
    )

    if not resp.ok:
        log.err(f"Upload failed {file_path.name}: HTTP {resp.status_code}")
        return None

    file_id = resp.json().get("id", "")
    log.ok(f"Uploaded: {file_path.name} (id: {file_id})")
    return file_id


# ══════════════════════════════════════════════════════════════════════════════
# PIXAZO API FUNCTIONS  (with rate limiting)
# ══════════════════════════════════════════════════════════════════════════════

def generate_image_flux(prompt, seed, api_key, width, height):
    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
        "Content-Type":              "application/json",
        "Cache-Control":             "no-cache",
    }
    payload = {
        "prompt": prompt, "num_steps": int(FLUX_STEPS),
        "seed": int(seed), "width": int(width), "height": int(height),
    }

    # ── RATE LIMIT: wait if needed before calling API ──
    rate_limiter.wait_if_needed()

    resp = requests.post(FLUX_ENDPOINT, json=payload, headers=headers, timeout=180)
    resp.raise_for_status()
    data = resp.json()
    for key in ("output", "imageUrl", "image_url", "url", "image"):
        if key in data and data[key]:
            return data[key]
    if "images" in data and data["images"]:
        img = data["images"][0]
        return img.get("url") or img.get("imageUrl") if isinstance(img, dict) else str(img)
    raise ValueError("Flux: no image URL: " + json.dumps(data)[:300])


def generate_image_sdxl(prompt, seed, api_key, width, height,
                         negative_prompt, num_steps, guidance_scale):
    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
        "Content-Type":              "application/json",
        "Cache-Control":             "no-cache",
    }
    payload = {
        "prompt": str(prompt), "negative_prompt": str(negative_prompt),
        "height": int(height), "width": int(width),
        "num_steps": int(num_steps), "guidance_scale": int(guidance_scale),
        "seed": int(seed),
    }

    # ── RATE LIMIT: wait if needed before calling API ──
    rate_limiter.wait_if_needed()

    resp = requests.post(SDXL_ENDPOINT, json=payload, headers=headers, timeout=180)
    try:
        body_text = resp.text[:600]
    except Exception:
        body_text = "(unreadable)"
    if not resp.ok:
        raise ValueError(f"HTTP {resp.status_code} | {body_text}")
    data = resp.json()
    if "imageUrl" in data and data["imageUrl"]:
        return data["imageUrl"]
    for key in ("image_url", "output", "url", "image"):
        if key in data and data[key]:
            return data[key]
    if "images" in data and data["images"]:
        img = data["images"][0]
        return img.get("url") or img.get("imageUrl") if isinstance(img, dict) else str(img)
    raise ValueError("SDXL: no imageUrl: " + json.dumps(data)[:400])


def generate_image_api(prompt, seed, model_name, api_key, width, height,
                        negative_prompt="", num_steps=SDXL_NUM_STEPS,
                        guidance_scale=SDXL_GUIDANCE):
    if model_name == "flux-schnell":
        return generate_image_flux(prompt, seed, api_key, width, height)
    elif model_name in SDXL_MODELS:
        return generate_image_sdxl(
            prompt, seed, api_key, width, height,
            negative_prompt, num_steps, guidance_scale)
    else:
        raise ValueError("Unknown model: " + model_name)


def download_file(url, save_path):
    r = requests.get(url, timeout=90)
    r.raise_for_status()
    with open(str(save_path), "wb") as f:
        f.write(r.content)


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

def load_config():
    config = {}
    required = {
        "PIXAZO_API_KEY":          "Pixazo API key",
        "GOOGLE_CLIENT_ID":        "Google OAuth Client ID",
        "GOOGLE_CLIENT_SECRET":    "Google OAuth Client Secret",
        "GOOGLE_REFRESH_TOKEN":    "Google OAuth Refresh Token",
        "GOOGLE_DRIVE_FOLDER_ID":  "Google Drive Parent Folder ID",
    }

    missing = []
    for key, label in required.items():
        val = os.environ.get(key, "").strip()
        if not val:
            missing.append(f"  - {key} ({label})")
        config[key] = val

    if missing:
        log.err("Missing required environment variables:")
        for m in missing:
            print(m, flush=True)
        sys.exit(1)

    config["MODEL"]       = os.environ.get("PIXAZO_MODEL", "flux-schnell").strip()
    config["WIDTH"]       = int(os.environ.get("PIXAZO_WIDTH", "1024"))
    config["HEIGHT"]      = int(os.environ.get("PIXAZO_HEIGHT", "1024"))
    config["WORKERS"]     = 1   # ALWAYS 1 — rate limit protection
    config["COUNT"]       = os.environ.get("PIXAZO_COUNT", "ALL").strip().upper()
    config["NUM_STEPS"]   = int(os.environ.get("PIXAZO_NUM_STEPS", str(SDXL_NUM_STEPS)))
    config["GUIDANCE"]    = int(os.environ.get("PIXAZO_GUIDANCE", str(SDXL_GUIDANCE)))
    config["PROMPTS_DIR"] = os.environ.get("PIXAZO_PROMPTS_DIR", "prompts").strip()

    if config["MODEL"] not in VALID_MODELS:
        log.err(f"Invalid model: {config['MODEL']}")
        sys.exit(1)

    return config


# ══════════════════════════════════════════════════════════════════════════════
# PROCESS ONE JSON FILE  (sequential, rate-limited)
# ══════════════════════════════════════════════════════════════════════════════

def process_single_json(json_path, config, access_token):
    json_path = Path(json_path)
    subfolder_name = json_path.stem

    log.step(f"PROCESSING: {json_path.name} -> Drive/{subfolder_name}/")

    # Load JSON
    with open(json_path, "r", encoding="utf-8") as f:
        raw = f.read()
    raw = raw.replace('"status":\n  }',  '"status": "pending"\n  }')
    raw = raw.replace('"status": \n  }', '"status": "pending"\n  }')
    json_data = json.loads(raw)

    total  = len(json_data)
    done_c = sum(1 for x in json_data if x.get("status") == "completed")
    log.info(f"Loaded: {total} total | {done_c} done | {total - done_c} pending")

    # Config
    model_name = config["MODEL"]
    api_key    = config["PIXAZO_API_KEY"]
    width, height = config["WIDTH"], config["HEIGHT"]
    num_steps  = config["NUM_STEPS"]
    guidance   = config["GUIDANCE"]
    count_str  = config["COUNT"]
    parent_folder_id = config["GOOGLE_DRIVE_FOLDER_ID"]

    # Local output
    local_out = Path("generated_images") / subfolder_name
    local_out.mkdir(parents=True, exist_ok=True)

    # Build pending list
    items_pending = [x for x in json_data if x.get("status") != "completed"]
    skipped = 0
    truly_pending = []
    for item in items_pending:
        fname    = item.get("filename", f"img_{item.get('index', 0)}.png")
        out_path = local_out / fname
        if out_path.exists():
            item["status"]      = "completed"
            item["output_path"] = str(out_path)
            skipped += 1
        else:
            truly_pending.append(item)

    if skipped:
        log.warn(f"Skipped {skipped} - already on disk")

    if count_str != "ALL":
        try:
            truly_pending = truly_pending[:int(count_str)]
        except ValueError:
            pass

    total_gen = len(truly_pending)
    result = {"json": json_path.name, "generated": 0, "failed": 0,
              "uploaded": 0, "upload_failed": 0, "time_seconds": 0}

    if total_gen == 0:
        log.warn(f"'{json_path.name}' - all done, nothing to generate")
        return result

    # Generate images — SEQUENTIAL, 1 at a time, rate-limited
    log.info(f"Generating {total_gen} images | {model_name} | "
             f"{width}x{height} | 1 worker | 9 req/min limit")

    done_count  = 0
    fail_count  = 0
    start_t     = time.time()
    drive_queue = []

    for idx, item in enumerate(truly_pending, 1):
        fname    = item.get("filename", f"img_{item.get('index', 0)}.png")
        out_path = local_out / fname
        prompt   = item.get("prompt", "")
        seed     = int(item.get("seed", SDXL_DEFAULT_SEED))

        log.info(f"[{idx}/{total_gen}] Generating: {fname} "
                 f"({rate_limiter.status()})")

        try:
            # rate_limiter.wait_if_needed() is called inside generate_image_*
            img_url = generate_image_api(
                prompt, seed, model_name, api_key, width, height,
                negative_prompt=DEFAULT_NEG_PROMPT,
                num_steps=num_steps, guidance_scale=guidance)
            download_file(img_url, out_path)
            item["status"]      = "completed"
            item["output_path"] = str(out_path)
            item["done_at"]     = datetime.now().isoformat()
            drive_queue.append(out_path)
            done_count += 1
            log.ok(f"  {fname}")
        except Exception as e:
            item["status"] = "failed"
            fail_count += 1
            log.err(f"  {fname} - {str(e)[:300]}")

        # Progress
        processed = done_count + fail_count
        elapsed   = max(time.time() - start_t, 0.001)
        rate      = processed / elapsed * 60  # per minute
        remaining = total_gen - processed
        eta_s     = int(remaining / (processed / elapsed)) if processed > 0 else 0
        print(f"  Progress: {processed}/{total_gen} ({processed/total_gen*100:.0f}%) "
              f"| OK:{done_count} FAIL:{fail_count} "
              f"| {rate:.1f} img/min | ETA:{eta_s//60}m{eta_s%60}s",
              flush=True)

        # Save JSON after every image (crash-safe)
        try:
            with open(json_path, "w", encoding="utf-8") as fh:
                json.dump(json_data, fh, indent=2, ensure_ascii=False)
        except Exception:
            pass

    # Final JSON save
    try:
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(json_data, fh, indent=2, ensure_ascii=False)
        log.ok(f"JSON saved: {json_path}")
    except Exception as e:
        log.err(f"JSON save error: {e}")

    # Drive subfolder & upload
    upload_ok = 0
    upload_fail = 0

    if drive_queue or done_count > 0:
        log.info(f"Drive: creating subfolder '{subfolder_name}'...")
        try:
            sub_folder_id = create_drive_folder(
                subfolder_name, parent_folder_id, access_token)
        except Exception as e:
            log.err(f"Subfolder creation failed: {e}")
            sub_folder_id = None

        if sub_folder_id:
            log.info(f"Uploading {len(drive_queue)} images -> Drive/{subfolder_name}/")
            for fpath in drive_queue:
                try:
                    fid = upload_to_google_drive(fpath, sub_folder_id, access_token)
                    if fid:
                        upload_ok += 1
                    else:
                        upload_fail += 1
                except Exception as e:
                    log.err(f"Upload error {fpath.name}: {e}")
                    upload_fail += 1

            # Upload JSON to same subfolder
            log.info(f"Uploading {json_path.name} -> Drive/{subfolder_name}/")
            try:
                upload_to_google_drive(json_path, sub_folder_id, access_token,
                                       mime_type="application/json")
            except Exception as e:
                log.err(f"JSON upload error: {e}")

    elapsed = int(time.time() - start_t)
    result.update({
        "generated": done_count, "failed": fail_count,
        "uploaded": upload_ok, "upload_failed": upload_fail,
        "time_seconds": elapsed,
    })

    log.info(f"[{json_path.name}] Done {elapsed}s - "
             f"Gen:{done_count} Fail:{fail_count} "
             f"Up:{upload_ok} UpFail:{upload_fail}")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def run_pipeline(config):
    log.step("PIXAZO AI - HEADLESS GENERATOR v5.1")
    log.info(f"Model: {config['MODEL']} | Size: {config['WIDTH']}x{config['HEIGHT']}")
    log.info(f"Rate limit: {MAX_REQUESTS_PER_MINUTE} req/min | Workers: 1")

    # Find JSON files
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
        log.info(f"  {jf.name} -> Drive subfolder: '{jf.stem}'")

    # Auth
    log.step("Google Drive Authentication")
    access_token = get_google_access_token(
        config["GOOGLE_CLIENT_ID"],
        config["GOOGLE_CLIENT_SECRET"],
        config["GOOGLE_REFRESH_TOKEN"],
    )

    # Process each JSON
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
                "json": jf.name, "generated": 0, "failed": 0,
                "uploaded": 0, "upload_failed": 0, "error": str(e),
            })

    # Summary
    total_elapsed = int(time.time() - total_start)
    log.step("FINAL SUMMARY")

    t_gen = t_fail = t_up = t_uf = 0
    for r in all_results:
        g = r.get("generated", 0)
        f = r.get("failed", 0)
        u = r.get("uploaded", 0)
        uf = r.get("upload_failed", 0)
        t_gen += g; t_fail += f; t_up += u; t_uf += uf
        st = "OK" if f == 0 and "error" not in r else "WARN"
        print(f"  [{st}] {r['json']:30s} Gen:{g} Fail:{f} "
              f"Up:{u} UpFail:{uf}", flush=True)

    print(flush=True)
    log.info(f"TOTALS - Gen:{t_gen} Fail:{t_fail} Up:{t_up} UpFail:{t_uf}")
    log.info(f"Total time: {total_elapsed}s")
    log.info(f"Effective rate: {t_gen / max(total_elapsed/60, 0.01):.1f} img/min")

    if t_fail > 0:
        sys.exit(1)


if __name__ == "__main__":
    try:
        config = load_config()
        run_pipeline(config)
    except KeyboardInterrupt:
        log.warn("Interrupted")
        sys.exit(130)
    except Exception as e:
        log.err(f"Fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
