#!/usr/bin/env python3
"""
PIXAZO AI - HEADLESS IMAGE GENERATOR v3.0 (GitHub Actions Edition)
===================================================================
prompts/ folder-ல எந்த JSON போட்டாலும் automatically process ஆகும்.
ஒவ்வொரு JSON-க்கும் தனி subfolder create ஆகும்.

Folder Structure:
    prompts/
        cats.json       → output/cats/       → Drive: <root>/cats/
        nature.json     → output/nature/     → Drive: <root>/nature/
        portraits.json  → output/portraits/  → Drive: <root>/portraits/

Required GitHub Secrets:
    PIXAZO_API_KEY          - Pixazo API key
    GOOGLE_CLIENT_ID        - Google OAuth2 Client ID
    GOOGLE_CLIENT_SECRET    - Google OAuth2 Client Secret
    GOOGLE_REFRESH_TOKEN    - Google OAuth2 Refresh Token
    GOOGLE_DRIVE_FOLDER_ID  - Root Drive folder ID (subfolders auto-created inside)

Install:
    pip install requests google-api-python-client google-auth
"""

import argparse
import json
import os
import sys
import time
import logging
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

# ── Logging ────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("pixazo")

# ── API Endpoints ──────────────────────────────────────────────
MODEL_ENDPOINTS = {
    "flux-schnell":                "https://gateway.pixazo.ai/flux-1-schnell/v1/getData",
    "stable-diffusion":            "https://gateway.pixazo.ai/stable-diffusion/v1/sd/textToImage",
    "sdxl":                        "https://gateway.pixazo.ai/sdxl/v1/sdxl/textToImage",
    "stable-diffusion-inpainting": "https://gateway.pixazo.ai/stable-diffusion-inpainting/v1/inpainting/textToImage",
}
FLUX_SCHNELL_STEPS = 4
DEFAULT_API_KEY    = os.environ.get("PIXAZO_API_KEY", "605ef817f3db4092871ebdf6334f3c47")


# ══════════════════════════════════════════════════════════════
# IMAGE GENERATION
# ══════════════════════════════════════════════════════════════

def generate_image_api(prompt, seed, model_name, api_key, width, height):
    url = MODEL_ENDPOINTS.get(model_name)
    if not url:
        raise ValueError(f"Unknown model: {model_name}")

    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
    }
    payload = {"prompt": prompt, "seed": seed, "width": width, "height": height}
    if model_name == "flux-schnell":
        payload["num_steps"] = FLUX_SCHNELL_STEPS

    resp = requests.post(url, json=payload, headers=headers, timeout=120)
    resp.raise_for_status()
    data = resp.json()

    for key in ["output", "imageUrl", "image_url", "url", "image"]:
        if key in data and data[key]:
            return data[key]
    if "images" in data and data["images"]:
        img = data["images"][0]
        return img.get("url") or img.get("imageUrl") if isinstance(img, dict) else str(img)
    if "data" in data and data["data"]:
        item = data["data"][0]
        if isinstance(item, dict):
            return item.get("url") or item.get("imageUrl")
    return None


def download_file(url, save_path):
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    Path(save_path).write_bytes(r.content)


# ══════════════════════════════════════════════════════════════
# GOOGLE DRIVE — SERVICE + FOLDER HELPERS
# ══════════════════════════════════════════════════════════════

def build_drive_service():
    """Env secrets-ல இருந்து Drive service build பண்ணும்."""
    client_id     = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        raise EnvironmentError(
            "Missing Google secrets! Set: GOOGLE_CLIENT_ID, "
            "GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN"
        )

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/drive.file"],
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def get_or_create_drive_folder(service, folder_name: str, parent_id: str = None) -> str:
    """
    Drive-ல folder_name இருந்தா அதோட ID return பண்ணும்.
    இல்லன்னா புது folder create பண்ணி ID return பண்ணும்.
    """
    query_parts = [
        f"name = '{folder_name}'",
        "mimeType = 'application/vnd.google-apps.folder'",
        "trashed = false",
    ]
    if parent_id:
        query_parts.append(f"'{parent_id}' in parents")

    results = service.files().list(
        q=" and ".join(query_parts),
        fields="files(id, name)",
        spaces="drive",
    ).execute()

    files = results.get("files", [])
    if files:
        log.info(f"  📂 Existing Drive folder: '{folder_name}'")
        return files[0]["id"]

    metadata = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        metadata["parents"] = [parent_id]

    folder = service.files().create(body=metadata, fields="id").execute()
    log.info(f"  📁 Created Drive folder: '{folder_name}'")
    return folder["id"]


def upload_to_drive(service, file_path: Path, folder_id: str) -> str:
    metadata = {"name": file_path.name, "parents": [folder_id]}
    media    = MediaFileUpload(str(file_path), mimetype="image/png", resumable=False)
    try:
        f = service.files().create(
            body=metadata, media_body=media, fields="id"
        ).execute()
        log.info(f"    ✅ {file_path.name}")
        return f["id"]
    except HttpError as e:
        log.error(f"    ❌ {file_path.name} → {e}")
        raise


def upload_subfolder_to_drive(service, local_dir: Path,
                               subfolder_name: str, root_folder_id: str) -> int:
    """
    local_dir images → Drive root_folder / subfolder_name /
    Returns number of successfully uploaded files.
    """
    log.info(f"  📤 Drive upload: '{subfolder_name}'...")
    drive_subfolder_id = get_or_create_drive_folder(
        service, subfolder_name, parent_id=root_folder_id
    )

    images = sorted(list(local_dir.glob("*.png")) + list(local_dir.glob("*.jpg")))
    if not images:
        log.warning(f"  ⚠️  No images found in {local_dir}")
        return 0

    success = 0
    for img_path in images:
        try:
            upload_to_drive(service, img_path, drive_subfolder_id)
            success += 1
        except Exception:
            pass

    log.info(f"  '{subfolder_name}' done: {success}/{len(images)} uploaded.")
    return success


# ══════════════════════════════════════════════════════════════
# SINGLE JSON PROCESSING
# ══════════════════════════════════════════════════════════════

def process_json_file(json_file: Path, base_output_dir: Path,
                      model_name, api_key, width, height, workers, count):
    """
    ஒரு JSON file process பண்ணும்.
    Output → base_output_dir / json_file.stem /
    Returns (done, fail, out_dir)
    """
    subfolder_name = json_file.stem          # "cats.json" → "cats"
    out_dir        = base_output_dir / subfolder_name
    out_dir.mkdir(parents=True, exist_ok=True)

    log.info("=" * 55)
    log.info(f"📄 {json_file.name}  →  output/{subfolder_name}/")
    log.info("=" * 55)

    raw = json_file.read_text(encoding="utf-8")
    raw = raw.replace('"status":\n  }',  '"status": "pending"\n  }')
    raw = raw.replace('"status": \n  }', '"status": "pending"\n  }')

    try:
        json_data = json.loads(raw)
    except json.JSONDecodeError as e:
        log.error(f"JSON parse error in {json_file.name}: {e}")
        return 0, 0, out_dir

    log.info(f"Total items: {len(json_data)}")

    pending = [x for x in json_data if x.get("status") != "completed"]

    skipped = 0
    truly_pending = []
    for item in pending:
        fname = item.get("filename", f"img_{item.get('index', 0)}.png")
        if (out_dir / fname).exists():
            item["status"]      = "completed"
            item["output_path"] = str(out_dir / fname)
            skipped += 1
        else:
            truly_pending.append(item)

    if skipped:
        log.info(f"Skipped {skipped} (already on disk).")

    pending = truly_pending
    if count and str(count).upper() != "ALL":
        try:
            pending = pending[:int(count)]
        except ValueError:
            pass

    if not pending:
        log.info("✅ All images already done.")
        return 0, 0, out_dir

    log.info(f"Generating {len(pending)} | model={model_name} | workers={workers}")

    done    = [0]
    fail    = [0]
    lock    = threading.Lock()
    start_t = time.time()

    def gen_one(item):
        fname    = item.get("filename", f"img_{item.get('index', 0)}.png")
        out_path = out_dir / fname
        prompt   = item.get("prompt", "")
        seed     = item.get("seed", 42)
        try:
            img_url = generate_image_api(prompt, seed, model_name, api_key, width, height)
            if not img_url:
                raise ValueError("Empty API response")
            download_file(img_url, out_path)
            with lock:
                item["status"]      = "completed"
                item["output_path"] = str(out_path)
                item["done_at"]     = datetime.now().isoformat()
            log.info(f"  ✅ {fname}")
            return "ok"
        except Exception as e:
            with lock:
                item["status"] = "failed"
            log.error(f"  ❌ {fname} → {str(e)[:100]}")
            return "fail"

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(gen_one, item): item for item in pending}
        for future in as_completed(futures):
            result = future.result()
            with lock:
                if result == "ok":     done[0] += 1
                elif result == "fail": fail[0] += 1
            processed = done[0] + fail[0]
            log.info(f"  Progress: {processed}/{len(pending)} | ✅{done[0]} ❌{fail[0]}")

    elapsed = int(time.time() - start_t)
    log.info(f"Done: ✅{done[0]}  ❌{fail[0]}  ⏱{elapsed}s")

    try:
        json_file.write_text(
            json.dumps(json_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        log.info(f"JSON status saved → {json_file.name}")
    except Exception as e:
        log.warning(f"JSON save error: {e}")

    return done[0], fail[0], out_dir


# ══════════════════════════════════════════════════════════════
# MAIN — SCAN prompts/ FOLDER
# ══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Pixazo AI — Scan prompts/ folder & generate per-JSON subfolders"
    )
    parser.add_argument("--prompts-dir", default="prompts",
                        help="Folder with prompt JSON files (default: ./prompts)")
    parser.add_argument("--output-dir",  default="output",
                        help="Base output folder (default: ./output)")
    parser.add_argument("--model",       default="flux-schnell",
                        choices=list(MODEL_ENDPOINTS.keys()))
    parser.add_argument("--width",       type=int, default=1024)
    parser.add_argument("--height",      type=int, default=1024)
    parser.add_argument("--workers",     type=int, default=3)
    parser.add_argument("--count",       default="ALL",
                        help="Max images per JSON (or ALL)")
    parser.add_argument("--drive-folder-id", default=None,
                        help="Root Google Drive folder ID")
    args = parser.parse_args()

    prompts_dir    = Path(args.prompts_dir)
    base_out_dir   = Path(args.output_dir)
    root_folder_id = args.drive_folder_id or os.environ.get("GOOGLE_DRIVE_FOLDER_ID")

    # ── Validate ───────────────────────────────────────────────
    if not prompts_dir.exists():
        log.error(f"Prompts folder not found: '{prompts_dir}/'")
        log.error("Repo-ல 'prompts/' folder create பண்ணி JSON files போடுங்க.")
        sys.exit(1)

    json_files = sorted(prompts_dir.glob("*.json"))
    if not json_files:
        log.error(f"No .json files found in '{prompts_dir}/'")
        sys.exit(1)

    log.info(f"🔍 Found {len(json_files)} JSON file(s) in '{prompts_dir}/':")
    for jf in json_files:
        log.info(f"   • {jf.name}  →  output/{jf.stem}/")

    # ── Drive service (one-time init) ──────────────────────────
    drive_service = None
    drive_enabled = bool(root_folder_id)
    if drive_enabled:
        try:
            drive_service = build_drive_service()
            log.info(f"✅ Google Drive ready. Root: {root_folder_id}")
        except EnvironmentError as e:
            log.warning(f"⚠️  Drive disabled — {e}")
            drive_enabled = False

    # ── Process each JSON ──────────────────────────────────────
    grand_done = 0
    grand_fail = 0
    summary    = []

    for json_file in json_files:
        done, fail, out_dir = process_json_file(
            json_file       = json_file,
            base_output_dir = base_out_dir,
            model_name      = args.model,
            api_key         = DEFAULT_API_KEY,
            width           = args.width,
            height          = args.height,
            workers         = args.workers,
            count           = args.count,
        )
        grand_done += done
        grand_fail += fail

        # Upload this batch to its own Drive subfolder
        uploaded = 0
        if drive_enabled and drive_service:
            uploaded = upload_subfolder_to_drive(
                service        = drive_service,
                local_dir      = out_dir,
                subfolder_name = json_file.stem,
                root_folder_id = root_folder_id,
            )

        summary.append((json_file.name, done, fail, uploaded))

    # ── Final Summary ──────────────────────────────────────────
    log.info("")
    log.info("╔══════════════════════════════════════════════════╗")
    log.info("║              FINAL SUMMARY                      ║")
    log.info("╠══════════════════════════════════════════════════╣")
    for (jname, d, f, u) in summary:
        icon = "✅" if f == 0 else "⚠️"
        log.info(f"║ {icon} {jname:<22} gen:{d:>3}  fail:{f:>2}  drive:{u:>3} ║")
    log.info("╠══════════════════════════════════════════════════╣")
    log.info(f"║  TOTAL  generated:{grand_done:<5}  failed:{grand_fail:<16}║")
    log.info("╚══════════════════════════════════════════════════╝")

    if grand_fail > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
