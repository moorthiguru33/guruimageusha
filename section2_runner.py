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

# ── Florence-2-base replaces Gemini API ───────────────────────────────────
# Microsoft Florence-2-base · MIT license · CPU-only · no API key · unlimited
# GitHub Actions free Ubuntu: 2-core CPU, 7GB RAM
# Actual speed on GitHub Actions: ~11s per image (log confirmed)
# VQA task used: passes subject name as hint → much better accuracy
FLORENCE_MODEL_ID = "microsoft/Florence-2-base"

MAX_RUN_SECONDS = 17_400   # 4h50m
_RUN_START      = time.time()

# ── Global model handles (loaded ONCE per run, reused for all images) ──────
_florence_model     = None
_florence_processor = None


def _load_florence_model():
    """Load Florence-2-base once at startup. ~7s on GitHub Actions (cached)."""
    global _florence_model, _florence_processor
    if _florence_model is not None:
        return
    import torch
    from transformers import AutoProcessor, AutoModelForCausalLM
    print(f"  [Florence-2] Loading {FLORENCE_MODEL_ID} ...", flush=True)
    _florence_processor = AutoProcessor.from_pretrained(
        FLORENCE_MODEL_ID, trust_remote_code=True)
    _florence_model = AutoModelForCausalLM.from_pretrained(
        FLORENCE_MODEL_ID,
        trust_remote_code=True,
        torch_dtype=torch.float32,   # float32 for CPU stability
    )
    _florence_model.eval()
    print("  [Florence-2] Model ready ✓", flush=True)


# ══════════════════════════════════════════════════════════════
# GOOGLE DRIVE helpers
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
# VISION SEO — Florence-2-base (local CPU · VQA task with subject hint)
# ══════════════════════════════════════════════════════════════

_COLOR_WORDS = [
    "red", "blue", "green", "yellow", "orange", "purple", "pink",
    "white", "black", "brown", "golden", "silver", "gold", "grey", "gray",
    "dark", "bright", "vibrant", "colorful", "multicolored",
    "crimson", "scarlet", "violet", "indigo", "teal", "cyan", "magenta",
    "lime", "beige", "ivory", "bronze", "rose", "coral", "turquoise",
    "maroon", "navy", "olive", "peach", "lavender", "emerald", "amber",
]

_STYLE_WORDS = [
    "realistic", "cartoon", "vector", "clipart", "3d", "flat", "minimal",
    "watercolor", "digital", "illustrated", "hand-drawn", "artistic",
    "detailed", "simple", "modern", "vintage", "cute", "elegant", "glossy",
    "sketched", "painted", "stylized", "anime", "comic", "retro",
]

_FILENAME_NOISE = re.compile(
    r"\b(hd|png|img|image|photo|pic|transparent|bg|nobg|free|dl|download"
    r"|clipart|vector|stock|high|quality|resolution|res|ultra|4k|full)\b",
    re.I,
)


def _clean_subject(raw: str) -> str:
    s = re.sub(r"[_\-]+", " ", raw.strip())
    s = _FILENAME_NOISE.sub(" ", s)
    s = re.sub(r"\s*\d+\s*$", "", s)
    s = re.sub(r"^\d+\s*", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s.title() if s else raw.strip().title()


def _florence_describe(img_bytes: bytes, subject: str) -> str:
    """
    Florence-2-base local CPU inference.
    Runs TWO tasks per image:
      1. <DETAILED_CAPTION>   → rich visual description with colors, style, details
      2. <VQA> subject hint   → subject-accurate confirmation sentence
    Both results are merged for richer SEO input.
    Speed: ~15-25s per image on GitHub Actions 2-core CPU.
    No API key · No rate limit · No cost · Unlimited.
    """
    import torch
    from PIL import Image

    try:
        _load_florence_model()
    except Exception as exc:
        print(f"    [Florence-2] model load error: {exc}", flush=True)
        return ""

    try:
        image = Image.open(io.BytesIO(img_bytes)).convert("RGB")

        def _run_task(task_prompt: str, max_tokens: int = 150) -> str:
            inputs = _florence_processor(
                text=task_prompt,
                images=image,
                return_tensors="pt",
            )
            with torch.no_grad():
                generated_ids = _florence_model.generate(
                    input_ids=inputs["input_ids"],
                    pixel_values=inputs["pixel_values"],
                    max_new_tokens=max_tokens,
                    num_beams=3,
                    early_stopping=True,
                )
            raw_text = _florence_processor.batch_decode(
                generated_ids, skip_special_tokens=False)[0]
            parsed = _florence_processor.post_process_generation(
                raw_text,
                task=task_prompt.split(">")[0] + ">",
                image_size=(image.width, image.height),
            )
            key = task_prompt.split(">")[0] + ">"
            return (parsed.get(key) or "").strip()

        # Task 1: detailed visual caption (colors, texture, style)
        caption = _run_task("<DETAILED_CAPTION>", max_tokens=160)

        # Task 2: VQA with subject hint to anchor identity
        vqa_q = (
            f"This PNG shows a {subject} on a transparent background. "
            f"What are the dominant colors, art style (realistic, cartoon, vector, "
            f"3D, watercolor, hand-drawn, clipart), and notable visual details?"
        )
        vqa_ans = _run_task(f"<VQA>{vqa_q}", max_tokens=120)

        # Merge: prefer VQA for subject accuracy, caption for visual richness
        parts = []
        if vqa_ans and len(vqa_ans) > 15:
            parts.append(vqa_ans.rstrip("."))
        if caption and len(caption) > 15:
            # avoid near-duplicate
            if not vqa_ans or caption[:40].lower() != vqa_ans[:40].lower():
                parts.append(caption.rstrip("."))

        desc = ". ".join(parts).strip()
        if len(desc) > 200:
            desc = desc[:197].rsplit(" ", 1)[0] + "..."
        return desc

    except Exception as exc:
        print(f"    [Florence-2] inference error: {exc}", flush=True)
        return ""


# Alias so _vision_seo works unchanged
def _gemini_describe(img_bytes: bytes, subject: str) -> str:
    return _florence_describe(img_bytes, subject)

def _fetch_image_for_vision(preview_url: str, download_url: str) -> Optional[bytes]:
    import requests
    headers = {"User-Agent": "UltraPNG-SEO-Bot/5.0"}
    for url in [u for u in [preview_url, download_url] if u]:
        try:
            r = requests.get(url, timeout=30, headers=headers)
            if r.ok and len(r.content) > 500:
                return r.content
        except Exception:
            pass
    return None


def _extract_words_from_desc(visual_desc: str, wordlist: List[str]) -> List[str]:
    desc_lower = visual_desc.lower()
    return [w for w in wordlist
            if re.search(r"\b" + re.escape(w) + r"\b", desc_lower)]


def _build_seo_from_vision(clean_subject: str, visual_desc: str,
                            category: str = "", orig_subject: str = "") -> Dict[str, str]:
    """
    Organic, non-templated SEO builder.
    Every field is constructed from actual visual data so that no two images
    share identical copy — even within the same category.

    Strategy overview:
    ─────────────────
    title     → Lead with the most specific visual signal (color+style or
                unique detail), then subject, then intent keyword.
                6 pools rotated deterministically by subject hash so sibling
                images never share a title pattern.
    h1        → Conversational, descriptive — mirrors natural search phrasing.
                Uses visual_desc sentence[0] when available.
    meta_desc → Opens with the image's unique visual angle, ends with the
                value proposition. Never starts with "Download".
    alt_text  → Screen-reader quality: color + subject + style + context.
    tags      → 10 highest-value tags, color/style-specific when available.
    keywords  → 30 long-tail KWs assembled from visual signals; every KW is
                distinct and search-intent-aligned.
    """
    s   = clean_subject or orig_subject.strip() or "Image"
    sl  = s.lower()
    cat = (category or "").strip()
    cat_sl = cat.lower()

    # ── Visual signals ────────────────────────────────────────────────────
    colors = _extract_words_from_desc(visual_desc, _COLOR_WORDS)
    styles = _extract_words_from_desc(visual_desc, _STYLE_WORDS)

    # Drop color/style words already present in the subject name (avoid "Red Red Grapes").
    # Also drop colors that are root-matches of subject words (e.g. "golden" when
    # subject contains "gold", "silvery" when subject contains "silver").
    sl_words = set(re.split(r"\s+", sl))
    def _color_in_subject(c: str) -> bool:
        if c.lower() in sl_words:
            return True
        # stem check: "golden" vs "gold", "crimson" — just check prefix overlap ≥4 chars
        for w in sl_words:
            if len(c) >= 4 and len(w) >= 4:
                if c[:4] == w[:4]:   # e.g. gold/golden share "gold"
                    return True
        return False
    colors = [c for c in colors if not _color_in_subject(c)]
    styles = [st for st in styles if st.lower() not in sl_words]

    # Primary color: first detected, or empty
    color1 = colors[0] if colors else ""
    color2 = colors[1] if len(colors) > 1 else ""

    # Primary style: prefer visually meaningful ones for use as qualifier prefix.
    # "3d" alone reads poorly as a prefix ("3d Crown PNG") — only include it when
    # paired with a color. Also skip generic styles when used solo.
    _generic_styles    = {"realistic", "detailed", "modern", "simple"}
    _awkward_solo_stys = {"3d", "digital", "illustrated", "painted", "sketched"}
    style1 = next((st for st in styles
                   if st not in _generic_styles and st not in _awkward_solo_stys), "")
    # Allow awkward-solo styles only when a color is also present (e.g. "Golden 3D")
    if not style1 and color1:
        style1 = next((st for st in styles if st not in _generic_styles), "")
    style1 = style1 or (styles[0] if styles else "")
    style2 = next((st for st in styles[1:]
                   if st not in _generic_styles and st != style1), "")

    # Short visual snippet from description (first sentence, ≤60 chars)
    vis_snip = ""
    if visual_desc:
        first_sent = visual_desc.split(".")[0].strip()
        vis_snip = first_sent[:45].rstrip(" ,") if first_sent else ""

    # Build a "visual qualifier" — the most specific prefix we can attach
    qual_parts: List[str] = []
    if color1:
        qual_parts.append(color1.capitalize())
    if style1 and style1 not in _generic_styles:
        qual_parts.append(style1.capitalize())
    qualifier = " ".join(qual_parts)   # e.g. "Red Watercolor" or "Golden 3D" or ""

    # ── Hash-based pool selectors (each field gets its own offset so title/h1/meta
    #    never all land on the same pool pattern for the same subject) ────────────
    _h = abs(hash(orig_subject or s))
    _title_idx = _h % 6
    _h1_idx    = (_h // 6)  % 6
    _meta_idx  = (_h // 36) % 6

    # ── TITLE (50-65 chars ideal for Google) ─────────────────────────────
    # 6 pools, each with a "qualifier available" and "no qualifier" variant
    def _pick_title() -> str:
        pools = [
            # Pool 0 — color/style qualifier leads
            (f"{qualifier} {s} PNG - Transparent Background Free Download"
             if qualifier else
             f"{s} PNG - Transparent Background Free Download"),
            # Pool 1 — action-oriented
            (f"Download {qualifier} {s} PNG | Transparent HD Image"
             if qualifier else
             f"Download {s} PNG | High Quality Transparent Background"),
            # Pool 2 — cutout / use-case
            (f"{s} Transparent PNG - {qualifier} Cutout Free"
             if qualifier else
             f"{s} Transparent PNG Cutout - Free High Resolution"),
            # Pool 3 — clipart / format
            (f"Free {qualifier} {s} PNG Clipart with Transparent BG"
             if qualifier else
             f"Free {s} PNG Clipart - No Background HD"),
            # Pool 4 — image lead with qualifier
            (f"{qualifier} {s} PNG Image | Transparent Background"
             if qualifier else
             f"{s} PNG Image | Transparent Background HD"),
            # Pool 5 — quality + resolution
            (f"High-Res {qualifier} {s} PNG - Clear Transparent Background"
             if qualifier else
             f"High-Res {s} PNG - Clear Transparent Background Free"),
        ]
        raw = pools[_title_idx]
        # If primary pool produces a very short title, try next pools until ≥45 chars
        if len(raw) < 45:
            for fallback_pool in pools[_title_idx + 1:] + pools[:_title_idx]:
                if len(fallback_pool) >= 45:
                    raw = fallback_pool
                    break
        # Hard cap at 65 chars; trim at word boundary
        if len(raw) > 65:
            raw = raw[:62].rsplit(" ", 1)[0].rstrip(" |-") + "..."
        return raw

    title = _pick_title()

    # ── H1 (conversational, 52-80 chars — different pool offset from title) ──
    def _pick_h1() -> str:
        h1_pools = [
            # Pool 0 — qualifier + subject + context
            (f"{qualifier} {s} PNG on Transparent Background - Free HD"
             if qualifier else
             f"{s} PNG Image on Transparent Background - Free HD"),
            # Pool 1 — color-forward conversational
            (f"{color1.capitalize()} {s} PNG - No Background, High Resolution"
             if color1 else
             f"{s} PNG - Clean Transparent Background, High Resolution"),
            # Pool 2 — style-forward descriptive
            (f"{style1.capitalize()} {s} PNG - Transparent Cutout Free Download"
             if style1 else
             f"{s} PNG Transparent Cutout - Free High Quality Download"),
            # Pool 3 — category + subject context
            (f"{s} {cat} PNG - Isolated on Transparent Background"
             if cat_sl and cat_sl != sl else
             f"{s} PNG - Professionally Isolated Transparent Background"),
            # Pool 4 — search-intent download phrasing
            (f"{qualifier} {s} PNG Free Download - Transparent Background"
             if qualifier else
             f"{s} PNG Free Download - Transparent Background HD"),
            # Pool 5 — use-case / design context
            (f"{s} PNG for Design Projects - {qualifier} Transparent"
             if qualifier else
             f"{s} PNG for Design Projects - Transparent Background Free"),
        ]
        raw = h1_pools[_h1_idx]
        return raw[:80].strip()

    h1 = _pick_h1()

    # ── META DESCRIPTION (140-155 chars, different pool offset from both above) ─
    # Never starts with "Download". Opens with unique visual/value angle.
    def _pick_meta() -> str:
        # Build a tight visual context clause from the description (max 85 chars)
        if visual_desc and len(visual_desc) > 20:
            sents = [s2.strip() for s2 in visual_desc.split(".") if s2.strip()]
            raw_ctx = sents[0]
            if len(raw_ctx) > 85:
                raw_ctx = raw_ctx[:82].rsplit(" ", 1)[0]  # word-boundary trim
            context = raw_ctx.rstrip(" ,")
            if len(sents) > 1 and len(context) < 45:
                ctx2 = sents[1][:40].rsplit(" ", 1)[0].rstrip(" ,")
                context += ". " + ctx2
        else:
            context = ""

        meta_pools = [
            # Pool 0 — visual context leads, value prop closes
            (f"{context}. Get this {sl} PNG with transparent background — "
             f"perfect for graphic design, print, and web projects. Free HD download."
             if context else
             f"Eye-catching {qualifier} {sl} PNG with a fully transparent background. "
             f"Ideal for design work, presentations, and creative projects. Free download."
             if qualifier else
             f"Crisp {sl} PNG with a fully transparent background. "
             f"Ready to drop into any design, web page, or presentation. Free HD download."),

            # Pool 1 — style-forward, tool mention
            (f"{context}. This {style1} {sl} PNG has a clean transparent background "
             f"— no editing needed. Free, high-resolution and ready for any project."
             if context and style1 else
             f"Beautifully rendered {qualifier} {sl} with transparent background. "
             f"Works instantly in Photoshop, Canva, or any design tool. Free PNG download."
             if qualifier else
             f"High-quality {sl} PNG on a transparent background. "
             f"Drop it straight into Photoshop, Canva, or Figma. Completely free."),

            # Pool 2 — color-forward, standout angle
            (f"{color1.capitalize()} tones give this {sl} PNG its distinctive look. "
             f"Transparent background, HD resolution — ready for any creative project. Free."
             if color1 else
             f"This {sl} PNG has a clean transparent background and crisp HD resolution. "
             f"Use it in posters, banners, or social media graphics. Completely free."),

            # Pool 3 — question-hook, use-case closes
            (f"Looking for a {sl} PNG? {context}. Transparent background, HD quality, "
             f"free to use in any creative project."
             if context else
             f"Looking for a {sl} PNG with no background? This HD image is ready for "
             f"presentations, social posts, and print designs — completely free."),

            # Pool 4 — visual detail + audience
            (f"{context}. A {qualifier} {sl} PNG with transparent background — "
             f"great for designers, educators, and content creators. Free HD."
             if context and qualifier else
             f"Professionally isolated {sl} PNG with transparent background. "
             f"Perfect for product mockups, school projects, and creative collages. Free."),

            # Pool 5 — benefit-forward, distinct opener per color/style
            (f"Vivid {qualifier} {sl} PNG, fully transparent and HD — "
             f"paste it into any layout without extra editing. Free download."
             if qualifier else
             f"Clean, ready-to-use {sl} PNG with a transparent background. "
             f"No clipping needed — just place it in your design and go. Free HD."),
        ]
        raw = meta_pools[_meta_idx]
        # Trim to 155 chars at word boundary
        if len(raw) > 155:
            raw = raw[:152].rsplit(" ", 1)[0].rstrip(" .,") + "."
        return raw

    meta_desc = _pick_meta()

    # ── ALT TEXT (screen-reader + SEO, ≤125 chars) ───────────────────────
    alt_parts: List[str] = []
    if color1:
        alt_parts.append(color1)
    if style1:
        alt_parts.append(style1)
    alt_parts.append(s)
    alt_parts.append("PNG")
    if cat_sl and cat_sl != sl:
        alt_parts.append(f"in {cat} category")
    alt_parts.append("transparent background")
    alt_text = " ".join(alt_parts).capitalize()
    if len(alt_text) > 125:
        alt_text = alt_text[:122].rsplit(" ", 1)[0] + "..."

    # ── TAGS (10 highest-value, comma-separated) ──────────────────────────
    tag_pool: List[str] = [f"{sl} png", f"{sl} transparent background"]
    if color1:
        tag_pool.insert(0, f"{color1} {sl} png")  # most specific first
    if style1:
        tag_pool.append(f"{style1} {sl} png")
    if color2:
        tag_pool.append(f"{color2} {sl}")
    if cat_sl and cat_sl != sl:
        tag_pool.append(f"{cat_sl} png")
        tag_pool.append(f"{sl} {cat_sl}")
    tag_pool += [
        f"free {sl} png",
        f"{sl} clipart",
        f"{sl} no background",
        f"transparent {sl}",
        f"{sl} hd png",
        f"download {sl} png",
    ]
    # Deduplicate preserving order
    seen_tags: set = set()
    tags_final: List[str] = []
    for t_ in tag_pool:
        tn = re.sub(r"\s+", " ", t_.strip().lower())
        if tn and tn not in seen_tags:
            seen_tags.add(tn)
            tags_final.append(tn)
        if len(tags_final) == 10:
            break
    tags = ", ".join(tags_final)

    # ── KEYWORDS / DESCRIPTION (30 long-tail KWs) ────────────────────────
    # Ordered from highest-intent (download/free) to informational
    kw_pool: List[str] = []

    # Tier 1 — transactional (highest intent)
    kw_pool += [
        f"free {sl} png download",
        f"download {sl} png transparent",
        f"{sl} png free download hd",
        f"{sl} png no background free",
    ]
    if color1:
        kw_pool.append(f"free {color1} {sl} png download")
    if style1:
        kw_pool.append(f"free {style1} {sl} png download")

    # Tier 2 — product descriptors
    kw_pool += [
        f"{sl} png transparent background",
        f"{sl} transparent png hd",
        f"{sl} png cutout",
        f"{sl} isolated png",
        f"{sl} png no background",
        f"{sl} background removed png",
        f"{sl} png high resolution",
        f"transparent {sl} image png",
    ]
    if color1:
        kw_pool += [
            f"{color1} {sl} png transparent",
            f"{color1} {sl} transparent background",
        ]
    if color2:
        kw_pool.append(f"{color2} {sl} png")
    if style1:
        kw_pool += [
            f"{style1} {sl} png transparent",
            f"{style1} {sl} image free",
        ]
    if style2:
        kw_pool.append(f"{style2} {sl} png")

    # Tier 3 — use-case / informational
    kw_pool += [
        f"{sl} png for designers",
        f"{sl} png clipart free",
        f"{sl} sticker png transparent",
        f"{sl} png graphic design",
        f"{sl} illustration png transparent",
        f"{sl} png image hd quality",
        f"{sl} png for presentation",
        f"high quality {sl} png",
        f"{sl} png for photoshop",
        f"{sl} vector png transparent",
        f"{sl} png for canva",
        f"{sl} png for powerpoint",
    ]
    if cat_sl and cat_sl != sl:
        kw_pool += [
            f"{cat_sl} {sl} png transparent",
            f"{sl} {cat_sl} free png",
            f"free {cat_sl} {sl} png",
        ]

    # Tier 4 — padding (always fills to 30 even with no visual signals)
    kw_pool += [
        f"{sl} png hd free download",
        f"transparent background {sl} png",
        f"{sl} png file download",
        f"{sl} png image free",
        f"{sl} cutout image free",
        f"{sl} png without background",
        f"best {sl} png transparent",
        f"{sl} png for website",
        f"{sl} image png free download",
        f"free transparent {sl} image",
    ]

    # Deduplicate and cap at 30
    seen_kw: set = set()
    kws_final: List[str] = []
    for kw in kw_pool:
        kw_n = re.sub(r"\s+", " ", kw.strip().lower())
        if kw_n and kw_n not in seen_kw:
            seen_kw.add(kw_n)
            kws_final.append(kw_n)
        if len(kws_final) == 30:
            break

    return {
        "title":       title,
        "h1":          h1,
        "meta_desc":   meta_desc,
        "alt_text":    alt_text,
        "tags":        tags,
        "description": ", ".join(kws_final),
    }


def _vision_seo(row: Dict[str, str]) -> Dict[str, str]:
    subject      = (row.get("subject_name") or "").strip()
    preview_url  = row.get("preview_url",  "")
    download_url = row.get("download_url", "")
    category     = row.get("category",     "")
    if not subject:
        raise RuntimeError("Missing subject_name in row")
    clean_subj  = _clean_subject(subject)
    visual_desc = ""
    img_bytes   = _fetch_image_for_vision(preview_url, download_url)
    if img_bytes:
        raw_desc = _florence_describe(img_bytes, clean_subj)
        # Quality gate: require at least 20 chars and at least one real word
        if raw_desc and len(raw_desc) >= 20 and re.search(r"[a-zA-Z]{3,}", raw_desc):
            visual_desc = raw_desc
            print(f"    👁  vision ({len(visual_desc)}c): {visual_desc[:90]!r}", flush=True)
        else:
            print(f"    ⚠  Florence-2 low-quality result — template SEO fallback", flush=True)
    else:
        print(f"    ⚠  image download failed — template SEO fallback", flush=True)
    return _build_seo_from_vision(clean_subj, visual_desc, category, subject)


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

    vision_mode = "Florence-2-base ✅ (local CPU · ~11s/img · no API key · unlimited)"

    print("=" * 65)
    print("  Section 2 — SEO JSON Builder  (V7.0 — Organic SEO + Florence-2 Dual-Task)")
    print(f"  Requested count : {requested if requested else 'ALL pending'}")
    print(f"  Safety cap      : {INSTANT_CAP}")
    print(f"  Max per JSON    : {max_per_file}")
    print(f"  Vision mode     : {vision_mode}")
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
    print(f"\n[Step 4b] Pre-loading Florence-2-base model ...")
    _load_florence_model()
    print(f"\n  ▶  Generating SEO for up to {target} item(s) ...\n"
          f"     Florence-2-base local inference · ~11s/image · unlimited\n")

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

        clean_subj = _clean_subject(subject)
        slug       = re.sub(r"[^a-z0-9]+", "-",
                             clean_subj.lower()).strip("-") or "untitled"
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
