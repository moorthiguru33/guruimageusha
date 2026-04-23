import base64
import io
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


ULTRADATA_XLSX  = "ultradata.xlsx"
WATERMARK_TEXT  = "www.ultrapng.com"
INSTANT_CAP     = 2000

# ── Gemma 3 1B replaces Florence-2 ─────────────────────────────────────────
GEMMA_MODEL_ID = "google/gemma-3-1b-it"

MAX_RUN_SECONDS = 17_400   # 4h50m
_RUN_START      = time.time()

# ── Global model handles (loaded ONCE per run, reused for all items) ───────
_gemma_model     = None
_gemma_tokenizer = None


def _load_gemma_model():
    """Load Gemma 3 1B once at startup. ~30s on first run (cached)."""
    global _gemma_model, _gemma_tokenizer
    if _gemma_model is not None:
        return
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    print(f"  [Gemma] Loading {GEMMA_MODEL_ID} ...", flush=True)

    hf_token = os.environ.get("HF_TOKEN")
    _gemma_tokenizer = AutoTokenizer.from_pretrained(
        GEMMA_MODEL_ID,
        token=hf_token
    )
    _gemma_model = AutoModelForCausalLM.from_pretrained(
        GEMMA_MODEL_ID,
        torch_dtype=torch.float32,
        device_map="cpu",
        token=hf_token
    )
    _gemma_model.eval()
    print("  [Gemma] Model ready ✓", flush=True)


# ══════════════════════════════════════════════════════════════
# GOOGLE DRIVE helpers  (unchanged)
# ══════════════════════════════════════════════════════════════

_drive_token_cache: Dict[str, Any] = {"value": None, "expires": 0}

def _drive_token() -> str:
    import requests
    if _drive_token_cache["value"] and time.time() < _drive_token_cache["expires"]:
        return _drive_token_cache["value"]
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id":     os.environ.get("GOOGLE_CLIENT_ID", ""),
        "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
        "refresh_token": os.environ.get("GOOGLE_REFRESH_TOKEN", ""),
        "grant_type":    "refresh_token",
    }, timeout=30)
    d = r.json()
    if "access_token" not in d:
        raise RuntimeError(f"Drive token error: {d}")
    _drive_token_cache.update({"value": d["access_token"],
                                "expires": time.time() + 3200})
    return _drive_token_cache["value"]

def _dh(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}

_drive_folder_cache: Dict[str, str] = {}

def _drive_folder_id(token: str, name: str, parent_id: Optional[str] = None) -> str:
    import requests
    cache_key = f"{parent_id or 'root'}::{name}"
    if cache_key in _drive_folder_cache:
        return _drive_folder_cache[cache_key]
    q = (f"name='{name}' and mimeType='application/vnd.google-apps.folder'"
         f" and trashed=false")
    if parent_id:
        q += f" and '{parent_id}' in parents"
    r = requests.get("https://www.googleapis.com/drive/v3/files",
                     headers=_dh(token),
                     params={"q": q, "fields": "files(id,name)", "pageSize": 1},
                     timeout=30)
    r.raise_for_status()
    files = r.json().get("files", [])
    if files:
        fid = files[0]["id"]
    else:
        body: Dict[str, Any] = {"name": name,
                                 "mimeType": "application/vnd.google-apps.folder"}
        if parent_id:
            body["parents"] = [parent_id]
        r2 = requests.post("https://www.googleapis.com/drive/v3/files",
                            headers={**_dh(token), "Content-Type": "application/json"},
                            json=body, timeout=30)
        r2.raise_for_status()
        fid = r2.json()["id"]
    _drive_folder_cache[cache_key] = fid
    return fid

def _drive_list_folder(token: str, folder_id: str,
                       mime_filter: Optional[str] = None) -> List[Dict]:
    import requests
    q = f"'{folder_id}' in parents and trashed=false"
    if mime_filter:
        q += f" and mimeType='{mime_filter}'"
    results, page_token = [], None
    while True:
        params: Dict[str, Any] = {
            "q": q, "pageSize": 1000,
            "fields": "nextPageToken,files(id,name,mimeType,size)",
        }
        if page_token:
            params["pageToken"] = page_token
        r = requests.get("https://www.googleapis.com/drive/v3/files",
                          headers=_dh(token), params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        results.extend(data.get("files", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return results

def _drive_list_pngs(token: str, folder_id: str) -> List[Dict]:
    import requests
    q = (f"'{folder_id}' in parents and trashed=false and "
         "(mimeType='image/png' or name contains '.png')")
    results, page_token = [], None
    while True:
        params: Dict[str, Any] = {
            "q": q, "pageSize": 1000,
            "fields": "nextPageToken,files(id,name,mimeType)",
        }
        if page_token:
            params["pageToken"] = page_token
        r = requests.get("https://www.googleapis.com/drive/v3/files",
                          headers=_dh(token), params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        results.extend(data.get("files", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return results

def _drive_download(token: str, fid: str) -> bytes:
    import requests
    r = requests.get(f"https://www.googleapis.com/drive/v3/files/{fid}",
                     headers=_dh(token), params={"alt": "media"}, timeout=180)
    r.raise_for_status()
    return r.content

# ══════════════════════════════════════════════════════════════
# GITHUB API helpers
# ══════════════════════════════════════════════════════════════

def _gh_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"}

def _gh_get_sha(token: str, owner: str, repo: str,
                path: str, branch: str = "main") -> Optional[str]:
    import requests
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    r = requests.get(url, headers=_gh_headers(token),
                     params={"ref": branch}, timeout=30)
    if r.status_code == 200:
        return r.json().get("sha")
    return None

def _gh_upload_file(token: str, owner: str, repo: str,
                    path: str, content_bytes: bytes,
                    message: str, branch: str = "main") -> Dict:
    import requests
    url  = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    sha  = _gh_get_sha(token, owner, repo, path, branch)
    body: Dict[str, Any] = {
        "message": message,
        "content": base64.b64encode(content_bytes).decode(),
        "branch":  branch,
    }
    if sha:
        body["sha"] = sha
    for attempt in range(1, 4):
        r = requests.put(url, headers={**_gh_headers(token),
                                        "Content-Type": "application/json"},
                          json=body, timeout=90)
        if r.ok:
            return r.json()
        if attempt < 3:
            time.sleep(5 * attempt)
        else:
            r.raise_for_status()
    return {}

def _jsdelivr_url(owner: str, repo: str, branch: str, path: str) -> str:
    return f"https://cdn.jsdelivr.net/gh/{owner}/{repo}@{branch}/{path}"


# ══════════════════════════════════════════════════════════════
# WEBP PREVIEW GENERATOR
# ══════════════════════════════════════════════════════════════

WEBP_MAX_SIDE  = 800
WEBP_MAX_BYTES = 80 * 1024

def _make_webp_preview(png_bytes: bytes, watermark: str) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    def _font(size: int):
        for fp in [
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        ]:
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                pass
        return ImageFont.load_default()

    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    w, h = img.size
    if max(w, h) > WEBP_MAX_SIDE:
        scale = WEBP_MAX_SIDE / max(w, h)
        img   = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    w, h = img.size
    CELL = 16
    bg   = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(bg)
    for gy in range(0, h, CELL):
        for gx in range(0, w, CELL):
            if (gx // CELL + gy // CELL) % 2 == 0:
                draw.rectangle([gx, gy, gx + CELL - 1, gy + CELL - 1],
                                fill=(204, 204, 204))
    bg.paste(img, mask=img.split()[3])
    wm_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    wm_draw  = ImageDraw.Draw(wm_layer)
    wm_font  = _font(max(11, w // 30))
    step_x, step_y = max(80, w // 4), max(40, h // 5)
    for oy in range(-h, h * 2, step_y):
        for ox in range(-w, w * 2, step_x):
            wm_draw.text((ox, oy), watermark, font=wm_font,
                          fill=(200, 200, 200, 80))
    bg = bg.convert("RGBA")
    bg.alpha_composite(wm_layer)
    bg = bg.convert("RGB")
    FOOTER_H = max(18, h // 18)
    canvas   = Image.new("RGB", (w, h + FOOTER_H), (40, 40, 40))
    canvas.paste(bg, (0, 0))
    ft_draw  = ImageDraw.Draw(canvas)
    ft_font  = _font(max(9, FOOTER_H - 4))
    ft_draw.rectangle([0, h, w, h + FOOTER_H], fill=(40, 40, 40))
    ft_draw.text((4, h + 2), watermark, font=ft_font, fill=(220, 220, 220))
    buf = io.BytesIO()
    for quality in [85, 70, 55, 40, 25, 10]:
        buf.seek(0); buf.truncate()
        canvas.save(buf, "WEBP", quality=quality, method=6)
        if buf.tell() <= WEBP_MAX_BYTES:
            break
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════
# ULTRADATA XLSX helpers
# ══════════════════════════════════════════════════════════════

def _append_ultradata_rows(xlsx_path: Path, rows: List[Dict]) -> int:
    import openpyxl
    if not rows:
        return 0
    wb = openpyxl.load_workbook(str(xlsx_path))
    ws = wb.active
    HEADERS = [
        "date_added", "subject_name", "category", "subcategory",
        "filename", "png_file_id", "webp_file_id",
        "download_url", "preview_url", "seo_status",
    ]
    if ws.max_row == 0 or ws.cell(row=1, column=1).value is None:
        ws.append(HEADERS)
    else:
        existing_hdr = [ws.cell(row=1, column=c).value
                        for c in range(1, ws.max_column + 1)]
        for col_name in HEADERS:
            if col_name not in existing_hdr:
                ws.cell(row=1, column=ws.max_column + 1, value=col_name)
                existing_hdr.append(col_name)
        HEADERS = [ws.cell(row=1, column=c).value
                   for c in range(1, ws.max_column + 1)]
    for row in rows:
        ws.append([row.get(h, "") for h in HEADERS])
    wb.save(str(xlsx_path))
    return len(rows)


# ══════════════════════════════════════════════════════════════
# DRIVE PNG LIBRARY SCANNER
# ══════════════════════════════════════════════════════════════

def _collect_all_pngs_from_drive(folder_name: str) -> List[Dict]:
    print(f"  Scanning Drive folder '{folder_name}' for PNGs ...")
    token   = _drive_token()
    root_id = _drive_folder_id(token, folder_name)
    print(f"  Root folder ID: {root_id}")
    all_pngs: List[Dict] = []
    queue: List[Tuple]   = []
    top_subs = _drive_list_folder(
        token, root_id, mime_filter="application/vnd.google-apps.folder")
    print(f"  Top-level subfolders: {len(top_subs)}")
    for sf in top_subs:
        queue.append((sf["id"], sf["name"], sf["name"], sf["name"]))
    for f in _drive_list_pngs(token, root_id):
        all_pngs.append({
            "fid": f["id"], "name": f["name"],
            "stem": Path(f["name"]).stem,
            "subfolder_name": "uncategorised",
            "top_category": "uncategorised", "folder_path": "",
        })
    visited: set = set()
    while queue:
        folder_id, folder_name_, top_cat, path_str = queue.pop(0)
        if folder_id in visited:
            continue
        visited.add(folder_id)
        token = _drive_token()
        pngs  = _drive_list_pngs(token, folder_id)
        if pngs:
            print(f"    [{path_str}]: {len(pngs)} PNG(s)")
        for f in pngs:
            all_pngs.append({
                "fid": f["id"], "name": f["name"],
                "stem": Path(f["name"]).stem,
                "subfolder_name": folder_name_,
                "top_category": top_cat, "folder_path": path_str,
            })
        nested = _drive_list_folder(
            token, folder_id, mime_filter="application/vnd.google-apps.folder")
        for sf in nested:
            if sf["id"] not in visited:
                queue.append((sf["id"], sf["name"], top_cat,
                               f"{path_str}/{sf['name']}"))
    print(f"  Total PNGs found in Drive: {len(all_pngs)}")
    return all_pngs


def process_drive_png_library(repo2_dir: Path, cfg: "Repo2Config") -> int:
    needed  = ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
               "GOOGLE_REFRESH_TOKEN", "GH_TOKEN", "GH_OWNER"]
    missing = [k for k in needed if not os.environ.get(k, "").strip()]
    if missing:
        print(f"  ⚠  Skipping Drive scan — missing env vars: {', '.join(missing)}")
        return 0
    if os.environ.get("SCAN_DRIVE", "true").lower() not in ("true", "1", "yes"):
        print("  SCAN_DRIVE=false — skipping Drive PNG library scan")
        return 0
    folder_name = os.environ.get("PNG_LIBRARY_FOLDER", "png_library_images").strip()
    gh_token    = os.environ.get("GH_TOKEN", "").strip()
    gh_owner    = os.environ.get("GH_OWNER", "").strip()
    prev_repo   = os.environ.get("PREVIEW_REPO",   "guruimageusha").strip()
    prev_branch = os.environ.get("PREVIEW_BRANCH", "main").strip()
    prev_folder = os.environ.get("PREVIEW_FOLDER", "preview_webp").strip()
    watermark   = os.environ.get("WATERMARK_TEXT", "www.ultrapng.com").strip()
    today_str   = datetime.utcnow().strftime("%Y-%m-%d")
    xlsx_path   = repo2_dir / ULTRADATA_XLSX
    if not xlsx_path.exists():
        print(f"  ⚠  {ULTRADATA_XLSX} not found — skipping Drive scan")
        return 0
    import openpyxl
    wb_check   = openpyxl.load_workbook(str(xlsx_path), read_only=True)
    ws_check   = wb_check.active
    header_row = [ws_check.cell(row=1, column=c).value
                  for c in range(1, ws_check.max_column + 1)]
    try:
        fn_col = header_row.index("filename") + 1
    except ValueError:
        print("  ⚠  'filename' column not found in ultradata.xlsx — skipping")
        return 0
    existing_filenames: set = set()
    for row in ws_check.iter_rows(min_row=2, values_only=True):
        val = row[fn_col - 1]
        if val:
            existing_filenames.add(str(val).strip())
    wb_check.close()
    print(f"  Existing UltraData entries: {len(existing_filenames)}")
    try:
        all_pngs = _collect_all_pngs_from_drive(folder_name)
    except Exception as exc:
        print(f"  ⚠  Drive scan failed: {exc}")
        return 0
    new_rows = []
    token    = _drive_token()
    for p in all_pngs:
        stem     = p["stem"]
        png_name = p["name"]
        if png_name in existing_filenames or stem in existing_filenames:
            continue
        subject_raw = re.sub(r"\s+", " ",
                             re.sub(r"[_\-]+", " ", stem).strip())
        cat    = p["top_category"].replace("_", " ").title()
        subcat = p["subfolder_name"].replace("_", " ").title()
        fid    = p["fid"]
        dl_url = f"https://drive.google.com/uc?export=download&id={fid}"
        webp_fid = ""
        prev_url = ""
        try:
            png_bytes  = _drive_download(token, fid)
            webp_bytes = _make_webp_preview(png_bytes, watermark)
            webp_path_in_repo = f"{prev_folder}/{stem}.webp"
            res = _gh_upload_file(gh_token, gh_owner, prev_repo,
                                   webp_path_in_repo, webp_bytes,
                                   f"preview: add {stem}.webp",
                                   branch=prev_branch)
            if res:
                prev_url = _jsdelivr_url(gh_owner, prev_repo,
                                          prev_branch, webp_path_in_repo)
        except Exception as e:
            print(f"    ⚠  WEBP gen failed for {png_name}: {e}")
        new_rows.append({
            "date_added":   today_str,
            "subject_name": subject_raw.title(),
            "category":     cat,
            "subcategory":  subcat,
            "filename":     png_name,
            "png_file_id":  fid,
            "webp_file_id": webp_fid,
            "download_url": dl_url,
            "preview_url":  prev_url,
            "seo_status":   "",
        })
    if not new_rows:
        print("  ✅  No new PNGs to add from Drive scan.")
        return 0
    print(f"  ➕  Adding {len(new_rows)} new rows to ultradata.xlsx ...")
    _push_xlsx_rows_via_api(
        cfg, new_rows,
        commit_msg=f"ultradata: +{len(new_rows)} from Drive png_library [{today_str}]",
    )
    return len(new_rows)


# ══════════════════════════════════════════════════════════════
# UTILITIES
# ══════════════════════════════════════════════════════════════

def _word_count(s: str) -> int:
    return len([w for w in re.split(r"\s+", (s or "").strip()) if w])

def _today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


# ══════════════════════════════════════════════════════════════
# GEMMA 3 1B SEO GENERATOR (text-only, from file name)
# ══════════════════════════════════════════════════════════════

FILENAME_NOISE = re.compile(
    r"\b(hd|png|img|image|photo|pic|transparent|bg|nobg|free|dl|download"
    r"|clipart|vector|stock|high|quality|resolution|res|ultra|4k|full)\b",
    re.I,
)

def _clean_subject(raw: str) -> str:
    s = re.sub(r"[_\-]+", " ", raw.strip())
    s = FILENAME_NOISE.sub(" ", s)
    s = re.sub(r"\s*\d+\s*$", "", s)
    s = re.sub(r"^\d+\s*", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s.title() if s else raw.strip().title()

def _extract_json(text: str) -> Optional[str]:
    """Extract the first balanced JSON object from text."""
    start = text.find('{')
    if start == -1:
        return None
    count = 0
    for i, ch in enumerate(text[start:], start):
        if ch == '{':
            count += 1
        elif ch == '}':
            count -= 1
            if count == 0:
                return text[start:i+1]
    return None  # unbalanced

def _gemma_generate_seo(clean_subject: str, category: str,
                        orig_subject: str) -> Dict[str, str]:
    """Generate SEO fields using Gemma 3 1B from subject + category."""
    prompt = f"""You are an SEO assistant. Output ONLY a JSON object (no extra text) for:
Subject: {clean_subject}
Category: {category}

Fields:
- title: SEO page title (50-70 chars), must contain subject, "PNG", "Transparent", "Free Download".
- h1: conversational H1 (50-80 chars).
- meta_desc: meta description (140-160 chars), include transparent background benefit.
- alt_text: alt attribute (under 125 chars).
- tags: list of 10 relevant comma-separated tags.
- keywords: list of exactly 30 comma-separated long-tail keywords.

Example:
{{"title": "Golden Crown 3D Render PNG Transparent Background Free Download",
  "h1": "Golden Crown PNG on Transparent Background - Free HD Download",
  "meta_desc": "Get this stunning golden crown PNG with transparent background. Perfect for graphic design, banners, and social media. Free HD download.",
  "alt_text": "Golden crown 3D render PNG transparent background",
  "tags": "golden crown png, crown transparent, free crown png, 3d crown png, crown clipart, crown image, royal crown png, crown no background, crown hd, golden crown transparent",
  "keywords": "free golden crown png download, golden crown transparent png, ... (30 total)"
}}

JSON:"""

    import torch
    try:
        _load_gemma_model()
    except Exception as exc:
        print(f"    [Gemma] Model load error: {exc}", flush=True)
        return _fallback_rule_seo(clean_subject, category, orig_subject)

    try:
        inputs = _gemma_tokenizer(prompt, return_tensors="pt")
        with torch.no_grad():
            outputs = _gemma_model.generate(
                **inputs,
                max_new_tokens=600,
                do_sample=False,      # greedy = fast, deterministic
            )
        raw_text = _gemma_tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Extract only the first balanced JSON object
        json_str = _extract_json(raw_text)
        if not json_str:
            raise ValueError("No balanced JSON found in Gemma output")

        data = json.loads(json_str)

        # Validate required keys
        required = ["title", "h1", "meta_desc", "alt_text", "tags", "keywords"]
        for k in required:
            if k not in data:
                raise ValueError(f"Missing key {k} in Gemma output")

        # Ensure exactly 30 keywords
        kw_list = [kw.strip() for kw in data["keywords"].split(",") if kw.strip()]
        if len(kw_list) < 30:
            # Generic fallback keywords (complete list)
            extras = [
                f"{clean_subject.lower()} png free download",
                f"{clean_subject.lower()} transparent png hd",
                f"transparent {clean_subject.lower()} png",
                f"{clean_subject.lower()} png no background",
                f"{clean_subject.lower()} png cutout",
                f"{clean_subject.lower()} isolated png",
                f"{clean_subject.lower()} png high resolution",
                f"free {clean_subject.lower()} png download",
                f"download {clean_subject.lower()} png transparent",
                f"{clean_subject.lower()} png for designers",
                f"{clean_subject.lower()} png clipart free",
                f"{clean_subject.lower()} sticker png transparent",
                f"{clean_subject.lower()} illustration png transparent",
                f"{clean_subject.lower()} png image hd quality",
                f"high quality {clean_subject.lower()} png",
                f"{clean_subject.lower()} png for photoshop",
                f"{clean_subject.lower()} png for canva",
                f"{clean_subject.lower()} png for powerpoint",
                f"{clean_subject.lower()} png for website",
                f"{category.lower()} {clean_subject.lower()} png transparent",
                f"{clean_subject.lower()} {category.lower()} free png",
                f"free {category.lower()} {clean_subject.lower()} png",
                f"{clean_subject.lower()} png image free",
                f"{clean_subject.lower()} cutout image free",
                f"{clean_subject.lower()} png without background",
                f"best {clean_subject.lower()} png transparent",
                f"{clean_subject.lower()} image png free download",
                f"free transparent {clean_subject.lower()} image",
                f"{clean_subject.lower()} png hd free download",
                f"transparent background {clean_subject.lower()} png",
            ]
            existing = set(kw_list)
            kw_list = kw_list + [w for w in extras if w not in existing]
            kw_list = kw_list[:30]
        elif len(kw_list) > 30:
            kw_list = kw_list[:30]

        data["keywords"] = ", ".join(kw_list)

        return {
            "title": data["title"],
            "h1": data["h1"],
            "meta_desc": data["meta_desc"],
            "alt_text": data["alt_text"],
            "tags": data["tags"],
            "description": data["keywords"],
        }

    except Exception as e:
        print(f"    [Gemma] Generation/parse error: {e} — using fallback SEO", flush=True)
        return _fallback_rule_seo(clean_subject, category, orig_subject)


def _fallback_rule_seo(clean_subject: str, category: str,
                       orig_subject: str) -> Dict[str, str]:
    """Simple rule-based SEO when Gemma fails."""
    s = clean_subject or orig_subject.strip() or "Image"
    sl = s.lower()
    cat_sl = (category or "").strip().lower()
    title = f"{s} PNG Transparent Background Free Download"
    h1 = f"{s} PNG on Transparent Background - Free HD Download"
    meta = f"Download this free {s} PNG with transparent background. High quality, perfect for designers and creative projects."
    alt = f"{s} PNG transparent background"
    tags = ", ".join([f"{sl} png", f"{sl} transparent", f"free {sl} png",
                      f"{sl} no background", f"{sl} hd png"])
    kw_list = [f"{sl} png free download", f"{sl} transparent png hd",
               f"free {sl} png download", f"{sl} png no background",
               f"{sl} png transparent background", f"{sl} png cutout",
               f"{sl} isolated png", f"{sl} png high resolution",
               f"high quality {sl} png", f"{sl} png for designers",
               f"{sl} png clipart free", f"{sl} sticker png transparent",
               f"{sl} illustration png transparent",
               f"{sl} png image hd quality", f"best {sl} png transparent",
               f"{sl} image png free download",
               f"free transparent {sl} image",
               f"{sl} png hd free download",
               f"transparent background {sl} png",
               f"{sl} cutout image free",
               f"{sl} png without background",
               f"{sl} png for photoshop", f"{sl} png for canva",
               f"{sl} png for powerpoint", f"{sl} png for website",
               f"{cat_sl} {sl} png transparent",
               f"{sl} {cat_sl} free png",
               f"free {cat_sl} {sl} png",
               f"{sl} png image free",
               f"download {sl} png transparent"]
    kw_list = kw_list[:30]
    return {
        "title": title[:70],
        "h1": h1[:85],
        "meta_desc": meta[:160],
        "alt_text": alt[:125],
        "tags": tags,
        "description": ", ".join(kw_list),
    }


# ══════════════════════════════════════════════════════════════
# VISION SEO stubs — now simply calls Gemma
# ══════════════════════════════════════════════════════════════

def _vision_seo(row: Dict[str, str]) -> Dict[str, str]:
    """Generates SEO for a row using Gemma 3 1B (no image needed)."""
    subject      = (row.get("subject_name") or "").strip()
    category     = row.get("category",     "")
    if not subject:
        raise RuntimeError("Missing subject_name in row")
    clean_subj = _clean_subject(subject)
    print(f"    🧠 Gemma generating SEO for '{clean_subj}' ...", flush=True)
    seo = _gemma_generate_seo(clean_subj, category, subject)
    return seo


def _trigger_self_restart(remaining: int,
                           workflow_file: str = "section2_seo.yml") -> None:
    import requests
    repo     = os.environ.get("GITHUB_REPOSITORY", "").strip()
    gh_token = (os.environ.get("GH_TOKEN") or
                os.environ.get("REPO2_TOKEN", "")).strip()
    ref      = os.environ.get("GITHUB_REF_NAME", "main").strip() or "main"
    if not repo or not gh_token:
        print("  ⚠  Cannot auto-restart: GITHUB_REPOSITORY or GH_TOKEN not set")
        return
    url = (f"https://api.github.com/repos/{repo}"
           f"/actions/workflows/{workflow_file}/dispatches")
    try:
        r = requests.post(
            url,
            headers={"Authorization": f"token {gh_token}",
                     "Accept": "application/vnd.github.v3+json"},
            json={"ref": ref, "inputs": {"count": "", "scan_drive": "false"}},
            timeout=30,
        )
        if r.status_code in (204, 200):
            print(f"  🔄  Auto-restart dispatched ({remaining} items still pending) ✓")
        else:
            print(f"  ⚠  Auto-restart failed: {r.status_code} — {r.text[:120]}")
    except Exception as exc:
        print(f"  ⚠  Auto-restart exception: {exc}")


# ══════════════════════════════════════════════════════════════
# ULTRADATA XLSX READ / UPDATE
# ══════════════════════════════════════════════════════════════

def _read_pending_rows(xlsx_path: Path) -> List[Dict[str, str]]:
    import openpyxl
    wb = openpyxl.load_workbook(str(xlsx_path))
    ws = wb.active
    if ws.max_row < 2:
        return []
    headers = [str(c.value or "").strip() for c in ws[1]]
    idx     = {h: i for i, h in enumerate(headers)}
    needed  = ["subject_name", "filename", "download_url", "preview_url"]
    for h in needed:
        if h not in idx:
            raise RuntimeError(f"ultradata.xlsx missing column: {h}")
    out = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        def _v(col):
            return ("" if col not in idx or r[idx[col]] is None
                    else str(r[idx[col]]).strip())
        if _v("seo_status").lower() == "completed":
            continue
        filename     = _v("filename")
        subject_name = _v("subject_name")
        if not filename or not subject_name:
            continue
        out.append({
            "subject_name": subject_name,
            "filename":     filename,
            "download_url": _v("download_url"),
            "preview_url":  _v("preview_url"),
            "webp_file_id": _v("webp_file_id"),
            "category":     _v("category"),
            "subcategory":  _v("subcategory"),
            "date_added":   _v("date_added"),
        })
    return out

def _mark_completed(xlsx_path: Path, completed_filenames: set) -> int:
    import openpyxl
    if not xlsx_path.exists() or not completed_filenames:
        return 0
    wb = openpyxl.load_workbook(str(xlsx_path))
    ws = wb.active
    if ws.max_row < 2:
        return 0
    headers = [str(c.value or "").strip() for c in ws[1]]
    if "seo_status" not in headers:
        seo_col = len(headers) + 1
        ws.cell(row=1, column=seo_col, value="seo_status")
        headers.append("seo_status")
    else:
        seo_col = headers.index("seo_status") + 1
    if "filename" not in headers:
        return 0
    filename_col = headers.index("filename") + 1
    updated = 0
    for row in ws.iter_rows(min_row=2):
        fn   = str(row[filename_col - 1].value or "").strip()
        cell = row[seo_col - 1]
        if fn in completed_filenames and str(cell.value or "").strip() != "completed":
            cell.value = "completed"
            updated += 1
    wb.save(str(xlsx_path))
    return updated


# ══════════════════════════════════════════════════════════════
# REPO2 (clone / load / save / push)
# ══════════════════════════════════════════════════════════════

@dataclass
class Repo2Config:
    token:    str
    slug:     str
    data_dir: str = "data"

def _clone_repo2(cfg: Repo2Config, workdir: Path) -> Path:
    repo_url = f"https://x-access-token:{cfg.token}@github.com/{cfg.slug}.git"
    if workdir.exists():
        subprocess.run(["git", "pull", "--rebase", "--autostash"],
                       cwd=str(workdir), check=False)
        return workdir
    subprocess.run(["git", "clone", "--depth", "1", repo_url, str(workdir)],
                   check=True)
    return workdir

def _load_existing_entries(repo2_dir: Path,
                            data_dir: str) -> Tuple[Dict[str, Any], List[Path]]:
    d = repo2_dir / data_dir
    d.mkdir(parents=True, exist_ok=True)
    files = sorted([p for p in d.glob("json*.json") if p.is_file()])
    if not files:
        f1 = d / "json1.json"
        f1.write_text("[]", encoding="utf-8")
        files = [f1]
    all_entries: Dict[str, Any] = {}
    for f in files:
        try:
            arr = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(arr, list):
                for e in arr:
                    fn = (e or {}).get("filename")
                    if fn and fn not in all_entries:
                        all_entries[fn] = e
        except Exception:
            continue
    return all_entries, files

def _get_active_file(files: List[Path], repo2_dir: Path, data_dir: str,
                     max_entries: int, file_entries: Dict[Path, List]) -> Path:
    last = files[-1]
    if len(file_entries.get(last, [])) < max_entries:
        return last
    m   = re.match(r"json(\d+)\.json$", last.name)
    nxt = (int(m.group(1)) + 1) if m else (len(files) + 1)
    newf = repo2_dir / data_dir / f"json{nxt}.json"
    newf.write_text("[]", encoding="utf-8")
    files.append(newf)
    file_entries[newf] = []
    print(f"\n  [JSON] Created {newf.name} (previous file full)", flush=True)
    return newf

def _save_json_files(file_entries: Dict[Path, List]) -> None:
    for f, arr in file_entries.items():
        tmp = f.with_suffix(f.suffix + ".tmp")
        tmp.write_text(json.dumps(arr, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        tmp.replace(f)

def _git_setup(repo2_dir: Path) -> None:
    subprocess.run(["git", "config", "user.name",  "github-actions[bot]"],
                   cwd=str(repo2_dir), check=True)
    subprocess.run(["git", "config", "user.email",
                    "github-actions[bot]@users.noreply.github.com"],
                   cwd=str(repo2_dir), check=True)

def _commit_push_repo2(repo2_dir: Path, cfg: "Repo2Config", added: int,
                        commit_msg: Optional[str] = None,
                        file_entries: Optional[Dict] = None,
                        max_retries: int = 3) -> None:
    _git_setup(repo2_dir)
    msg = commit_msg or f"seo: add {added} entries [section2]"
    for attempt in range(1, max_retries + 1):
        subprocess.run(["git", "add", cfg.data_dir],
                        cwd=str(repo2_dir), check=True)
        if (repo2_dir / ULTRADATA_XLSX).exists():
            subprocess.run(["git", "add", ULTRADATA_XLSX],
                            cwd=str(repo2_dir), check=True)
        diff = subprocess.run(["git", "diff", "--staged", "--quiet"],
                               cwd=str(repo2_dir))
        if diff.returncode == 0:
            print("  Repo2: nothing to commit — already up-to-date.")
            return
        subprocess.run(["git", "commit", "-m", msg],
                        cwd=str(repo2_dir), check=True)
        subprocess.run(["git", "fetch", "origin", "main"],
                        cwd=str(repo2_dir), capture_output=True)
        rebase = subprocess.run(["git", "rebase", "origin/main"],
                                 cwd=str(repo2_dir),
                                 capture_output=True, text=True)
        if rebase.returncode != 0:
            print(f"  [WARN] Rebase conflict (attempt {attempt}/{max_retries}) ...")
            subprocess.run(["git", "rebase", "--abort"],
                            cwd=str(repo2_dir), capture_output=True)
            if attempt >= max_retries:
                raise RuntimeError(
                    f"Repo2 push failed after {max_retries} retries.\n"
                    f"Rebase stderr:\n{rebase.stderr}")
            subprocess.run(["git", "reset", "--hard", "origin/main"],
                            cwd=str(repo2_dir), check=True)
            if file_entries:
                _save_json_files(file_entries)
            time.sleep(3 * attempt)
            continue
        result = subprocess.run(["git", "push"], cwd=str(repo2_dir),
                                  capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  Repo2: pushed {added} SEO entries ✓")
            return
        print(f"  [WARN] git push failed (attempt {attempt}/{max_retries}):\n"
              f"{result.stderr}")
        if attempt >= max_retries:
            raise RuntimeError("Repo2 push failed — check REPO2_TOKEN permissions.")
        subprocess.run(["git", "reset", "--hard", "origin/main"],
                        cwd=str(repo2_dir), check=True)
        if file_entries:
            _save_json_files(file_entries)
        time.sleep(3 * attempt)

def _push_xlsx_rows_via_api(cfg: "Repo2Config", new_rows: List[Dict],
                              commit_msg: str, max_retries: int = 3) -> None:
    import requests, openpyxl
    token   = cfg.token
    branch  = "main"
    path    = ULTRADATA_XLSX
    api_url = f"https://api.github.com/repos/{cfg.slug}/contents/{path}"
    headers = {"Authorization": f"token {token}",
               "Accept": "application/vnd.github.v3+json",
               "Content-Type": "application/json"}
    HEADERS = [
        "date_added", "subject_name", "category", "subcategory",
        "filename", "png_file_id", "webp_file_id",
        "download_url", "preview_url", "seo_status",
    ]
    def _fetch_wb() -> Tuple[openpyxl.Workbook, str]:
        r = requests.get(api_url, headers=headers,
                          params={"ref": branch}, timeout=30)
        r.raise_for_status()
        d   = r.json()
        raw = base64.b64decode(d["content"].replace("\n", ""))
        return openpyxl.load_workbook(io.BytesIO(raw)), d["sha"]
    def _append_and_encode(wb_: openpyxl.Workbook) -> str:
        ws_ = wb_.active
        hdr = [ws_.cell(row=1, column=c).value
               for c in range(1, ws_.max_column + 1)]
        if not hdr or hdr[0] is None:
            ws_.append(HEADERS); hdr = HEADERS
        for col_name in HEADERS:
            if col_name not in hdr:
                ws_.cell(row=1, column=ws_.max_column + 1, value=col_name)
                hdr.append(col_name)
        hdr = [ws_.cell(row=1, column=c).value
               for c in range(1, ws_.max_column + 1)]
        for row in new_rows:
            ws_.append([row.get(h, "") for h in hdr])
        buf = io.BytesIO()
        wb_.save(buf)
        return base64.b64encode(buf.getvalue()).decode()
    wb, sha = _fetch_wb()
    for attempt in range(1, max_retries + 1):
        r = requests.put(api_url, headers=headers,
                          json={"message": commit_msg,
                                "content": _append_and_encode(wb),
                                "sha": sha, "branch": branch},
                          timeout=90)
        if r.ok:
            print(f"  xlsx pushed via API (+{len(new_rows)} rows) ✓")
            return
        if r.status_code == 409 and attempt < max_retries:
            print(f"  [WARN] xlsx 409 conflict (attempt {attempt}) — re-fetching ...")
            time.sleep(3 * attempt)
            wb, sha = _fetch_wb()
            continue
        r.raise_for_status()


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def main() -> None:
    root        = Path(__file__).resolve().parent
    repo2_token = os.environ.get("REPO2_TOKEN", "").strip()
    repo2_slug  = os.environ.get("REPO2_SLUG",  "").strip()
    if not repo2_token or not repo2_slug:
        raise SystemExit("❌  Missing REPO2_TOKEN or REPO2_SLUG in environment")
    max_per_file     = int(os.environ.get("REPO2_MAX_PER_JSON", "200"))
    checkpoint_every = 25
    count_env = (os.environ.get("S2_COUNT", "") or "").strip()
    requested: int | None = None
    if count_env:
        try:
            v = int(count_env)
            if v > 0:
                requested = min(v, INSTANT_CAP)
        except Exception:
            pass

    llm_mode = "Gemma 3 1B ✅ (local CPU · ~25s/item · no API key · unlimited)"

    print("=" * 65)
    print("  Section 2 — SEO JSON Builder  (V7.0 — Gemma 3 1B, no image)")
    print(f"  Requested count : {requested if requested else 'ALL pending'}")
    print(f"  Safety cap      : {INSTANT_CAP}")
    print(f"  Max per JSON    : {max_per_file}")
    print(f"  LLM mode        : {llm_mode}")
    print(f"  Max run time    : {MAX_RUN_SECONDS // 3600}h "
          f"{(MAX_RUN_SECONDS % 3600) // 60}m")
    print(f"  Drive PNG scan  : {os.environ.get('SCAN_DRIVE', 'true')}")
    print("=" * 65)

    print("\n[Step 1] Cloning private ultrapng repo ...")
    cfg       = Repo2Config(token=repo2_token, slug=repo2_slug)
    repo2_dir = _clone_repo2(cfg, root / "_repo2_work")
    xlsx      = repo2_dir / ULTRADATA_XLSX
    if not xlsx.exists():
        raise SystemExit(f"❌  {ULTRADATA_XLSX} not found in {repo2_slug}.")

    print("\n[Step 2] Scanning Drive png_library_images for unmatched PNGs ...")
    new_from_drive = process_drive_png_library(repo2_dir, cfg)
    if new_from_drive > 0:
        print(f"  ✅  {new_from_drive} new entries added from Drive scan")
        import shutil
        shutil.rmtree(str(repo2_dir), ignore_errors=True)
        repo2_dir = _clone_repo2(cfg, root / "_repo2_work")
        xlsx      = repo2_dir / ULTRADATA_XLSX

    print("\n[Step 3] Reading pending rows from ultradata.xlsx ...")
    pending = _read_pending_rows(xlsx)
    print(f"  Pending rows : {len(pending)}")
    if not pending:
        print("  ✅  Nothing pending — all done.")
        return

    seen: set = set()
    deduped: List[Dict] = []
    for r in pending:
        fn = r.get("filename", "")
        if fn and fn not in seen:
            seen.add(fn)
            deduped.append(r)
    pending = deduped

    print("\n[Step 4] Loading existing SEO entries from repo2 ...")
    existing, files = _load_existing_entries(repo2_dir, cfg.data_dir)
    print(f"  Existing SEO entries : {len(existing)}")
    todo = [r for r in pending if r["filename"] not in existing]
    print(f"  Still to generate    : {len(todo)}")
    if not todo:
        print("  ✅  All pending rows already have SEO in repo2.")
        return

    target = min(requested, len(todo)) if requested else len(todo)
    print(f"\n[Step 4b] Pre-loading Gemma 3 1B model ...")
    _load_gemma_model()
    print(f"\n  ▶  Generating SEO for up to {target} item(s) ...\n"
          f"     Gemma 3 1B local inference · ~25s/item · unlimited\n")

    file_entries: Dict[Path, List] = {}
    for f in files:
        try:
            arr = json.loads(f.read_text(encoding="utf-8"))
            file_entries[f] = arr if isinstance(arr, list) else []
        except Exception:
            file_entries[f] = []

    added               = 0
    completed_filenames : set = set()
    pending_push        = 0
    time_limit_hit      = False

    for i, r in enumerate(todo, 1):
        if added >= target:
            break
        elapsed = time.time() - _RUN_START
        if elapsed > MAX_RUN_SECONDS:
            print(f"\n⏰  Time limit ({elapsed / 3600:.2f}h) — checkpoint ...")
            time_limit_hit = True
            break

        subject  = r["subject_name"]
        filename = r["filename"]
        print(f"  [{i}/{target}] {subject} ({filename}) ...", flush=True)
        try:
            seo = _vision_seo(r)
        except Exception as e:
            print(f"    ✗ SKIP ({e})", flush=True)
            continue

        slug = re.sub(r"[^a-z0-9]+", "-",
                       _clean_subject(subject).lower()).strip("-") or "untitled"
        webp_fid   = r.get("webp_file_id", "")
        webp_preview = (
            f"https://lh3.googleusercontent.com/d/{webp_fid}=s800"
            if webp_fid else r.get("preview_url", "")
        )
        target_file = _get_active_file(files, repo2_dir, cfg.data_dir,
                                       max_per_file, file_entries)
        if target_file not in file_entries:
            file_entries[target_file] = []
        file_entries[target_file].append({
            "category":         r.get("category", ""),
            "subcategory":      r.get("subcategory", ""),
            "subject_name":     subject,
            "filename":         filename,
            "slug":             slug,
            "download_url":     r["download_url"],
            "preview_url":      r["preview_url"],
            "webp_preview_url": webp_preview,
            "title":            seo["title"],
            "h1":               seo["h1"],
            "meta_desc":        seo["meta_desc"],
            "alt_text":         seo["alt_text"],
            "tags":             seo["tags"],
            "description":      seo["description"],
            "word_count":       _word_count(seo["description"]),
            "date_added":       r.get("date_added", _today()),
        })
        completed_filenames.add(filename)
        added        += 1
        pending_push += 1
        kw = len([k for k in seo["description"].split(",") if k.strip()])
        elapsed_m = (time.time() - _RUN_START) / 60
        print(f"    ✓  title={len(seo['title'])}c  kw={kw}  "
              f"({elapsed_m:.1f} min elapsed)", flush=True)

        if pending_push >= checkpoint_every:
            print(f"\n  [Checkpoint] Saving {pending_push} entries ...")
            _save_json_files(file_entries)
            _mark_completed(xlsx, completed_filenames)
            _commit_push_repo2(repo2_dir, cfg, pending_push,
                                file_entries=file_entries)
            pending_push = 0
            print()

    if pending_push > 0 or completed_filenames:
        print(f"\n[Step 5] Final save & push ({pending_push} remaining) ...")
        _save_json_files(file_entries)
        updated = _mark_completed(xlsx, completed_filenames)
        print(f"  ultradata.xlsx: {updated} row(s) marked completed")
        _commit_push_repo2(repo2_dir, cfg, pending_push,
                            file_entries=file_entries)

    remaining     = len(todo) - added
    total_elapsed = (time.time() - _RUN_START) / 60
    print("\n" + "=" * 65)
    print(f"  ✅  Section 2 complete")
    print(f"  Added this run    : {added}")
    print(f"  Total in repo2    : {len(existing) + added}")
    print(f"  Elapsed time      : {total_elapsed:.1f} min")
    if remaining > 0:
        print(f"  Still pending     : {remaining}")
    print("=" * 65)
    if time_limit_hit and remaining > 0:
        print(f"\n[Auto-restart] Dispatching for {remaining} remaining items ...")
        _trigger_self_restart(remaining)


if __name__ == "__main__":
    main()
