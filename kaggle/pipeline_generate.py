"""
╔══════════════════════════════════════════════════════════════╗
║  UltraPNG — GENERATE Pipeline  (Trigger 1)                  ║
╠══════════════════════════════════════════════════════════════╣
║  Phase 1 → FLUX.2-Klein-4B   Generate 1024×1024 PNG        ║
║  Phase 2 → BiRefNet_HR       Background removal (FP16)      ║
║  Phase 3 → Watermark + WebP  Preview (800px)                ║
║           → Google Drive     PNG + WebP upload              ║
║           → manifest.csv     Append rows (Drive root)       ║
╠══════════════════════════════════════════════════════════════╣
║  200 images/day  |  Kaggle GPU  |  Daily auto               ║
║  NO JSON — NO Repo2 — NO SEO                                ║
╚══════════════════════════════════════════════════════════════╝
"""

import os, sys, json, time, gc, io, csv, shutil, subprocess
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

# ── Model IDs ─────────────────────────────────────────────────
FLUX_HF_ID = "black-forest-labs/FLUX.2-klein-4B"
RMBG_HF_ID = "ZhengPeng7/BiRefNet_HR"

# ── Install deps ──────────────────────────────────────────────
print("=" * 56)
print("Installing dependencies...")
PKGS = [
    "git+https://github.com/huggingface/diffusers.git",
    "transformers>=4.47.0", "accelerate>=0.28.0",
    "huggingface_hub>=0.23.0", "Pillow>=10.0",
    "numpy", "requests", "torchvision", "piexif",
]
r = subprocess.run(
    [sys.executable, "-m", "pip", "install", "-q", "--no-warn-conflicts"] + PKGS,
    capture_output=True, text=True)
print(f"  pip: {'OK' if r.returncode == 0 else 'WARN'}")
print("Done!\n")

import torch
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import requests as req

# ── Paths ─────────────────────────────────────────────────────
WORKING_DIR     = Path("/kaggle/working")
GENERATED_DIR   = WORKING_DIR / "generated"
TRANSPARENT_DIR = WORKING_DIR / "transparent"
PROJECT_DIR     = WORKING_DIR / "project"
CHECKPOINT_DIR  = WORKING_DIR / "checkpoints"

for d in [GENERATED_DIR, TRANSPARENT_DIR, CHECKPOINT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Config ────────────────────────────────────────────────────
GOOGLE_CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN", "")
GITHUB_REPO1         = os.environ.get("GITHUB_REPO", "")
GITHUB_TOKEN_REPO1   = os.environ.get("GITHUB_TOKEN_REPO1", "")
START_INDEX          = int(float(os.environ.get("START_INDEX", "0")))
END_INDEX            = int(float(os.environ.get("END_INDEX", "200")))

SITE_NAME       = "UltraPNG"
WATERMARK_TEXT  = "www.ultrapng.com"
WEBP_SIZE       = 800
MANIFEST_NAME   = "ultrapng_manifest.csv"
MANIFEST_COLS   = ["filename", "category", "subcategory", "subject_name",
                   "png_id", "webp_id", "png_url", "webp_url", "date_added"]

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

def save_checkpoint(name, data):
    p = CHECKPOINT_DIR / f"{name}.json"
    p.write_text(json.dumps(data, ensure_ascii=False), "utf-8")

def load_checkpoint(name):
    p = CHECKPOINT_DIR / f"{name}.json"
    if p.exists():
        log(f"  Checkpoint '{name}' loaded ({p.stat().st_size//1024}KB)")
        return json.loads(p.read_text("utf-8"))
    return None

# ── Subject name from filename fallback ──────────────────────
def filename_to_subject(stem):
    """img_000042 → subcategory-based OR 'white_table-brown' → 'White Table Brown'"""
    s = stem.replace("img_", "").replace("-", " ").replace("_", " ")
    # Remove numeric suffix like 000042
    parts = s.split()
    clean = [p for p in parts if not p.isdigit()]
    return " ".join(clean).title() if clean else stem.title()

# ── Category enhancers ────────────────────────────────────────
CATEGORY_ENHANCERS = {
    "indian_foods":  ", steaming hot presentation, glistening sauce",
    "food_indian":   ", steaming hot presentation, glistening sauce",
    "world_foods":   ", restaurant quality plating, steam rising",
    "food_world":    ", restaurant quality plating, steam rising",
    "fruits":        ", natural skin texture, fresh juice droplets",
    "vegetables":    ", fresh harvest quality, natural surface texture",
    "flowers":       ", visible petal vein detail, rich color saturation",
    "jewellery":     ", gem facet reflections, mirror-polished finish",
    "vehicles":      ", automotive paint reflection, chrome highlights",
    "animals":       ", fur strand detail, natural catchlight in eyes",
    "poultry":       ", feather strand detail, catchlight in eyes",
    "cool_drinks":   ", condensation droplets, liquid transparency",
    "beverages":     ", condensation droplets, liquid transparency",
    "footwear":      ", leather grain texture, fine stitching detail",
    "shoes":         ", leather grain texture, fine stitching detail",
    "indian_dress":  ", fabric weave texture, embroidery thread detail",
    "clothing":      ", fabric weave texture",
    "jewellery_models": ", professional portrait lighting",
    "office_models": ", professional portrait lighting",
}

def enhance_prompt(raw_prompt, category):
    cat = (category or "").lower()
    for key, extra in CATEGORY_ENHANCERS.items():
        if key in cat:
            return raw_prompt + extra
    return raw_prompt

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

def drive_find_file(token, name, parent=None):
    """Find file by name. Returns file_id or None."""
    h = {"Authorization": f"Bearer {token}"}
    q = f"name='{name}' and trashed=false"
    if parent:
        q += f" and '{parent}' in parents"
    r = req.get("https://www.googleapis.com/drive/v3/files",
                headers=h, params={"q": q, "fields": "files(id,name)"}, timeout=30)
    files = r.json().get("files", [])
    return files[0]["id"] if files else None

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

def drive_upload(token, name, data, mime, folder_id=None, file_id=None, retries=3):
    """Upload or update a file. If file_id given → update (overwrite)."""
    for attempt in range(1, retries + 1):
        try:
            h = {"Authorization": f"Bearer {token}"}
            if file_id:
                # Update existing file content
                r = req.patch(
                    f"https://www.googleapis.com/upload/drive/v3/files/{file_id}"
                    f"?uploadType=media",
                    headers={**h, "Content-Type": mime},
                    data=data, timeout=120)
                if r.ok:
                    return {"id": file_id}
                raise Exception(f"HTTP {r.status_code}: {r.text[:100]}")
            else:
                # Create new file
                metadata = json.dumps({"name": name,
                                       **({"parents": [folder_id]} if folder_id else {})})
                b    = "UltraPNGBoundary"
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

def preview_url(fid, size=800):
    return f"https://drive.google.com/thumbnail?id={fid}&sz=w{size}"

def download_url(fid):
    return f"https://drive.google.com/uc?export=download&id={fid}"

# ══════════════════════════════════════════════════════════════
# MANIFEST CSV — Drive root
# ══════════════════════════════════════════════════════════════
def manifest_download(token):
    """Download manifest.csv from Drive. Returns (csv_text, file_id) or ('', None)."""
    fid = drive_find_file(token, MANIFEST_NAME)
    if not fid:
        log("  manifest.csv not found on Drive — will create fresh")
        return "", None
    r = req.get(
        f"https://www.googleapis.com/drive/v3/files/{fid}",
        headers={"Authorization": f"Bearer {token}"},
        params={"alt": "media"}, timeout=60)
    if r.ok:
        log(f"  manifest.csv downloaded ({len(r.content)//1024}KB, id={fid})")
        return r.text, fid
    log(f"  manifest.csv download failed: {r.status_code}")
    return "", None

def manifest_parse(csv_text):
    """Parse manifest CSV → set of already-done filenames."""
    done = set()
    if not csv_text.strip():
        return done
    import io as _io
    reader = csv.DictReader(_io.StringIO(csv_text))
    for row in reader:
        fname = row.get("filename", "").strip()
        if fname:
            done.add(fname)
    log(f"  manifest.csv: {len(done)} already processed")
    return done

def manifest_upload(token, existing_text, new_rows, manifest_id):
    """Append new_rows to existing CSV and upload back to Drive."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=MANIFEST_COLS)

    if not existing_text.strip():
        writer.writeheader()
    else:
        buf.write(existing_text.rstrip("\n") + "\n")

    for row in new_rows:
        writer.writerow(row)

    csv_bytes = buf.getvalue().encode("utf-8")
    result = drive_upload(token, MANIFEST_NAME, csv_bytes, "text/csv",
                          file_id=manifest_id)
    if not manifest_id:
        # Newly created — share it
        drive_share(token, result["id"])
        return result["id"]
    return manifest_id

# ══════════════════════════════════════════════════════════════
# WATERMARK
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

def make_webp(png_path):
    """Transparent PNG → watermarked WebP preview (800px). Returns bytes, w, h."""
    with Image.open(png_path).convert("RGBA") as img:
        w, h = img.size
        if max(w, h) > WEBP_SIZE:
            ratio = WEBP_SIZE / max(w, h)
            img   = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        w, h = img.size

        # Checkerboard BG
        bg  = Image.new("RGB", (w, h), (255, 255, 255))
        drw = ImageDraw.Draw(bg)
        for ry in range(0, h, 20):
            for cx in range(0, w, 20):
                if (ry // 20 + cx // 20) % 2 == 1:
                    drw.rectangle([cx, ry, cx + 20, ry + 20], fill=(232, 232, 232))
        bg.paste(img.convert("RGB"), mask=img.split()[3])

        # Diagonal watermark
        wm_rot, fnt = _watermark_layer(w, h)
        bg_rgba = bg.convert("RGBA")
        bg_rgba.alpha_composite(wm_rot)
        bg = bg_rgba.convert("RGB")

        # Bottom banner
        try:
            fnt2 = ImageFont.truetype(
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 15)
        except Exception:
            fnt2 = fnt
        drw2 = ImageDraw.Draw(bg)
        drw2.rectangle([0, h - 36, w, h], fill=(13, 13, 20))
        drw2.text((w // 2 - 72, h - 26), WATERMARK_TEXT, fill=(245, 166, 35), font=fnt2)

        buf = io.BytesIO()
        bg.save(buf, "WEBP", quality=82, method=4)
    return buf.getvalue(), w, h

# ══════════════════════════════════════════════════════════════
# LOAD PROMPTS — build filename→item lookup
# ══════════════════════════════════════════════════════════════
def load_prompt_lookup():
    """Returns dict: {filename → item} for subject_name lookup."""
    log("Loading prompt splits for subject_name lookup...")
    splits_dir = PROJECT_DIR / "prompts" / "splits"
    index_file = splits_dir / "index.json"

    if index_file.exists():
        idx   = json.loads(index_file.read_text("utf-8"))
        files = [splits_dir / f for f in idx["files"]]
    else:
        files = sorted(f for f in splits_dir.glob("*.json") if f.name != "index.json")

    if not files:
        log("  FATAL: No prompt splits found!")
        return {}

    lookup = {}
    total  = 0
    for fpath in files:
        try:
            items = json.loads(fpath.read_text("utf-8"))
            for item in items:
                lookup[item["filename"]] = item
            total += len(items)
        except Exception as e:
            log(f"  Warn {fpath.name}: {e}")

    log(f"  Prompt lookup: {total} items from {len(files)} files")
    return lookup

def get_subject_name(fname, prompt_lookup):
    """Dual approach: prompt splits first, filename fallback."""
    item = prompt_lookup.get(fname)
    if item and item.get("subject_name"):
        return item["subject_name"]
    # Fallback: derive from filename
    stem = Path(fname).stem   # "img_000042" or custom name
    return filename_to_subject(stem)

def get_item_meta(fname, prompt_lookup):
    """Get category, subcategory, subject_name from lookup or defaults."""
    item = prompt_lookup.get(fname, {})
    return {
        "category":    item.get("category", "general"),
        "subcategory": item.get("subcategory", "general"),
        "subject_name": get_subject_name(fname, prompt_lookup),
        "prompt":      item.get("prompt", ""),
    }

# ══════════════════════════════════════════════════════════════
# PHASE 1 — FLUX.2-Klein-4B
# ══════════════════════════════════════════════════════════════
def phase1_generate(batch, skip_set, prompt_lookup):
    ckpt = load_checkpoint("phase1_generated")
    if ckpt:
        return ckpt

    log("=" * 56)
    log(f"PHASE 1: FLUX.2-Klein-4B — {FLUX_HF_ID}")
    log("=" * 56)

    from diffusers import Flux2KleinPipeline

    pipe = Flux2KleinPipeline.from_pretrained(FLUX_HF_ID, torch_dtype=torch.bfloat16)
    pipe.enable_model_cpu_offload(gpu_id=0)
    pipe.set_progress_bar_config(disable=True)
    log(f"  FLUX loaded | Batch: {len(batch)} | Skip: {len(skip_set)}\n")

    generated, skipped, t0 = [], 0, time.time()

    for i, item in enumerate(batch):
        fname = item["filename"]

        if fname in skip_set:
            skipped += 1
            continue

        try:
            cat = item.get("category", "general")
            sub = item.get("subcategory", "general")
            out_dir = GENERATED_DIR / cat / sub
            out_dir.mkdir(parents=True, exist_ok=True)
            out = out_dir / fname

            if out.exists():
                generated.append({"path": str(out), "item": item})
                continue

            gen    = torch.Generator("cpu").manual_seed(item["seed"])
            prompt = enhance_prompt(item["prompt"], cat)
            img    = pipe(prompt=prompt, num_inference_steps=4, guidance_scale=1.0,
                          height=1024, width=1024, generator=gen).images[0]

            # Blank check → retry
            arr = np.array(img)
            if arr.std() < 5 or (arr < 250).sum() < int(arr.shape[0] * arr.shape[1] * 0.003):
                log(f"  Retry (blank): {fname}")
                gen2 = torch.Generator("cpu").manual_seed(item["seed"] + 99)
                img  = pipe(prompt=prompt, num_inference_steps=4, guidance_scale=1.0,
                            height=1024, width=1024, generator=gen2).images[0]

            img.save(str(out), "PNG", compress_level=0)
            generated.append({"path": str(out), "item": item})

            done = len(generated)
            rate = done / max(time.time() - t0, 1)
            eta  = (len(batch) - skipped - i - 1) / max(rate, 0.01) / 60
            log(f"  [{i+1}/{len(batch)}] {fname} | ETA {eta:.0f}min")

        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            log(f"  OOM: {fname}")
        except Exception as e:
            log(f"  FAIL {fname}: {e}")

    log(f"\n  Deleting FLUX cache...")
    del pipe
    free_memory()
    for c in HF_CACHE.iterdir():
        if c.is_dir() and any(k in c.name.lower() for k in ["flux", "black-forest"]):
            shutil.rmtree(str(c), ignore_errors=True)

    save_checkpoint("phase1_generated", generated)
    log(f"PHASE 1 DONE — Generated: {len(generated)} | Skipped: {skipped}\n")
    return generated

# ══════════════════════════════════════════════════════════════
# PHASE 2 — BiRefNet_HR Background Removal
# ══════════════════════════════════════════════════════════════
def phase2_bg_remove(generated):
    ckpt = load_checkpoint("phase2_transparent")
    if ckpt:
        return ckpt

    log("=" * 56)
    log(f"PHASE 2: BiRefNet_HR — Background Removal")
    log("=" * 56)

    if not generated:
        return []

    from torchvision import transforms
    from transformers import AutoModelForImageSegmentation

    model = AutoModelForImageSegmentation.from_pretrained(
        RMBG_HF_ID, trust_remote_code=True, cache_dir=str(HF_CACHE))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch.set_float32_matmul_precision("high")
    model  = model.to(device).eval().half()
    log(f"  BiRefNet loaded on {device.upper()} FP16 | {len(generated)} images\n")

    transform_img = transforms.Compose([
        transforms.Resize((2048, 2048)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    def remove_bg(pil_img):
        ow, oh = pil_img.size
        inp    = transform_img(pil_img.convert("RGB")).unsqueeze(0).to(device).half()
        with torch.no_grad():
            preds = model(inp)[-1].sigmoid().cpu()
        mask   = transforms.ToPILImage()(preds[0].squeeze()).resize((ow, oh), Image.LANCZOS)
        result = pil_img.convert("RGBA")
        result.putalpha(mask)
        return result

    results, t0 = [], time.time()

    for i, gen_item in enumerate(generated):
        path = Path(gen_item["path"])
        item = gen_item["item"]
        try:
            out_dir = TRANSPARENT_DIR / item["category"] / item.get("subcategory", "general")
            out_dir.mkdir(parents=True, exist_ok=True)
            out = out_dir / path.name

            if out.exists():
                results.append({**gen_item, "transparent_path": str(out)})
                continue

            img    = Image.open(str(path)).convert("RGB")
            result = remove_bg(img)
            result.save(str(out), "PNG", compress_level=0)
            results.append({**gen_item, "transparent_path": str(out)})

            if (i + 1) % 20 == 0:
                log(f"  BG done: {i+1}/{len(generated)} | {(i+1)/(time.time()-t0):.2f}/s")

        except Exception as e:
            log(f"  RMBG FAIL {path.name}: {e}")

    log(f"\n  Deleting BiRefNet cache...")
    del model
    free_memory()
    for c in HF_CACHE.iterdir():
        if c.is_dir() and any(k in c.name.lower() for k in ["birefnet", "zhengpeng", "rmbg"]):
            shutil.rmtree(str(c), ignore_errors=True)
    shutil.rmtree(str(GENERATED_DIR), ignore_errors=True)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    save_checkpoint("phase2_transparent", results)
    log(f"PHASE 2 DONE — Transparent PNGs: {len(results)}\n")
    return results

# ══════════════════════════════════════════════════════════════
# PHASE 3 — WebP + Upload to Drive + manifest.csv
# ══════════════════════════════════════════════════════════════
def phase3_upload(transparent_list, prompt_lookup):
    ckpt = load_checkpoint("phase3_uploaded")
    if ckpt:
        return ckpt

    log("=" * 56)
    log("PHASE 3: WebP + Google Drive Upload + manifest.csv")
    log("=" * 56)

    if not transparent_list:
        return []

    token = get_drive_token()

    # Download existing manifest
    manifest_text, manifest_id = manifest_download(token)
    already_done = manifest_parse(manifest_text)

    # Drive folder structure: ultrapng_png/category/subcategory
    png_root = drive_folder(token, "ultrapng_png")
    wbp_root = drive_folder(token, "ultrapng_webp")
    log(f"  Drive folders ready | Uploading {len(transparent_list)} items\n")

    fcache    = {}     # key → (png_folder_id, webp_folder_id)
    new_rows  = []
    uploaded  = []
    t0        = time.time()

    for i, trans_item in enumerate(transparent_list):
        if i > 0 and i % 50 == 0:
            token = get_drive_token()

        path = Path(trans_item["transparent_path"])
        item = trans_item["item"]
        fname = path.name

        if fname in already_done:
            log(f"  SKIP (manifest): {fname}")
            continue

        try:
            cat = item.get("category", "general")
            sub = item.get("subcategory", "general")
            key = f"{cat}/{sub}"

            if key not in fcache:
                pc = drive_folder(token, cat, png_root)
                ps = drive_folder(token, sub, pc)
                wc = drive_folder(token, cat, wbp_root)
                ws = drive_folder(token, sub, wc)
                fcache[key] = (ps, ws)

            png_fid, wbp_fid = fcache[key]

            # Upload transparent PNG
            png_bytes = path.read_bytes()
            pr = drive_upload(token, fname, png_bytes, "image/png", folder_id=png_fid)
            drive_share(token, pr["id"])

            # Make WebP + upload
            webp_bytes, _, _ = make_webp(path)
            wr = drive_upload(token, path.stem + ".webp", webp_bytes,
                              "image/webp", folder_id=wbp_fid)
            drive_share(token, wr["id"])

            meta = get_item_meta(fname, prompt_lookup)
            row  = {
                "filename":     fname,
                "category":     meta["category"],
                "subcategory":  meta["subcategory"],
                "subject_name": meta["subject_name"],
                "png_id":       pr["id"],
                "webp_id":      wr["id"],
                "png_url":      download_url(pr["id"]),
                "webp_url":     preview_url(wr["id"], WEBP_SIZE),
                "date_added":   datetime.now().strftime("%Y-%m-%d"),
            }
            new_rows.append(row)
            uploaded.append(row)

            rate = (i + 1) / max(time.time() - t0, 1)
            eta  = (len(transparent_list) - i - 1) / max(rate, 0.01) / 60
            log(f"  [{i+1}/{len(transparent_list)}] {fname} | {meta['subject_name']} | ETA {eta:.0f}min")

        except Exception as e:
            log(f"  Upload FAIL {fname}: {e}")

    # Update manifest.csv on Drive
    if new_rows:
        log(f"\n  Updating manifest.csv (+{len(new_rows)} rows)...")
        manifest_upload(token, manifest_text, new_rows, manifest_id)
        log(f"  manifest.csv updated on Drive ✅")

    # Cleanup
    shutil.rmtree(str(TRANSPARENT_DIR), ignore_errors=True)
    TRANSPARENT_DIR.mkdir(parents=True, exist_ok=True)

    save_checkpoint("phase3_uploaded", uploaded)
    log(f"\nPHASE 3 DONE — Uploaded: {len(uploaded)} | Time: {(time.time()-t0)/60:.0f}min\n")
    return uploaded

# ══════════════════════════════════════════════════════════════
# SAVE LOGS → REPO1
# ══════════════════════════════════════════════════════════════
def save_logs(stats):
    log("Saving logs to Repo1...")
    try:
        repo1_dir = WORKING_DIR / "repo1"
        if repo1_dir.exists():
            shutil.rmtree(str(repo1_dir))
        url = f"https://x-access-token:{GITHUB_TOKEN_REPO1}@github.com/{GITHUB_REPO1}.git"
        subprocess.run(["git", "clone", "--depth=1", url, str(repo1_dir)],
                       check=True, capture_output=True)

        logs_dir = repo1_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d_%H%M")
        (logs_dir / f"gen_{date_str}.txt").write_text("\n".join(_LOG_LINES), "utf-8")
        (logs_dir / f"gen_{date_str}_stats.json").write_text(
            json.dumps(stats, ensure_ascii=False, indent=2), "utf-8")

        # Update batch tracker
        tracker = repo1_dir / "progress" / "batch_tracker.txt"
        tracker.parent.mkdir(parents=True, exist_ok=True)
        tracker.write_text(str(END_INDEX), "utf-8")

        env = {**os.environ,
               "GIT_AUTHOR_NAME": "UltraPNG Bot",
               "GIT_AUTHOR_EMAIL": "bot@ultrapng.com",
               "GIT_COMMITTER_NAME": "UltraPNG Bot",
               "GIT_COMMITTER_EMAIL": "bot@ultrapng.com"}
        subprocess.run(["git", "-C", str(repo1_dir), "add", "-A"],
                       check=True, env=env, capture_output=True)
        r = subprocess.run(["git", "-C", str(repo1_dir), "diff", "--cached", "--quiet"])
        if r.returncode != 0:
            subprocess.run(
                ["git", "-C", str(repo1_dir), "commit", "-m",
                 f"Generate {date_str}: +{stats.get('uploaded', 0)} images"],
                check=True, env=env, capture_output=True)
            subprocess.run(["git", "-C", str(repo1_dir), "push"],
                           check=True, env=env, capture_output=True)
        log("  Logs pushed ✅")
    except Exception as e:
        log(f"  Log push failed (non-fatal): {e}")

# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
def main():
    t0    = time.time()
    stats = {"status": "RUNNING", "generated": 0, "transparent": 0, "uploaded": 0}

    try:
        try:
            p = torch.cuda.get_device_properties(0)
            print(f"\n{'='*56}")
            print(f"  UltraPNG GENERATE Pipeline")
            print(f"  FLUX.2-Klein → BiRefNet → WebP → Drive")
            print(f"  Batch: {START_INDEX} → {END_INDEX} | GPU: {p.name} {p.total_memory/1e9:.0f}GB")
            print(f"{'='*56}\n")
        except Exception:
            pass

        # ── Clone project repo if not already present ─────────────
        if GITHUB_REPO1 and not PROJECT_DIR.exists():
            log("Cloning project repo for prompts...")
            repo_url = f"https://github.com/{GITHUB_REPO1}.git"
            if GITHUB_TOKEN_REPO1:
                repo_url = f"https://x-access-token:{GITHUB_TOKEN_REPO1}@github.com/{GITHUB_REPO1}.git"
            subprocess.run(["git", "clone", "--depth", "1", repo_url, str(PROJECT_DIR)],
                           capture_output=True, check=True)
            log("  Repo cloned successfully")

        # Load prompt lookup for subject_name
        prompt_lookup = load_prompt_lookup()

        # Load prompts for batch
        splits_dir = PROJECT_DIR / "prompts" / "splits"
        index_file = splits_dir / "index.json"
        if index_file.exists():
            idx   = json.loads(index_file.read_text("utf-8"))
            files = [splits_dir / f for f in idx["files"]]
        else:
            files = sorted(f for f in splits_dir.glob("*.json") if f.name != "index.json")

        if not files:
            raise Exception("No prompt splits found!")

        all_prompts = []
        for fpath in files:
            all_prompts.extend(json.loads(fpath.read_text("utf-8")))

        log(f"Total prompts: {len(all_prompts)} | Batch: {START_INDEX}→{END_INDEX}")

        batch = all_prompts[START_INDEX:END_INDEX]
        if not batch:
            log("Batch is empty — all done!")
            return

        # Download manifest to build skip set
        token = get_drive_token()
        manifest_text, _ = manifest_download(token)
        skip_set = manifest_parse(manifest_text)
        log(f"Batch: {len(batch)} prompts | Skip: {len(skip_set)} already done\n")

        # Phase 1: Generate
        generated = phase1_generate(batch, skip_set, prompt_lookup)
        stats["generated"] = len(generated)
        if not generated:
            log("No new images generated.")
            return

        # Phase 2: Background remove
        transparent = phase2_bg_remove(generated)
        stats["transparent"] = len(transparent)
        if not transparent:
            log("Background removal produced no results.")
            return

        # Phase 3: Upload to Drive + update manifest
        uploaded = phase3_upload(transparent, prompt_lookup)
        stats["uploaded"] = len(uploaded)

        # Clear checkpoints on success
        for ck in CHECKPOINT_DIR.glob("*.json"):
            ck.unlink()

        hrs = (time.time() - t0) / 3600
        stats.update({"duration": f"{hrs:.1f}h", "status": "SUCCESS"})
        print(f"\n{'='*56}")
        print(f"  GENERATE DONE in {hrs:.1f}h")
        print(f"  Generated:{len(generated)} Transparent:{len(transparent)} Uploaded:{len(uploaded)}")
        print(f"{'='*56}")

    except Exception as e:
        stats.update({"duration": f"{(time.time()-t0)/3600:.1f}h",
                      "status": f"FAILED: {str(e)[:80]}"})
        log(f"FATAL: {e}")
        raise
    finally:
        save_logs(stats)

if __name__ == "__main__":
    main()
