import json
import os
import re
import subprocess
import io
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


ULTRADATA_XLSX    = "ultradata.xlsx"
WATERMARK_TEXT    = "www.ultrapng.com"
S2_TRACKER_FILE   = "progress/s2_batch_tracker.txt"
INSTANT_CAP       = 1000    # GitHub Actions 6-hr safety cap for instant mode

# ── GROQ RATE LIMIT SAFE SETTINGS ─────────────────────────────
# LLaMA 3.3 70B free tier = 6,000 TPM. Each call ~900 tokens.
# Safe = 4 calls/min → 15 sec sleep between calls.
GROQ_SLEEP_SEC    = 15.0

# ── ACTIVE GROQ MODELS ONLY (verified March 2026) ─────────────
# mixtral-8x7b-32768  → DEPRECATED March 2025   ❌
# gemma2-9b-it        → DEPRECATED August 2025  ❌
# llama-3.3-70b-versatile → Active ✅ (primary — best quality)
# llama-3.1-8b-instant    → Active ✅ (fallback — higher TPM)
GROQ_MODELS = [
    "llama-3.3-70b-versatile",   # Primary: best SEO quality
    "llama-3.1-8b-instant",      # Fallback: higher rate limit
]

# ── GROQ VISION MODEL (single-shot: see image + write SEO) ────
# llama-4-scout-17b-16e-instruct → Active ✅ Vision capable, Free
GROQ_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


# ══════════════════════════════════════════════════════════════
# UTILITIES
# ══════════════════════════════════════════════════════════════

def _word_count(s: str) -> int:
    return len([w for w in re.split(r"\s+", (s or "").strip()) if w])


def _today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


# ══════════════════════════════════════════════════════════════
# PROGRESS TRACKER  (progress/s2_batch_tracker.txt)
# ══════════════════════════════════════════════════════════════

def _read_s2_tracker(root: Path) -> int:
    p = root / S2_TRACKER_FILE
    try:
        return int(p.read_text(encoding="utf-8").strip())
    except Exception:
        return 0


def _write_s2_tracker(root: Path, total: int) -> None:
    p = root / S2_TRACKER_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(str(total), encoding="utf-8")


# ══════════════════════════════════════════════════════════════
# WEB SEARCH  (DuckDuckGo — no key needed)
# ══════════════════════════════════════════════════════════════

def _ddg_snippets(query: str, limit: int = 6) -> List[str]:
    import requests
    q = (query or "").strip()
    if not q:
        return []
    r = requests.post("https://duckduckgo.com/html/", data={"q": q},
                      timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    if not r.ok:
        return []
    snippets = re.findall(r'class="result__snippet".*?>(.*?)</a>',
                          r.text, flags=re.S | re.I)
    cleaned = []
    for s in snippets:
        s = re.sub(r"<.*?>", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        if s and s not in cleaned:
            cleaned.append(s)
        if len(cleaned) >= limit:
            break
    return cleaned


# ══════════════════════════════════════════════════════════════
# GROQ VISION + SEO  (single-shot: image → all SEO fields)
# ══════════════════════════════════════════════════════════════

def _groq_vision_seo(subject_name: str, image_url: str,
                     retries: int = 3) -> Dict[str, str]:
    """
    Single API call: Groq Vision model sees the actual PNG image
    and writes all SEO fields in one shot.

    Model: llama-4-scout-17b-16e-instruct (vision capable, free tier)
    Fallback: llama-3.3-70b-versatile / llama-3.1-8b-instant (text-only)

    Respects Groq 429 retry-after header automatically.
    """
    import requests

    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Missing GROQ_API_KEY")
    subject = (subject_name or "").strip()
    if not subject:
        raise RuntimeError("Missing subject_name")

    seo_prompt = f"""You are a passionate graphic design expert and nature writer.
You genuinely love helping designers, students, teachers, and small business owners find beautiful images.
You are writing an informative, helpful resource page — NOT a download page, NOT an ad page.

Look carefully at the image. Write as if you discovered this beautiful {subject} image and want to share everything useful about it.

Subject: {subject}

STRICT RULES — violation causes rejection:
- NEVER write "download" more than twice in the entire description
- NEVER use "click here", "visit our site", "check out", "get it now", "grab it"
- NEVER say "The image provided", "This image shows", "UltraPNG.com showcases"
- NEVER mention AI, Groq, machine learning, robots, or automated tools
- NEVER sound like an advertisement — write like an expert sharing knowledge
- NEVER use bullet points or numbered lists
- NEVER repeat sentence structures across paragraphs
- Write like a real human expert who genuinely cares about design quality

OUTPUT: One valid JSON object with exactly these keys:

"title":
  MINIMUM 20 WORDS — count every single word before submitting.
  Write a natural, informative title a real human expert would write.
  Focus on: what makes THIS specific image special + who will find it useful.
  Vary structure completely — no two titles should follow the same pattern.
  EXAMPLE (count=24 words): "Striking Deep-Red Crab with Glistening Shell Texture on Clear Background — Ideal for Marine Biology Projects, Seafood Menus, and Coastal Design Themes"

"h1":
  8–14 words. Describe what makes this specific {subject} image stand out.
  Focus on a visual quality + use case. Never generic.

"meta_desc":
  Under 155 characters. Written to make someone curious, not to sell.
  Describe what's special about this image + one compelling reason to use it.

"alt_text":
  Precise visual description for screen readers and image search.
  Include: dominant color, subject, count (if multiple), angle, one distinctive detail.
  Format: "[color] {subject} [detail] on transparent background"

"tags":
  8–10 keywords. Mix of: subject-specific, color-specific, use-case, profession-specific.
  Examples: "{subject} transparent png", "seafood illustration", "marine life graphic",
  "restaurant menu artwork", "{subject} clipart hd", "food photography png"
  NO generic tags like "free image", "png download", "design resources" alone.

"description":
  MINIMUM 450 WORDS — count as you write. Five paragraphs. Pure prose, no lists.

  Paragraph 1 — ABOUT THIS IMAGE (minimum 110 words):
    Write as a passionate photographer or naturalist describing what they see.
    Start with the most striking visual detail — color, texture, composition.
    NEVER start with "The", "This", or the subject name directly.
    Start with a descriptive phrase: "Glistening under studio light...", "A rich amber tone...", "Caught at the perfect angle..."
    Describe: exact colors, surface texture, lighting quality, composition angle,
    number of subjects, any unique visual characteristics.
    End by explaining what makes this particular image special for creative work.

  Paragraph 2 — CREATIVE APPLICATIONS (minimum 110 words):
    Connect the SPECIFIC visual details from paragraph 1 to real use cases.
    Write like a design teacher explaining possibilities to a student.
    Example: "The warm amber shell tones make this {subject} a natural fit for autumn-themed restaurant menus..."
    Cover at least 4 different contexts: education, food industry, social media, print design.
    Explain WHY the visual properties suit each use — not just that they "can be used".
    Mention specific tools: Canva, Photoshop, Illustrator, Google Slides, PowerPoint.

  Paragraph 3 — WORKING WITH TRANSPARENT PNG (minimum 90 words):
    Write as a design tutor explaining transparent PNG to someone new to design.
    Find a fresh angle — explain it through a real scenario or comparison.
    Cover: no background removal needed, layers cleanly over any color,
    no jagged white edges like JPEG, maintains quality at any size,
    compatible with all major design software.
    Make this feel like genuine helpful advice, not technical documentation.

  Paragraph 4 — PRACTICAL TIPS (minimum 80 words):
    Share 2–3 genuinely useful tips for working with this specific image.
    Examples: suggested background colors that complement this {subject}'s colors,
    good font pairings for menu or poster use, ideal sizing for social media formats,
    how to add a drop shadow in Canva for depth.
    Write from experience — as if you have personally used this image in projects.

  Paragraph 5 — WHO WILL LOVE THIS (minimum 80 words):
    Paint a picture of specific real people who would benefit.
    Connect their work to THIS image's specific visual qualities.
    Examples: "A marine biology teacher preparing a lesson on crustaceans...",
    "A seafood restaurant owner designing a summer specials menu..."
    Be specific, warm, and encouraging — like a friend recommending something great.
    Do NOT end with a call-to-action or promotional sentence.

Return ONLY the JSON object. No markdown fences. No extra text."""

    def _make_messages(use_image: bool) -> list:
        if use_image and image_url:
            return [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text",      "text": seo_prompt},
                ],
            }]
        return [{"role": "user", "content": seo_prompt}]

    # Banned phrases — AdSense flags these as ad-page / AI / low-value signals
    _BANNED = [
        "the image provided", "the png image provided",
        "as an ai", "i can see", "i can observe", "upon examining",
        "click here", "visit our site", "check out", "grab it",
        "get it now", "don't miss", "act now", "limited time",
        "showcases a", "this image shows", "the image shows",
        "in conclusion", "in summary", "to summarize",
    ]

    def _parse_seo(content: str) -> Dict[str, str]:
        j0, j1 = content.find("{"), content.rfind("}") + 1
        if j0 == -1 or j1 == 0:
            raise ValueError("No JSON in response")
        raw  = content[j0:j1]
        data = json.loads(raw, strict=False)

        title     = (data.get("title")       or "").strip()
        desc      = (data.get("description") or "").strip()
        h1        = (data.get("h1")          or title).strip()
        meta_desc = (data.get("meta_desc")   or "").strip()
        alt_text  = (data.get("alt_text")    or title).strip()
        tags      = (data.get("tags")        or "").strip()

        # ── Strict quality gates ────────────────────────────
        title_wc = _word_count(title)
        desc_wc  = _word_count(desc)
        if title_wc < 20:
            raise RuntimeError(f"Title too short: {title_wc} words (need 20+) → '{title[:60]}'")
        if desc_wc < 400:
            raise RuntimeError(f"Description too short: {desc_wc} words (need 400+)")
        if len(meta_desc) > 155:
            meta_desc = meta_desc[:152] + "..."
        # ── Banned phrase check ─────────────────────────────
        desc_lower = desc.lower()
        for phrase in _BANNED:
            if phrase in desc_lower:
                raise RuntimeError(f"Banned phrase detected: '{phrase}' — regenerating")
        return {
            "title":       title,
            "h1":          h1,
            "meta_desc":   meta_desc,
            "alt_text":    alt_text,
            "tags":        tags,
            "description": desc,
        }


    # ── Attempt 1: Vision model (sees the actual image) ─────
    if image_url:
        last_err = None
        for attempt in range(1, retries + 1):
            try:
                r = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}",
                             "Content-Type": "application/json"},
                    json={
                        "model":           GROQ_VISION_MODEL,
                        "temperature":     0.5,
                        "max_tokens":      3000,
                        "response_format": {"type": "json_object"},
                        "messages":        _make_messages(use_image=True),
                    },
                    timeout=120,
                )
                if r.status_code == 429:
                    retry_after = float(r.headers.get("retry-after", "60"))
                    print(f"\n    [GROQ-V] 429 — waiting {retry_after:.0f}s ...", flush=True)
                    time.sleep(retry_after + 2)
                    continue
                r.raise_for_status()
                result = _parse_seo(r.json()["choices"][0]["message"]["content"].strip())
                return result

            except Exception as e:
                last_err = e
                if attempt < retries:
                    wait = GROQ_SLEEP_SEC * attempt
                    print(f"\n    [GROQ-V] attempt {attempt}/{retries} failed: {e}"
                          f" — retry in {wait:.0f}s", flush=True)
                    time.sleep(wait)

        print(f"\n    [GROQ-V] Vision failed ({last_err}) — falling back to text-only ...",
              flush=True)

    # ── Fallback: text-only models (no image) ───────────────
    for model_idx, model in enumerate(GROQ_MODELS):
        last_err = None
        for attempt in range(1, retries + 1):
            try:
                r = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}",
                             "Content-Type": "application/json"},
                    json={
                        "model":           model,
                        "temperature":     0.5,
                        "max_tokens":      3000,
                        "response_format": {"type": "json_object"},
                        "messages":        _make_messages(use_image=False),
                    },
                    timeout=120,
                )
                if r.status_code == 429:
                    retry_after = float(r.headers.get("retry-after", "60"))
                    print(f"\n    [GROQ-T] 429 on {model} — waiting {retry_after:.0f}s ...",
                          flush=True)
                    time.sleep(retry_after + 2)
                    continue
                r.raise_for_status()
                result = _parse_seo(r.json()["choices"][0]["message"]["content"].strip())
                if model_idx > 0:
                    print(f"    [GROQ-T] used fallback model: {model}", flush=True)
                return result

            except Exception as e:
                last_err = e
                if attempt < retries:
                    wait = GROQ_SLEEP_SEC * attempt * 2
                    print(f"\n    [GROQ-T] attempt {attempt}/{retries} on {model} failed: {e}"
                          f" — retry in {wait:.0f}s", flush=True)
                    time.sleep(wait)

        print(f"\n    [GROQ-T] {model} exhausted after {retries} attempts: {last_err}",
              flush=True)

    raise RuntimeError(f"All Groq models failed. Last: {last_err}")




# ══════════════════════════════════════════════════════════════
# ULTRADATA XLSX  READ / APPEND
# ══════════════════════════════════════════════════════════════

def _read_ultradata_rows(xlsx_path: Path) -> List[Dict[str, str]]:
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
    # Optional columns — graceful fallback if not present
    optional = ["category", "subcategory"]
    out = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        row = {h: ("" if r[idx[h]] is None else str(r[idx[h]]).strip()) for h in needed}
        for h in optional:
            row[h] = ("" if h not in idx or r[idx[h]] is None else str(r[idx[h]]).strip())
        if row["filename"] and row["subject_name"]:
            out.append(row)
    return out


def _append_ultradata_rows(xlsx_path: Path, new_rows: List[Dict[str, str]]) -> int:
    import openpyxl
    from openpyxl import Workbook
    headers = [
        "date_added", "subject_name", "category", "subcategory",
        "filename", "png_file_id", "webp_file_id", "download_url", "preview_url",
    ]
    if xlsx_path.exists():
        wb = openpyxl.load_workbook(str(xlsx_path))
        ws = wb.active
        if ws.max_row < 1:
            ws.append(headers)
    else:
        wb = Workbook()
        ws = wb.active
        ws.append(headers)
    appended = 0
    for r in new_rows:
        ws.append([
            r.get("date_added", _today()),
            r.get("subject_name", ""),
            r.get("category", ""),
            r.get("subcategory", ""),
            r.get("filename", ""),
            r.get("png_file_id", ""),
            r.get("webp_file_id", ""),
            r.get("download_url", ""),
            r.get("preview_url", ""),
        ])
        appended += 1
    wb.save(str(xlsx_path))
    return appended


# ══════════════════════════════════════════════════════════════
# GOOGLE DRIVE HELPERS
# ══════════════════════════════════════════════════════════════

def _drive_token() -> str:
    import requests
    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id":     os.environ.get("GOOGLE_CLIENT_ID", ""),
            "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
            "refresh_token": os.environ.get("GOOGLE_REFRESH_TOKEN", ""),
            "grant_type":    "refresh_token",
        },
        timeout=30,
    )
    r.raise_for_status()
    d = r.json()
    if "access_token" not in d:
        raise RuntimeError(f"Drive token error: {d}")
    return d["access_token"]


def _drive_folder(token: str, name: str, parent: str = "") -> str:
    import requests
    h = {"Authorization": f"Bearer {token}"}
    q = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent:
        q += f" and '{parent}' in parents"
    r = requests.get("https://www.googleapis.com/drive/v3/files",
                     headers=h,
                     params={"q": q, "fields": "files(id,name)"},
                     timeout=30)
    r.raise_for_status()
    files = r.json().get("files", [])
    if files:
        return files[0]["id"]
    meta = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent:
        meta["parents"] = [parent]
    c = requests.post("https://www.googleapis.com/drive/v3/files",
                      headers={**h, "Content-Type": "application/json"},
                      json=meta, timeout=30)
    c.raise_for_status()
    return c.json()["id"]


def _drive_list_png(token: str, folder_id: str) -> List[Dict[str, str]]:
    import requests
    h       = {"Authorization": f"Bearer {token}"}
    q       = (f"'{folder_id}' in parents and trashed=false and "
               f"(mimeType='image/png' or name contains '.png')")
    results = []
    page_token = None
    while True:
        params = {"q": q, "fields": "nextPageToken,files(id,name,parents,mimeType)",
                  "pageSize": 1000}
        if page_token:
            params["pageToken"] = page_token
        r = requests.get("https://www.googleapis.com/drive/v3/files",
                         headers=h, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        results.extend(data.get("files", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return results


def _drive_list_folders(token: str, folder_id: str) -> List[Dict[str, str]]:
    import requests
    h       = {"Authorization": f"Bearer {token}"}
    q       = (f"'{folder_id}' in parents and trashed=false and "
               f"mimeType='application/vnd.google-apps.folder'")
    results = []
    page_token = None
    while True:
        params = {"q": q, "fields": "nextPageToken,files(id,name)",
                  "pageSize": 1000}
        if page_token:
            params["pageToken"] = page_token
        r = requests.get("https://www.googleapis.com/drive/v3/files",
                         headers=h, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        results.extend(data.get("files", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return results


def _drive_download(token: str, file_id: str) -> bytes:
    import requests
    r = requests.get(f"https://www.googleapis.com/drive/v3/files/{file_id}",
                     headers={"Authorization": f"Bearer {token}"},
                     params={"alt": "media"}, timeout=120)
    r.raise_for_status()
    return r.content


def _drive_upload(token: str, folder_id: str, name: str,
                  data: bytes, mime: str) -> Dict[str, str]:
    import requests
    h        = {"Authorization": f"Bearer {token}"}
    boundary = "----UltraPNGS2"
    metadata = json.dumps({"name": name, "parents": [folder_id]})
    body = (
        f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{metadata}\r\n"
        f"--{boundary}\r\nContent-Type: {mime}\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--".encode()
    r = requests.post(
        "https://www.googleapis.com/upload/drive/v3/files"
        "?uploadType=multipart&fields=id,name",
        headers={**h, "Content-Type": f'multipart/related; boundary="{boundary}"'},
        data=body, timeout=120)
    r.raise_for_status()
    return r.json()


def _drive_share(token: str, file_id: str) -> None:
    import requests
    requests.post(
        f"https://www.googleapis.com/drive/v3/files/{file_id}/permissions",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"role": "reader", "type": "anyone"}, timeout=30)


def _drive_move(token: str, file_id: str,
                add_parent: str, remove_parent: str) -> None:
    import requests
    r = requests.patch(
        f"https://www.googleapis.com/drive/v3/files/{file_id}",
        headers={"Authorization": f"Bearer {token}"},
        params={"addParents": add_parent, "removeParents": remove_parent,
                "fields": "id"}, timeout=30)
    r.raise_for_status()


def _preview_url(fid: str, size: int = 800) -> str:
    return f"https://lh3.googleusercontent.com/d/{fid}=s{size}"


def _download_url(fid: str) -> str:
    return (f"https://drive.usercontent.google.com/download"
            f"?id={fid}&export=download&authuser=0")


# ══════════════════════════════════════════════════════════════
# PREVIEW IMAGE MAKER  (checkerboard bg + watermark)
# ══════════════════════════════════════════════════════════════

def _make_webp_preview(png_bytes: bytes) -> bytes:
    from PIL import Image, ImageDraw, ImageFont
    with Image.open(io.BytesIO(png_bytes)).convert("RGBA") as img_rgba:
        w, h = img_rgba.size
        if max(w, h) > 800:
            ratio    = 800 / max(w, h)
            img_rgba = img_rgba.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        w, h = img_rgba.size
        bg   = Image.new("RGB", (w, h), (255, 255, 255))
        drw  = ImageDraw.Draw(bg)
        for y in range(0, h, 20):
            for x in range(0, w, 20):
                if (y // 20 + x // 20) % 2 == 1:
                    drw.rectangle([x, y, x + 20, y + 20], fill=(232, 232, 232))
        bg.paste(img_rgba.convert("RGB"), mask=img_rgba.split()[3])
        try:
            fnt = ImageFont.truetype("arial.ttf", 13)
        except Exception:
            fnt = ImageFont.load_default()
        wm_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        wm_draw  = ImageDraw.Draw(wm_layer)
        for y in range(-h, h + 110, 110):
            for x in range(-w, w + 110, 110):
                wm_draw.text((x, y), WATERMARK_TEXT, fill=(0, 0, 0, 42), font=fnt)
        wm_rot  = wm_layer.rotate(-30, expand=False)
        bg_rgba = bg.convert("RGBA")
        bg_rgba.alpha_composite(wm_rot)
        out = bg_rgba.convert("RGB")
        d2  = ImageDraw.Draw(out)
        d2.rectangle([0, h - 36, w, h], fill=(13, 13, 20))
        d2.text((w // 2 - 72, h - 26), WATERMARK_TEXT, fill=(245, 166, 35), font=fnt)
        buf = io.BytesIO()
        out.save(buf, "WEBP", quality=82, method=4)
        return buf.getvalue()


# ══════════════════════════════════════════════════════════════
# MANUAL DROP PROCESSOR
# ══════════════════════════════════════════════════════════════

def _process_manual_drop_and_update_ultradata(xlsx_path: Path) -> List[Dict[str, str]]:
    token          = _drive_token()
    manual_root    = _drive_folder(token, "manual drop")
    png_root       = _drive_folder(token, "png_library_images")
    prev_root      = _drive_folder(token, "png_library_previews")
    library_manual = _drive_folder(token, "manual_drop", png_root)
    preview_manual = _drive_folder(token, "manual_drop", prev_root)

    files = _drive_list_png(token, manual_root)
    if not files:
        print("  Manual drop: no new files found.")
        return []

    print(f"  Manual drop: {len(files)} file(s) found.")
    new_rows: List[Dict[str, str]] = []
    for f in files:
        fid        = f["id"]
        name       = f.get("name", "untitled.png")
        old_parent = (f.get("parents") or [manual_root])[0]
        print(f"    Processing: {name}", end=" ", flush=True)
        try:
            png_bytes  = _drive_download(token, fid)
            webp_bytes = _make_webp_preview(png_bytes)
            webp       = _drive_upload(token, preview_manual,
                                       Path(name).stem + ".webp",
                                       webp_bytes, "image/webp")
            _drive_share(token, webp["id"])
            _drive_move(token, fid, library_manual, old_parent)
            _drive_share(token, fid)
            subject = Path(name).stem.replace("_", " ").replace("-", " ").title()
            new_rows.append({
                "date_added":   _today(),
                "subject_name": subject,
                "category":     "manual_drop",
                "subcategory":  "manual_drop",
                "filename":     name,
                "png_file_id":  fid,
                "webp_file_id": webp["id"],
                "download_url": _download_url(fid),
                "preview_url":  _preview_url(webp["id"], 800),
            })
            print("✓")
        except Exception as e:
            print(f"✗ SKIP ({e})")

    if new_rows:
        _append_ultradata_rows(xlsx_path, new_rows)
        print(f"  Manual drop: appended {len(new_rows)} row(s) to ultradata.xlsx")
    return new_rows


# ══════════════════════════════════════════════════════════════
# LIBRARY FILE SCANNER
# ══════════════════════════════════════════════════════════════

def _library_file_names(token: str) -> set:
    """Walk all sub-folders of png_library_images and collect filenames."""
    png_root = _drive_folder(token, "png_library_images")
    names    = set()
    queue    = [png_root]
    while queue:
        current = queue.pop(0)
        for f in _drive_list_png(token, current):
            names.add((f.get("name") or "").strip())
        for sf in _drive_list_folders(token, current):
            queue.append(sf["id"])
    return names


# ══════════════════════════════════════════════════════════════
# REPO 2  (clone / load / save / push)
# ══════════════════════════════════════════════════════════════

@dataclass
class Repo2Config:
    token:    str
    slug:     str
    data_dir: str = "data"


def _clone_repo2(cfg: Repo2Config, workdir: Path) -> Path:
    repo_url = f"https://x-access-token:{cfg.token}@github.com/{cfg.slug}.git"
    if workdir.exists():
        subprocess.run(["git", "remote", "set-url", "origin", repo_url],
                       cwd=str(workdir), check=False)
        subprocess.run(["git", "pull", "--rebase", "--autostash"],
                       cwd=str(workdir), check=False)
        return workdir
    subprocess.run(["git", "clone", "--depth", "1", repo_url, str(workdir)],
                   check=True)
    return workdir


def _load_repo2_entries(repo2_dir: Path,
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


def _save_repo2_files(repo2_dir: Path, data_dir: str,
                      file_entries: Dict[Path, List[Dict[str, Any]]]) -> None:
    for f, arr in file_entries.items():
        tmp = f.with_suffix(f.suffix + ".tmp")
        tmp.write_text(json.dumps(arr, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(f)


def _ensure_capacity(files: List[Path], repo2_dir: Path,
                     data_dir: str, max_entries: int) -> Path:
    last = files[-1]
    try:
        arr = json.loads(last.read_text(encoding="utf-8"))
        n   = len(arr) if isinstance(arr, list) else 0
    except Exception:
        n = 0
    if n < max_entries:
        return last
    m   = re.match(r"json(\d+)\.json$", last.name)
    nxt = (int(m.group(1)) + 1) if m else (len(files) + 1)
    newf = repo2_dir / data_dir / f"json{nxt}.json"
    newf.write_text("[]", encoding="utf-8")
    files.append(newf)
    return newf


def _commit_push_repo2(repo2_dir: Path, cfg: Repo2Config, added: int) -> None:
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"],
                   cwd=str(repo2_dir), check=True)
    subprocess.run(["git", "config", "user.email",
                    "github-actions[bot]@users.noreply.github.com"],
                   cwd=str(repo2_dir), check=True)
    subprocess.run(["git", "add", cfg.data_dir], cwd=str(repo2_dir), check=True)
    diff = subprocess.run(["git", "diff", "--staged", "--quiet"], cwd=str(repo2_dir))
    if diff.returncode == 0:
        print("  Repo2: nothing to commit — already up-to-date.")
        return
    subprocess.run(["git", "commit", "-m", f"seo: add {added} entries from ultradata"],
                   cwd=str(repo2_dir), check=True)
    result = subprocess.run(["git", "push"], cwd=str(repo2_dir),
                            capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [ERROR] git push failed:\n{result.stderr}")
        raise RuntimeError("Repo2 push failed — check REPO2_TOKEN permissions.")
    print(f"  Repo2: pushed {added} new SEO entries ✓")


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def main() -> None:
    root = Path(__file__).resolve().parent
    xlsx = root / ULTRADATA_XLSX
    if not xlsx.exists():
        raise SystemExit(f"Missing {ULTRADATA_XLSX} in repo root")

    repo2_token = os.environ.get("REPO2_TOKEN", "").strip()
    repo2_slug  = os.environ.get("REPO2_SLUG",  "").strip()
    if not repo2_token or not repo2_slug:
        raise SystemExit("Missing REPO2_TOKEN or REPO2_SLUG")

    max_per_file   = int(os.environ.get("REPO2_MAX_PER_JSON", "200"))
    run_mode       = os.environ.get("S2_RUN_MODE",        "scheduled").strip().lower()
    batch_size     = int(os.environ.get("S2_BATCH_SIZE",     "220").strip())
    scheduled_days = int(os.environ.get("S2_SCHEDULED_DAYS", "200").strip())

    print("=" * 62)
    print("  Section 2 — SEO JSON Builder")
    print(f"  Mode           : {run_mode}")
    print(f"  Batch size     : {batch_size}  |  Instant cap: {INSTANT_CAP}")
    print(f"  Scheduled days : {scheduled_days}")
    print(f"  GROQ sleep     : {GROQ_SLEEP_SEC}s  (~{60/GROQ_SLEEP_SEC:.1f} calls/min — safe)")
    print(f"  GROQ models    : {' → '.join(GROQ_MODELS)}")
    print("=" * 62)

    # ── STEP 1: Manual drop ──────────────────────────────────
    print("\n[Step 1] Manual drop scan ...")
    _process_manual_drop_and_update_ultradata(xlsx)

    # ── STEP 2: Read ultradata rows ──────────────────────────
    print("\n[Step 2] Reading ultradata.xlsx ...")
    all_rows = _read_ultradata_rows(xlsx)
    print(f"  Total rows in xlsx : {len(all_rows)}")
    if not all_rows:
        print("  No rows — nothing to do.")
        return

    # ── STEP 3: PNG availability check ──────────────────────
    # Rows in ultradata.xlsx where PNG is NOT in Drive library
    # are SKIPPED — prevents broken pages with missing images.
    # They will be picked up automatically once PNG arrives in Drive.
    print("\n[Step 3] Checking Drive png_library_images ...")
    drive_token   = _drive_token()
    library_names = _library_file_names(drive_token)
    print(f"  PNG files in Drive : {len(library_names)}")

    rows_with_png    = [r for r in all_rows if r.get("filename", "") in library_names]
    rows_missing_png = [r for r in all_rows if r.get("filename", "") not in library_names]

    if rows_missing_png:
        print(f"  ⚠  {len(rows_missing_png)} row(s) skipped — PNG not in Drive library "
              f"(will retry once PNG arrives):")
        for r in rows_missing_png[:10]:
            print(f"       • {r['filename']}  ({r['subject_name']})")
        if len(rows_missing_png) > 10:
            print(f"       ... and {len(rows_missing_png) - 10} more")

    print(f"  Rows with PNG ready: {len(rows_with_png)}")
    if not rows_with_png:
        print("  No valid rows with PNG — nothing to process.")
        return

    # ── STEP 4: Clone repo2 & find pending ──────────────────
    print("\n[Step 4] Cloning Repo2 ...")
    cfg       = Repo2Config(token=repo2_token, slug=repo2_slug)
    repo2_dir = _clone_repo2(cfg, root / "_repo2_work")

    existing, files = _load_repo2_entries(repo2_dir, cfg.data_dir)
    missing = [r for r in rows_with_png if r["filename"] not in existing]

    print(f"  Repo2 existing SEO : {len(existing)}")
    print(f"  Rows with PNG      : {len(rows_with_png)}")
    print(f"  Pending SEO        : {len(missing)}")

    if not missing:
        print("\n  All entries have SEO — nothing to add.")
        return

    # ── STEP 5: Apply batch / instant limit ─────────────────
    total_pending = len(missing)
    if run_mode == "instant":
        if len(missing) > INSTANT_CAP:
            print(f"\n⚠  Instant mode: capping at {INSTANT_CAP} of {len(missing)} pending.")
            print(f"   Re-run to continue. (GitHub Actions 6-hr limit)")
            missing = missing[:INSTANT_CAP]
        else:
            print(f"\n▶  Instant mode: processing all {len(missing)} pending entries.")
    else:
        if len(missing) > batch_size:
            print(f"\n▶  Scheduled mode: {batch_size} of {len(missing)} pending.")
            missing = missing[:batch_size]
        else:
            print(f"\n▶  Scheduled mode: all remaining {len(missing)} entries.")

    # ── STEP 6: Generate SEO ─────────────────────────────────
    est_min = len(missing) * GROQ_SLEEP_SEC / 60
    print(f"\n[Step 5] Generating SEO for {len(missing)} item(s) ...")
    print(f"         Estimated time: ~{est_min:.1f} minutes\n")

    file_entries: Dict[Path, List[Dict[str, Any]]] = {}
    for f in files:
        try:
            arr = json.loads(f.read_text(encoding="utf-8"))
            file_entries[f] = arr if isinstance(arr, list) else []
        except Exception:
            file_entries[f] = []

    added = 0
    for i, r in enumerate(missing, 1):
        subject     = r["subject_name"]
        preview_url = r.get("preview_url", "")
        print(f"  [{i}/{len(missing)}] {subject} ...", end=" ", flush=True)
        try:
            seo    = _groq_vision_seo(subject, preview_url)
            target = _ensure_capacity(files, repo2_dir, cfg.data_dir, max_per_file)
            if target not in file_entries:
                file_entries[target] = []
            # slug: unique per filename (subject-slug + short filename suffix)
            base_slug = re.sub(r"[^a-z0-9]+", "-",
                               subject.lower()).strip("-") or "untitled"
            fn_id     = re.sub(r"[^0-9]", "", r["filename"])[-4:] or "0"
            slug      = f"{base_slug}-{fn_id}"
            file_entries[target].append({
                "category":     r.get("category", ""),
                "subcategory":  r.get("subcategory", ""),
                "subject_name": subject,
                "filename":     r["filename"],
                "slug":         slug,
                "download_url":    r["download_url"],
                "preview_url":     preview_url,
                "webp_preview_url": r.get("webp_preview_url", preview_url),
                "title":           seo["title"],
                "h1":              seo["h1"],
                "meta_desc":       seo["meta_desc"],
                "alt_text":        seo["alt_text"],
                "tags":            seo["tags"],
                "description":     seo["description"],
                "word_count":      _word_count(seo["description"]),
                "date_added":      r.get("date_added", _today()),
            })
            added += 1
            wc = _word_count(seo["description"])
            tw = _word_count(seo["title"])
            print(f"✓  title={tw}w  desc={wc}w")
        except Exception as e:
            print(f"✗ SKIP ({e})")

        # Safe 15s sleep between calls — ~4 calls/min within 6,000 TPM free limit
        if i < len(missing):
            time.sleep(GROQ_SLEEP_SEC)

    # ── STEP 7: Save & push repo2 ───────────────────────────
    print(f"\n[Step 6] Saving & pushing {added} entries to Repo2 ...")
    _save_repo2_files(repo2_dir, cfg.data_dir, file_entries)
    if added > 0:
        _commit_push_repo2(repo2_dir, cfg, added)
    else:
        print("  Nothing added — skipping push.")

    # ── STEP 8: Update progress tracker ─────────────────────
    prev_total = _read_s2_tracker(root)
    new_total  = prev_total + added
    _write_s2_tracker(root, new_total)

    print("\n" + "=" * 62)
    print(f"  Section 2 complete — added {added} SEO entries.")
    print(f"  Total SEO entries to date : {new_total}")
    if rows_missing_png:
        print(f"  ⚠  PNG-missing rows skipped : {len(rows_missing_png)}"
              f"  (auto-retried next run once PNG arrives in Drive)")
    if run_mode == "scheduled" and total_pending > len(missing):
        remaining = total_pending - added
        if remaining > 0:
            days_left = (remaining + batch_size - 1) // batch_size
            print(f"  Remaining pending : {remaining}  (~{days_left} more scheduled runs)")
    print("=" * 62)


if __name__ == "__main__":
    main()
