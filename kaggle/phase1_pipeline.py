"""
UltraPNG — Phase 1 Kaggle Pipeline
FLUX.2-Klein-4B → BiRefNet_HR BG Remove → PNG + WebP → Google Drive → Google Sheets → Trigger Phase 2
"""
import os, sys, json, time, gc, re, io, shutil, subprocess
from pathlib import Path
from datetime import datetime
import requests as req

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

HF_CACHE = Path("/kaggle/working/hf_cache")
HF_CACHE.mkdir(parents=True, exist_ok=True)
os.environ["HF_HOME"]               = str(HF_CACHE)
os.environ["HUGGINGFACE_HUB_CACHE"] = str(HF_CACHE)
os.environ["TRANSFORMERS_CACHE"]    = str(HF_CACHE)

# ── Model IDs ─────────────────────────────────────────────────
FLUX_MODEL = "black-forest-labs/FLUX.2-klein-4B"
RMBG_MODEL = "ZhengPeng7/BiRefNet_HR"

# ── Config (injected by inject_creds.py) ──────────────────────
GOOGLE_CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN", "")
GITHUB_TOKEN_REPO2   = os.environ.get("GITHUB_TOKEN_REPO2", "")
GITHUB_REPO2         = os.environ.get("GITHUB_REPO2", "")
GITHUB_REPO1         = os.environ.get("GITHUB_REPO1", "")
GITHUB_TOKEN_REPO1   = os.environ.get("GITHUB_TOKEN_REPO1", "")
GOOGLE_SHEETS_ID     = os.environ.get("GOOGLE_SHEETS_ID", "")
DRIVE_ROOT_FOLDER_ID = os.environ.get("DRIVE_ROOT_FOLDER_ID", "")
START_INDEX          = int(os.environ.get("START_INDEX", "0"))
END_INDEX            = int(os.environ.get("END_INDEX", "200"))

WATERMARK_TEXT = "www.ultrapng.com"
SITE_NAME      = "UltraPNG"

WORK        = Path("/kaggle/working")
GENERATED   = WORK / "generated"
TRANSPARENT = WORK / "transparent"
CHECKPOINT  = WORK / "checkpoints"
REPO1_DIR   = WORK / "repo1"

for _d in [GENERATED, TRANSPARENT, CHECKPOINT]:
    _d.mkdir(parents=True, exist_ok=True)

# ── Install dependencies ───────────────────────────────────────
print("Installing dependencies...")
_PKGS = [
    "git+https://github.com/huggingface/diffusers.git",
    "transformers>=4.47.0", "accelerate>=0.28.0", "sentencepiece",
    "huggingface_hub>=0.23.0", "Pillow>=10.0", "numpy",
    "onnxruntime-gpu", "torchvision", "piexif", "opencv-python-headless",
]
for _pkg in _PKGS:
    r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", _pkg],
                       capture_output=True, text=True)
    print(f"  {'OK' if r.returncode == 0 else 'WARN'} {_pkg}")

import torch
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ── Logging ───────────────────────────────────────────────────
_LOG = []

def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    _LOG.append(line)

# ── Utilities ─────────────────────────────────────────────────
def free_gpu():
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()

def get_safe_device():
    """Returns 'cuda' only if GPU CUDA capability >= 7.0, else 'cpu'."""
    if not torch.cuda.is_available():
        return "cpu"
    major, minor = torch.cuda.get_device_capability(0)
    if major < 7:
        log(f"  WARNING: GPU sm_{major}{minor} not supported by PyTorch (need sm_70+). Using CPU.")
        return "cpu"
    log(f"  GPU sm_{major}{minor} detected — using CUDA ✓")
    return "cuda"

def slugify(s, max_len=60):
    s = re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")
    if len(s) > max_len:
        cut = s[:max_len]
        idx = cut.rfind("-")
        s = cut[:idx] if idx > max_len // 2 else cut
    return s or "untitled"

def delete_hf_cache_for(keywords):
    for sub in HF_CACHE.iterdir():
        if sub.is_dir() and any(k in sub.name.lower() for k in keywords):
            shutil.rmtree(str(sub), ignore_errors=True)
            log(f"  Deleted HF cache: {sub.name}")

# ── Google OAuth ──────────────────────────────────────────────
_token_cache = {"value": None, "expires": 0}

def get_token():
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
        raise RuntimeError(f"OAuth failed: {d}")
    _token_cache.update({"value": d["access_token"], "expires": time.time() + 3200})
    return _token_cache["value"]

# ── Google Drive ───────────────────────────────────────────────
def drive_headers():
    return {"Authorization": f"Bearer {get_token()}"}

def drive_get_or_create_folder(name, parent_id):
    h = drive_headers()
    q = (f"name='{name}' and mimeType='application/vnd.google-apps.folder'"
         f" and '{parent_id}' in parents and trashed=false")
    r = req.get("https://www.googleapis.com/drive/v3/files",
                headers=h, params={"q": q, "fields": "files(id)"}, timeout=30)
    files = r.json().get("files", [])
    if files:
        return files[0]["id"]
    r = req.post("https://www.googleapis.com/drive/v3/files",
                 headers={**h, "Content-Type": "application/json"},
                 json={"name": name, "mimeType": "application/vnd.google-apps.folder",
                       "parents": [parent_id]}, timeout=30)
    return r.json()["id"]

def drive_list_subfolders(parent_id):
    """Return {name: id} dict for all subfolders in one API call."""
    h, result, page_token = drive_headers(), {}, None
    while True:
        params = {
            "q": (f"'{parent_id}' in parents and "
                  "mimeType='application/vnd.google-apps.folder' and trashed=false"),
            "fields": "files(id,name),nextPageToken",
            "pageSize": 1000,
        }
        if page_token:
            params["pageToken"] = page_token
        data = req.get("https://www.googleapis.com/drive/v3/files",
                       headers=h, params=params, timeout=30).json()
        for f in data.get("files", []):
            result[f["name"]] = f["id"]
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return result

def drive_upload(folder_id, name, data_bytes, mime="image/png", retries=3):
    h = drive_headers()
    for attempt in range(1, retries + 1):
        try:
            boundary = "UltraPNGBoundary"
            meta = json.dumps({"name": name, "parents": [folder_id]})
            body = (
                f"--{boundary}\r\nContent-Type: application/json\r\n\r\n{meta}\r\n"
                f"--{boundary}\r\nContent-Type: {mime}\r\n\r\n"
            ).encode() + data_bytes + f"\r\n--{boundary}--".encode()
            r = req.post(
                "https://www.googleapis.com/upload/drive/v3/files"
                "?uploadType=multipart&fields=id,name",
                headers={**h, "Content-Type": f'multipart/related; boundary="{boundary}"'},
                data=body, timeout=120,
            )
            if r.ok:
                return r.json()
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:120]}")
        except Exception as e:
            if attempt < retries:
                time.sleep(5 * attempt)
            else:
                raise

def drive_share(file_id):
    try:
        req.post(
            f"https://www.googleapis.com/drive/v3/files/{file_id}/permissions",
            headers={**drive_headers(), "Content-Type": "application/json"},
            json={"role": "reader", "type": "anyone"}, timeout=30,
        )
    except Exception:
        pass

def preview_url(fid, size=800):
    return f"https://lh3.googleusercontent.com/d/{fid}=s{size}"

def download_url(fid):
    return f"https://drive.usercontent.google.com/download?id={fid}&export=download&authuser=0"

# ── Folder Cache (built once at upload start) ──────────────────
class FolderCache:
    def __init__(self, png_root_id, webp_root_id):
        self.png_root  = png_root_id
        self.webp_root = webp_root_id
        log("  Loading folder cache...")
        self._png  = drive_list_subfolders(png_root_id)
        self._webp = drive_list_subfolders(webp_root_id)
        log(f"  Folder cache: {len(self._png)} PNG cats, {len(self._webp)} WebP cats")

    def get_png_folder(self, category):
        if category not in self._png:
            self._png[category] = drive_get_or_create_folder(category, self.png_root)
        return self._png[category]

    def get_webp_folder(self, category):
        if category not in self._webp:
            self._webp[category] = drive_get_or_create_folder(category, self.webp_root)
        return self._webp[category]

# ── Google Sheets ──────────────────────────────────────────────
SHEET_RANGE = "Sheet1"
SHEET_COLS  = ["filename", "subject_name", "category",
               "png_file_id", "webp_file_id",
               "png_url", "webp_url",
               "seo_done", "status", "date_added"]

def sheets_get_all_filenames():
    """One API call — returns set of all logged filenames."""
    url = (f"https://sheets.googleapis.com/v4/spreadsheets/{GOOGLE_SHEETS_ID}"
           f"/values/{SHEET_RANGE}!A:A")
    r = req.get(url, headers={"Authorization": f"Bearer {get_token()}"}, timeout=30)
    if not r.ok:
        log(f"  Sheets read failed: {r.status_code}")
        return set()
    values = r.json().get("values", [])
    return {row[0] for row in values[1:] if row}

def sheets_ensure_header():
    url = (f"https://sheets.googleapis.com/v4/spreadsheets/{GOOGLE_SHEETS_ID}"
           f"/values/{SHEET_RANGE}!A1:J1")
    r = req.get(url, headers={"Authorization": f"Bearer {get_token()}"}, timeout=30)
    existing = r.json().get("values", [[]])[0] if r.ok else []
    if existing == SHEET_COLS:
        return
    req.put(
        f"https://sheets.googleapis.com/v4/spreadsheets/{GOOGLE_SHEETS_ID}"
        f"/values/{SHEET_RANGE}!A1:J1",
        headers={"Authorization": f"Bearer {get_token()}",
                 "Content-Type": "application/json"},
        params={"valueInputOption": "USER_ENTERED"},
        json={"values": [SHEET_COLS]},
        timeout=30,
    )

def sheets_append_batch(rows, chunk_size=50):
    """Append rows in batches — minimal API calls."""
    url = (f"https://sheets.googleapis.com/v4/spreadsheets/{GOOGLE_SHEETS_ID}"
           f"/values/{SHEET_RANGE}:append")
    h   = {"Authorization": f"Bearer {get_token()}", "Content-Type": "application/json"}
    params = {"valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"}
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i:i + chunk_size]
        r = req.post(url, headers=h, params=params,
                     json={"values": chunk}, timeout=30)
        if not r.ok:
            log(f"  Sheets append error: {r.status_code} {r.text[:100]}")
        time.sleep(0.3)

# ── Checkpoint ─────────────────────────────────────────────────
def save_ckpt(name, data):
    p = CHECKPOINT / f"{name}.json"
    tmp = str(p) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, str(p))

def load_ckpt(name):
    p = CHECKPOINT / f"{name}.json"
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return None

# ── Category Prompt Enhancers ──────────────────────────────────
_ENHANCERS = {
    "indian_foods":    ", appetizing food styling, steam visible, glistening surface",
    "world_foods":     ", appetizing food styling, steam visible, glistening sauce",
    "fruits":          ", natural skin texture, juice droplets",
    "vegetables":      ", natural surface texture, fresh harvest quality",
    "flowers":         ", petal vein detail, natural color saturation",
    "jewellery":       ", gem facet reflections, gold metal mirror finish",
    "vehicles":        ", automotive paint reflection, chrome detail",
    "animals":         ", fur and feather strand detail, catchlight in eyes",
    "poultry_animals": ", fur and feather strand detail, catchlight in eyes",
    "raw_meat":        ", fresh meat texture, glistening moist surface",
    "beverages":       ", condensation droplets, liquid transparency",
    "footwear":        ", leather grain, stitching detail",
    "clothing":        ", fabric weave, embroidery thread detail",
    "indian_dress":    ", fabric weave, embroidery thread detail",
}

def enhance_prompt(prompt, category):
    cat = (category or "").lower()
    for key, extra in _ENHANCERS.items():
        if key in cat:
            return prompt + extra
    return prompt

# ── WebP Preview Builder ───────────────────────────────────────
def make_webp(png_path):
    """Returns WebP bytes: checkered BG + diagonal watermark + footer bar."""
    import piexif
    with Image.open(png_path).convert("RGBA") as rgba:
        w, h = rgba.size
        if max(w, h) > 800:
            scale = 800 / max(w, h)
            rgba  = rgba.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        w, h = rgba.size

        # Checkered background
        bg  = Image.new("RGB", (w, h), (255, 255, 255))
        drw = ImageDraw.Draw(bg)
        for ry in range(0, h, 20):
            for cx in range(0, w, 20):
                if (ry // 20 + cx // 20) % 2:
                    drw.rectangle([cx, ry, cx + 20, ry + 20], fill=(232, 232, 232))
        bg.paste(rgba.convert("RGB"), mask=rgba.split()[3])

        # Diagonal watermark
        try:
            fnt = ImageFont.truetype(
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 13)
        except Exception:
            fnt = ImageFont.load_default()

        wm = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        wd = ImageDraw.Draw(wm)
        for ry in range(-h, h + 110, 110):
            for cx in range(-w, w + 110, 110):
                wd.text((cx, ry), WATERMARK_TEXT, fill=(0, 0, 0, 42), font=fnt)
        wm = wm.rotate(-30, expand=False)

        bg_rgba = bg.convert("RGBA")
        bg_rgba.alpha_composite(wm)
        bg = bg_rgba.convert("RGB")

        # Footer bar
        try:
            fnt2 = ImageFont.truetype(
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 15)
        except Exception:
            fnt2 = fnt
        fd = ImageDraw.Draw(bg)
        fd.rectangle([0, h - 36, w, h], fill=(13, 13, 20))
        fd.text((w // 2 - 72, h - 26), WATERMARK_TEXT, fill=(245, 166, 35), font=fnt2)

        buf = io.BytesIO()
        bg.save(buf, "WEBP", quality=82, method=4)
        return buf.getvalue(), w, h

# ── Prompts Loader ─────────────────────────────────────────────
def load_prompts():
    log("Loading prompts from Repo1...")
    if not REPO1_DIR.exists():
        url = f"https://x-access-token:{GITHUB_TOKEN_REPO1}@github.com/{GITHUB_REPO1}.git"
        subprocess.run(["git", "clone", "--depth", "1", url, str(REPO1_DIR)],
                       capture_output=True)
    sys.path.insert(0, str(REPO1_DIR))
    try:
        from prompts.prompt_engine import load_all_prompts
        prompts = load_all_prompts(str(REPO1_DIR / "prompts" / "splits"))
        log(f"  Loaded {len(prompts)} prompts")
        return prompts
    except Exception as e:
        log(f"  Prompt load failed: {e}")
        return []

# ── Phase 1: FLUX Image Generation ────────────────────────────
def phase1_generate(batch, skip_set):
    ckpt = load_ckpt("p1_generated")
    if ckpt:
        log(f"  Checkpoint: {len(ckpt)} generated (skip FLUX)")
        return ckpt

    log("=" * 56)
    log("PHASE 1: FLUX.2-Klein-4B — Image Generation")
    log(f"  Loading from HuggingFace: {FLUX_MODEL}")
    log("=" * 56)

    from diffusers import Flux2KleinPipeline

    log(f"  Loading: {FLUX_MODEL}")
    log("  (First run: downloads ~8GB — ~5 min)")
    pipe = Flux2KleinPipeline.from_pretrained(
        FLUX_MODEL,
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
            out = GENERATED / fname
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
            log(f"  [{i+1}/{len(batch)}] OK {fname} | {item.get('category', '')} | ETA {eta:.0f}min")

        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            log(f"  OOM: {fname}")
        except Exception as e:
            log(f"  FAIL {fname}: {e}")

    log("\n  Deleting FLUX.2 -> freeing VRAM + disk cache...")
    del pipe
    free_gpu()

    # Delete FLUX HF cache to free disk
    for _cache_sub in HF_CACHE.iterdir():
        if _cache_sub.is_dir():
            _name = _cache_sub.name.lower()
            if "flux" in _name or "black-forest" in _name:
                shutil.rmtree(str(_cache_sub), ignore_errors=True)
                log(f"  Deleted FLUX cache: {_cache_sub.name}")
    _used = sum(f.stat().st_size for f in HF_CACHE.rglob("*") if f.is_file()) / 1e9
    log(f"  HF cache after cleanup: {_used:.1f}GB")

    save_ckpt("p1_generated", generated)
    log(f"PHASE 1 DONE — Generated: {len(generated)} | Skipped: {skipped}\n")
    return generated

# ── Phase 2: Background Removal ────────────────────────────────
def phase2_bg_remove(generated):
    ckpt = load_ckpt("p2_transparent")
    if ckpt:
        log(f"  Checkpoint: {len(ckpt)} transparent (skip RMBG)")
        return ckpt

    log("=" * 56)
    log("PHASE 2: BiRefNet_HR — Background Removal (FP16 GPU)")
    log("=" * 56)

    from torchvision import transforms
    from transformers import AutoModelForImageSegmentation

    model  = AutoModelForImageSegmentation.from_pretrained(
        RMBG_MODEL, trust_remote_code=True, cache_dir=str(HF_CACHE))
    device = get_safe_device()
    torch.set_float32_matmul_precision("high")
    if device == "cuda":
        model = model.to(device).eval().half()
    else:
        model = model.to(device).eval()  # float32 on CPU (.half() not supported)

    transform = transforms.Compose([
        transforms.Resize((2048, 2048)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    def remove_bg(pil_img):
        ow, oh = pil_img.size
        inp = transform(pil_img.convert("RGB")).unsqueeze(0).to(device)
        if device == "cuda":
            inp = inp.half()
        with torch.no_grad():
            pred = model(inp)[-1].sigmoid().cpu()[0].squeeze()
        mask = transforms.ToPILImage()(pred).resize((ow, oh), Image.LANCZOS)
        out  = pil_img.convert("RGBA")
        out.putalpha(mask)
        return out

    result, t0 = [], time.time()

    for i, g in enumerate(generated):
        src = Path(g["path"])
        dst = TRANSPARENT / src.name
        try:
            if not dst.exists():
                img = Image.open(str(src)).convert("RGB")
                remove_bg(img).save(str(dst), "PNG", compress_level=0)
            result.append({**g, "transparent_path": str(dst)})
            if (i + 1) % 20 == 0:
                rate = (i + 1) / max(time.time() - t0, 1)
                log(f"  RMBG: {i+1}/{len(generated)} | {rate:.2f}/s")
        except Exception as e:
            log(f"  RMBG FAIL {src.name}: {e}")

    log(f"\n  Unloading BiRefNet → freeing VRAM...")
    del model, transform
    free_gpu()
    delete_hf_cache_for(["birefnet", "rmbg", "briaai"])

    # Remove generated (no longer needed, transparent/ has final PNGs)
    shutil.rmtree(str(GENERATED), ignore_errors=True)
    GENERATED.mkdir()

    save_ckpt("p2_transparent", result)
    log(f"PHASE 2 DONE | Transparent: {len(result)}")
    return result

# ── Phase 3: Drive Upload + Sheets Log ────────────────────────
def phase3_upload_and_log(images):
    ckpt = load_ckpt("p3_uploaded")
    if ckpt:
        log(f"  Checkpoint: {len(ckpt)} uploaded (skip upload)")
        return ckpt

    log("=" * 56)
    log("PHASE 3: Google Drive Upload + Sheets Log")
    log("=" * 56)

    # Get or create root folders (PNG and WebP under DRIVE_ROOT_FOLDER_ID)
    png_root  = drive_get_or_create_folder("PNG",  DRIVE_ROOT_FOLDER_ID)
    webp_root = drive_get_or_create_folder("WebP", DRIVE_ROOT_FOLDER_ID)
    folders   = FolderCache(png_root, webp_root)

    today   = datetime.now().strftime("%Y-%m-%d")
    rows    = []  # For batch Sheets append
    result  = []
    t0      = time.time()

    for i, img in enumerate(images):
        path = Path(img["transparent_path"])
        item = img["item"]
        cat  = item.get("category", "general")

        # Refresh token every 50 uploads
        if i > 0 and i % 50 == 0:
            get_token()

        try:
            png_bytes  = path.read_bytes()
            webp_bytes, pw, ph = make_webp(path)

            png_folder  = folders.get_png_folder(cat)
            webp_folder = folders.get_webp_folder(cat)

            pr = drive_upload(png_folder,  path.name,        png_bytes,  "image/png")
            wr = drive_upload(webp_folder, path.stem + ".webp", webp_bytes, "image/webp")

            drive_share(pr["id"])
            drive_share(wr["id"])

            subject = (item.get("subject_name") or
                       cat.replace("-", " ").replace("_", " ").title())

            rows.append([
                path.name,
                subject,
                cat,
                pr["id"],
                wr["id"],
                download_url(pr["id"]),
                preview_url(wr["id"], 800),
                "FALSE",
                "ACTIVE",
                today,
            ])

            result.append({**img, "png_file_id": pr["id"], "webp_file_id": wr["id"]})

            # Batch append every 50 rows
            if len(rows) >= 50:
                sheets_append_batch(rows)
                rows.clear()
                log(f"  Uploaded+logged: {i+1}/{len(images)}")

            time.sleep(0.05)

        except Exception as e:
            log(f"  Upload FAIL {path.name}: {e}")

    # Append remaining rows
    if rows:
        sheets_append_batch(rows)

    # Delete transparent images (uploaded to Drive)
    shutil.rmtree(str(TRANSPARENT), ignore_errors=True)
    TRANSPARENT.mkdir()

    save_ckpt("p3_uploaded", result)
    log(f"PHASE 3 DONE | Uploaded: {len(result)} in {(time.time()-t0)/60:.1f}m")
    return result

# ── Trigger Phase 2 GitHub Actions ────────────────────────────
def trigger_phase2():
    if not GITHUB_TOKEN_REPO1 or not GITHUB_REPO1:
        log("  Phase 2 trigger skipped (no token/repo)")
        return
    r = req.post(
        f"https://api.github.com/repos/{GITHUB_REPO1}/dispatches",
        headers={
            "Authorization": f"token {GITHUB_TOKEN_REPO1}",
            "Accept": "application/vnd.github.v3+json",
        },
        json={"event_type": "phase1_complete"},
        timeout=30,
    )
    if r.status_code == 204:
        log("  Phase 2 triggered via repository_dispatch ✓")
    else:
        log(f"  Phase 2 trigger failed: {r.status_code}")

# ── Main ───────────────────────────────────────────────────────
def main():
    log("=" * 56)
    log("UltraPNG Phase 1 Pipeline — Start")
    log(f"Batch: {START_INDEX} → {END_INDEX} ({END_INDEX - START_INDEX} images)")
    log("=" * 56)

    sheets_ensure_header()

    # Load prompts and slice batch
    all_prompts = load_prompts()
    if not all_prompts:
        log("FATAL: No prompts loaded")
        sys.exit(1)

    total = len(all_prompts)
    start = min(START_INDEX, total)
    end   = min(END_INDEX,   total)
    batch = all_prompts[start:end]
    log(f"Prompts: {total} total | This batch: {len(batch)}")

    # Build skip-set from Sheets (ONE API call)
    log("Building skip-set from Sheets...")
    skip_set = sheets_get_all_filenames()
    log(f"  Skip-set: {len(skip_set)} already processed")

    # Run pipeline
    generated   = phase1_generate(batch,     skip_set)
    transparent = phase2_bg_remove(generated)
    phase3_upload_and_log(transparent)

    # Trigger Phase 2
    trigger_phase2()

    log("=" * 56)
    log("Phase 1 COMPLETE ✓")
    log("=" * 56)

main()
