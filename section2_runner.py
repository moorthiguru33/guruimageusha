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

# ── Gemini replaces Moondream2 ─────────────────────────────────────────────
# Free tier: 1500 req/day, 15 req/min, zero cost, no model download, ~1s/call
GEMINI_MODEL   = "gemini-2.0-flash"
GEMINI_API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

MAX_RUN_SECONDS = 17_400   # 4h50m
_RUN_START      = time.time()

# ── Rate-limit guard: 14 req/min (free tier cap is 15/min) ────────────────
_GEMINI_WINDOW: List[float] = []
_GEMINI_MAX_PER_MIN = 14


def _gemini_rate_wait() -> None:
    now    = time.time()
    cutoff = now - 60.0
    while _GEMINI_WINDOW and _GEMINI_WINDOW[0] < cutoff:
        _GEMINI_WINDOW.pop(0)
    if len(_GEMINI_WINDOW) >= _GEMINI_MAX_PER_MIN:
        sleep_for = 60.0 - (now - _GEMINI_WINDOW[0]) + 0.5
        if sleep_for > 0:
            print(f"    [rate-limit] {sleep_for:.1f}s pause (14/min cap) ...",
                  flush=True)
            time.sleep(sleep_for)
    _GEMINI_WINDOW.append(time.time())


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
# VISION SEO — Gemini 2.0 Flash (replaces Moondream2)
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


def _gemini_describe(img_bytes: bytes, subject: str) -> str:
    """
    Gemini 2.0 Flash vision API — free tier: 1500/day, 15/min.
    Returns a short 1-sentence visual description of the image.
    """
    import requests

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return ""

    _gemini_rate_wait()

    mime = "image/png"
    if img_bytes[:3] == b"\xff\xd8\xff":
        mime = "image/jpeg"
    elif img_bytes[:4] == b"RIFF" and img_bytes[8:12] == b"WEBP":
        mime = "image/webp"

    prompt = (
        f"This PNG shows '{subject}'. "
        "In ONE short sentence (max 120 chars) describe: "
        "main colors, visual style (realistic/cartoon/vector/clipart/3D), "
        "and any distinctive features. Be factual and concise."
    )

    payload = {
        "contents": [{"parts": [
            {"inline_data": {"mime_type": mime,
                             "data": base64.b64encode(img_bytes).decode()}},
            {"text": prompt},
        ]}],
        "generationConfig": {"maxOutputTokens": 150, "temperature": 0.2},
    }

    url = f"{GEMINI_API_URL}?key={api_key}"
    for attempt in range(1, 4):
        try:
            r = requests.post(url, json=payload, timeout=30)
            if r.status_code == 429:
                wait = 20 * attempt
                print(f"    [Gemini] 429 — waiting {wait}s ...", flush=True)
                time.sleep(wait)
                continue
            r.raise_for_status()
            data = r.json()
            text = (data.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text", "")).strip()
            return text
        except Exception as exc:
            print(f"    [Gemini] attempt {attempt} error: {exc}", flush=True)
            if attempt < 3:
                time.sleep(5 * attempt)
    return ""


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
    s  = clean_subject or orig_subject.strip() or "Image"
    sl = s.lower()
    colors = _extract_words_from_desc(visual_desc, _COLOR_WORDS)
    styles = _extract_words_from_desc(visual_desc, _STYLE_WORDS)
    cat_sl = (category or "").lower().strip()
    pfx_parts: List[str] = []
    if colors:
        pfx_parts.append(colors[0].capitalize())
    non_obvious = [st for st in styles
                   if st not in ("realistic", "detailed", "modern", "simple")]
    if non_obvious:
        pfx_parts.append(non_obvious[0].capitalize())
    prefix = " ".join(pfx_parts)

    def t(a: str, b: str) -> str:
        return (a if prefix else b)[:60].strip()

    title_patterns = [
        t(f"{prefix} {s} PNG Transparent Background Free Download",
          f"{s} PNG Transparent Background - Free HD Download"),
        t(f"Download {prefix} {s} PNG - High Quality Transparent Image",
          f"Download {s} PNG - Transparent Background HD Image"),
        t(f"{s} Transparent PNG - {prefix} Isolated Image Free Download",
          f"{s} Transparent PNG - Isolated Background Free Download"),
        t(f"Free {prefix} {s} PNG Clipart - Transparent Background",
          f"Free {s} PNG Clipart - Transparent HD Background"),
        t(f"{s} PNG Image with Transparent Background - {prefix} Download",
          f"{s} PNG Image with Transparent Background - HD Free"),
        t(f"High Quality {prefix} {s} PNG - Transparent Background",
          f"High Quality {s} PNG - Transparent Background Free"),
    ]
    title = title_patterns[abs(hash(orig_subject or s)) % len(title_patterns)]

    if visual_desc and len(visual_desc) > 20:
        snippet = visual_desc.split(".")[0][:55].strip()
        h1 = f"{s} PNG - {snippet}"
    elif prefix:
        h1 = f"{prefix} {s} PNG Image with Transparent Background"
    else:
        h1 = f"{s} PNG Image with Transparent Background HD Quality"
    h1 = h1[:80]

    if visual_desc:
        visual_snippet = visual_desc[:75].rstrip(" .,")
        meta_desc = (f"Download {sl} PNG with transparent background. "
                     f"{visual_snippet}. Free HD image for designers & projects.")
    else:
        meta_desc = (f"Download high-quality {sl} PNG with transparent background. "
                     f"Perfect for graphic design, presentations, and creative projects. "
                     f"Free HD download.")
    meta_desc = meta_desc[:155]

    alt_text = (f"{prefix} {s} on transparent background - high quality PNG image"
                if prefix else
                f"{s} on transparent background - high resolution free PNG image")[:125]

    tag_parts = [f"{sl} png", f"{sl} transparent background", f"{sl} hd png"]
    if colors:
        tag_parts.append(f"{colors[0]} {sl}")
    if styles:
        tag_parts.append(f"{styles[0]} {sl} png")
    if cat_sl and cat_sl != sl:
        tag_parts.append(f"{cat_sl} png")
    tag_parts += [f"{sl} clipart", f"free {sl} png", f"{sl} download"]
    tags = ", ".join(tag_parts[:10])

    kws_raw = [
        f"{sl} png", f"{sl} transparent background", f"{sl} hd image",
        f"{sl} clipart", f"free {sl} png", f"{sl} png download",
        f"{sl} cutout png", f"transparent {sl} png", f"{sl} high quality png",
        f"{sl} isolated png", f"{sl} png image", f"{sl} background removed png",
        f"{sl} digital art png", f"{sl} transparent png free", f"download {sl} png",
        f"{sl} high resolution png", f"{sl} png file free", f"{sl} sticker png",
        f"{sl} vector png", f"free {sl} clipart png", f"{sl} no background png",
        f"{sl} png hd free download", f"{sl} illustration png",
        f"{sl} graphic design png", f"png {sl} transparent free",
    ]
    for c in colors[:2]:
        kws_raw += [f"{c} {sl} png", f"{c} {sl} transparent background"]
    for st in styles[:1]:
        kws_raw.append(f"{st} {sl} png")
    if cat_sl and cat_sl != sl:
        kws_raw += [f"{cat_sl} {sl} png", f"{sl} {cat_sl} transparent"]
    seen_kw: set = set()
    kws_final: List[str] = []
    for kw in kws_raw:
        kw_n = re.sub(r"\s+", " ", kw.strip().lower())
        if kw_n and kw_n not in seen_kw:
            seen_kw.add(kw_n)
            kws_final.append(kw_n)
        if len(kws_final) >= 30:
            break

    return {
        "title":       title,
        "h1":          h1,
        "meta_desc":   meta_desc,
        "alt_text":    alt_text,
        "tags":        tags,
        "description": ", ".join(kws_final[:30]),
    }


def _vision_seo(row: Dict[str, str]) -> Dict[str, str]:
    subject      = (row.get("subject_name") or "").strip()
    preview_url  = row.get("preview_url",  "")
    download_url = row.get("download_url", "")
    category     = row.get("category",     "")
    if not subject:
        raise RuntimeError("Missing subject_name in row")
    clean_subj = _clean_subject(subject)
    api_key    = os.environ.get("GEMINI_API_KEY", "").strip()
    visual_desc = ""
    if api_key:
        img_bytes = _fetch_image_for_vision(preview_url, download_url)
        if img_bytes:
            visual_desc = _gemini_describe(img_bytes, clean_subj)
            if visual_desc:
                print(f"    👁  vision: {visual_desc[:80]!r}", flush=True)
        else:
            print(f"    ⚠  image download failed — template SEO", flush=True)
    else:
        print(f"    ℹ  no GEMINI_API_KEY — template SEO", flush=True)
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

    gemini_key  = os.environ.get("GEMINI_API_KEY", "").strip()
    vision_mode = ("Gemini 2.0 Flash ✅ (free API, ~1s/image)"
                   if gemini_key else
                   "Template only ⚠️  (add GEMINI_API_KEY secret for vision)")

    print("=" * 65)
    print("  Section 2 — SEO JSON Builder  (V5.0 — Gemini Flash Vision)")
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
    print(f"\n  ▶  Generating SEO for up to {target} item(s) ...\n"
          f"     (No model loading — Gemini API is instant!)\n")

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
