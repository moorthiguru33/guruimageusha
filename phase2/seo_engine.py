"""
UltraPNG — Phase 2 SEO Engine
Runs in GitHub Actions (no GPU required)
Sheets read → Drive PNG check → Manual drop scan → Groq dual-model SEO → Repo2 push → Sheets update
"""
import os, sys, json, time, re, io, subprocess, shutil, hashlib
from pathlib import Path
from datetime import datetime
import requests as req
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Secrets (from GitHub Actions env) ─────────────────────────
GOOGLE_CLIENT_ID     = os.environ["GOOGLE_CLIENT_ID"]
GOOGLE_CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]
GOOGLE_REFRESH_TOKEN = os.environ["GOOGLE_REFRESH_TOKEN"]
GOOGLE_SHEETS_ID     = os.environ["GOOGLE_SHEETS_ID"]
DRIVE_ROOT_FOLDER_ID = os.environ["DRIVE_ROOT_FOLDER_ID"]
GITHUB_TOKEN_REPO2   = os.environ["GITHUB_TOKEN_REPO2"]
GITHUB_REPO2         = os.environ["GITHUB_REPO2"]
GROQ_API_KEY         = os.environ["GROQ_API_KEY"]

WATERMARK_TEXT = "www.ultrapng.com"
SITE_URL       = "https://www.ultrapng.com"
SITE_NAME      = "UltraPNG"
WORK           = Path("/tmp/ultrapng_phase2")
REPO2_DIR      = WORK / "repo2"
WORK.mkdir(parents=True, exist_ok=True)

# ── Logging ────────────────────────────────────────────────────
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

# ── Google OAuth ───────────────────────────────────────────────
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

def auth():
    return {"Authorization": f"Bearer {get_token()}"}

# ── Google Drive ───────────────────────────────────────────────
def drive_get_folder_id(name, parent_id):
    q = (f"name='{name}' and mimeType='application/vnd.google-apps.folder'"
         f" and '{parent_id}' in parents and trashed=false")
    r = req.get("https://www.googleapis.com/drive/v3/files",
                headers=auth(), params={"q": q, "fields": "files(id)"}, timeout=30)
    files = r.json().get("files", [])
    if files:
        return files[0]["id"]
    r = req.post("https://www.googleapis.com/drive/v3/files",
                 headers={**auth(), "Content-Type": "application/json"},
                 json={"name": name, "mimeType": "application/vnd.google-apps.folder",
                       "parents": [parent_id]}, timeout=30)
    return r.json()["id"]

def drive_list_folder(folder_id):
    """Returns [{id, name}] for all files in folder (not folders)."""
    items, page_token = [], None
    while True:
        params = {
            "q":      f"'{folder_id}' in parents and mimeType!='application/vnd.google-apps.folder' and trashed=false",
            "fields": "files(id,name),nextPageToken",
            "pageSize": 1000,
        }
        if page_token:
            params["pageToken"] = page_token
        data = req.get("https://www.googleapis.com/drive/v3/files",
                       headers=auth(), params=params, timeout=30).json()
        items.extend(data.get("files", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return items

def _check_one_file(file_id):
    try:
        r = req.get(f"https://www.googleapis.com/drive/v3/files/{file_id}",
                    headers=auth(), params={"fields": "id,trashed"}, timeout=10)
        if r.status_code == 200:
            return file_id, not r.json().get("trashed", False)
        return file_id, False
    except Exception:
        return file_id, True  # Assume exists on timeout

def batch_check_files_exist(file_ids):
    """Parallel Drive existence check — 10 concurrent threads."""
    results = {}
    ids = [f for f in file_ids if f]
    if not ids:
        return results
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(_check_one_file, fid): fid for fid in ids}
        for fut in as_completed(futures):
            fid, exists = fut.result()
            results[fid] = exists
    return results

def drive_download_bytes(file_id):
    r = req.get(
        f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media",
        headers=auth(), timeout=60,
    )
    r.raise_for_status()
    return r.content

def drive_upload(folder_id, name, data_bytes, mime="image/png", retries=3):
    for attempt in range(1, retries + 1):
        try:
            boundary = "UltraPNGBoundary"
            meta     = json.dumps({"name": name, "parents": [folder_id]})
            body = (
                f"--{boundary}\r\nContent-Type: application/json\r\n\r\n{meta}\r\n"
                f"--{boundary}\r\nContent-Type: {mime}\r\n\r\n"
            ).encode() + data_bytes + f"\r\n--{boundary}--".encode()
            r = req.post(
                "https://www.googleapis.com/upload/drive/v3/files"
                "?uploadType=multipart&fields=id,name",
                headers={**auth(), "Content-Type": f'multipart/related; boundary="{boundary}"'},
                data=body, timeout=120,
            )
            if r.ok:
                return r.json()
            raise RuntimeError(f"HTTP {r.status_code}")
        except Exception as e:
            if attempt < retries:
                time.sleep(5 * attempt)
            else:
                raise

def drive_share(file_id):
    try:
        req.post(f"https://www.googleapis.com/drive/v3/files/{file_id}/permissions",
                 headers={**auth(), "Content-Type": "application/json"},
                 json={"role": "reader", "type": "anyone"}, timeout=30)
    except Exception:
        pass

def drive_delete(file_id):
    try:
        req.delete(f"https://www.googleapis.com/drive/v3/files/{file_id}",
                   headers=auth(), timeout=30)
    except Exception:
        pass

def preview_url(fid, size=800):
    return f"https://lh3.googleusercontent.com/d/{fid}=s{size}"

def download_url(fid):
    return f"https://drive.usercontent.google.com/download?id={fid}&export=download&authuser=0"

# ── Google Sheets ──────────────────────────────────────────────
# Columns: filename | subject_name | category | png_file_id | webp_file_id |
#          png_url  | webp_url     | seo_done | status      | date_added
# Index:      0           1            2           3              4
#             5           6              7          8              9

SHEET_RANGE = "Sheet1"

def sheets_read_all():
    """One API call — returns list of dicts, one per row (skip header)."""
    url = (f"https://sheets.googleapis.com/v4/spreadsheets/{GOOGLE_SHEETS_ID}"
           f"/values/{SHEET_RANGE}")
    r   = req.get(url, headers={"Authorization": f"Bearer {get_token()}"}, timeout=30)
    r.raise_for_status()
    values = r.json().get("values", [])
    if len(values) < 2:
        return []
    headers = values[0]
    rows = []
    for i, row in enumerate(values[1:], start=2):  # start=2 for 1-indexed Sheets row
        padded = row + [""] * (len(headers) - len(row))
        rows.append({
            "row_num": i,
            **dict(zip(headers, padded)),
        })
    return rows

def sheets_batch_update(updates):
    """
    updates: list of {"row": int, "col": int (0-indexed), "value": str}
    Sends ONE batchUpdate call.
    """
    if not updates:
        return
    # Convert to Sheets A1 notation
    col_letters = "ABCDEFGHIJ"
    value_ranges = []
    for u in updates:
        col  = col_letters[u["col"]]
        cell = f"{SHEET_RANGE}!{col}{u['row']}"
        value_ranges.append({"range": cell, "values": [[u["value"]]]})

    url = (f"https://sheets.googleapis.com/v4/spreadsheets/{GOOGLE_SHEETS_ID}"
           "/values:batchUpdate")
    req.post(url,
             headers={"Authorization": f"Bearer {get_token()}",
                      "Content-Type": "application/json"},
             json={"valueInputOption": "USER_ENTERED", "data": value_ranges},
             timeout=60)

def sheets_append_rows(rows):
    url = (f"https://sheets.googleapis.com/v4/spreadsheets/{GOOGLE_SHEETS_ID}"
           f"/values/{SHEET_RANGE}:append")
    req.post(url,
             headers={"Authorization": f"Bearer {get_token()}",
                      "Content-Type": "application/json"},
             params={"valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"},
             json={"values": rows}, timeout=30)

# ── WebP Generator (for repair / manual images) ────────────────
def make_webp_bytes(png_bytes):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    w, h = img.size
    if max(w, h) > 800:
        scale = 800 / max(w, h)
        img   = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    w, h = img.size

    bg  = Image.new("RGB", (w, h), (255, 255, 255))
    drw = ImageDraw.Draw(bg)
    for ry in range(0, h, 20):
        for cx in range(0, w, 20):
            if (ry // 20 + cx // 20) % 2:
                drw.rectangle([cx, ry, cx + 20, ry + 20], fill=(232, 232, 232))
    bg.paste(img.convert("RGB"), mask=img.split()[3])

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
    wm  = wm.rotate(-30, expand=False)
    out = bg.convert("RGBA")
    out.alpha_composite(wm)
    out = out.convert("RGB")

    try:
        fnt2 = ImageFont.truetype(
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 15)
    except Exception:
        fnt2 = fnt
    fd = ImageDraw.Draw(out)
    fd.rectangle([0, h - 36, w, h], fill=(13, 13, 20))
    fd.text((w // 2 - 72, h - 26), WATERMARK_TEXT, fill=(245, 166, 35), font=fnt2)

    buf = io.BytesIO()
    out.save(buf, "WEBP", quality=82, method=4)
    return buf.getvalue(), w, h

# ── Manual Drop Detection ──────────────────────────────────────
_KEYWORD_CATEGORY = [
    ("biryani|curry|rice|dosa|idli|chapati|roti|sambar|dal|paneer|masala|korma", "indian_foods"),
    ("pizza|burger|pasta|noodle|sushi|sandwich|taco|salad|soup",                  "world_foods"),
    ("apple|mango|banana|grape|orange|strawberry|watermelon|fruit",               "fruits"),
    ("tomato|onion|carrot|potato|spinach|broccoli|vegetable|veggie",              "vegetables"),
    ("rose|lotus|sunflower|jasmine|tulip|daisy|orchid|flower",                    "flowers"),
    ("dog|cat|tiger|lion|elephant|horse|rabbit|bird|eagle|parrot|animal",         "animals"),
    ("car|bike|truck|bus|motorcycle|vehicle|scooter|auto",                         "vehicles"),
    ("ring|necklace|earring|bracelet|bangle|jewel|gold|diamond",                  "jewellery"),
    ("shirt|saree|dress|kurta|lehenga|cloth|fashion|clothing",                    "clothing"),
    ("phone|laptop|computer|tablet|earphone|speaker|electronic",                  "electronics"),
    ("chicken|fish|meat|prawn|shrimp|seafood|egg|poultry",                        "raw_meat"),
    ("coffee|tea|juice|drink|water|milk|beverage|cola|soda",                      "beverages"),
    ("shoe|sandal|slipper|boot|heel|footwear",                                    "footwear"),
]

def detect_category(filename):
    name = re.sub(r"[_\-\s]+", " ", Path(filename).stem.lower())
    for pattern, cat in _KEYWORD_CATEGORY:
        if re.search(pattern, name):
            return cat
    return "general"

def filename_to_subject(filename):
    stem  = Path(filename).stem
    words = re.split(r"[_\-\s]+", stem)
    # Remove trailing numbers (e.g., "tiger_001" → "Tiger")
    words = [w for w in words if not w.isdigit()]
    return " ".join(w.capitalize() for w in words if w)

# ── Groq SEO Generation ────────────────────────────────────────
_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_H   = {"Authorization": f"Bearer {GROQ_API_KEY}",
              "Content-Type": "application/json"}

# Perspective angles for uniqueness — chosen by subject hash
_ANGLES = [
    "Start by describing the precise color, texture, and visual composition of this specific image.",
    "Start by explaining the artistic style and what makes this image visually stand out.",
    "Start by describing the ideal design scenario where this PNG would be the perfect choice.",
    "Start by discussing the cultural or contextual significance of this subject.",
    "Start with a bold opening about why this is the definitive PNG resource for this subject.",
]

def _get_angle(filename):
    return _ANGLES[int(hashlib.md5(filename.encode()).hexdigest(), 16) % len(_ANGLES)]

_SYS_FAST = (
    "You are a professional SEO writer for UltraPNG.com — a free transparent PNG library. "
    "Return ONLY valid JSON, no markdown. Be specific, unique, creative. "
    "Never write generic AI-sounding phrases. Write like a human expert."
)

_SYS_DESC = (
    "You are a senior content writer for UltraPNG.com specializing in SEO descriptions. "
    "Write 100% unique, human-quality content. Never start two descriptions the same way. "
    "Never use generic phrases like 'high-quality' or 'perfect for designers'. "
    "Describe specific visual qualities. Write naturally as a subject expert would."
)

def _groq_call(model, messages, max_tokens=600, retries=5):
    backoff = 8
    for attempt in range(1, retries + 1):
        try:
            r = req.post(_GROQ_URL, headers=_GROQ_H, json={
                "model": model, "messages": messages, "max_tokens": max_tokens,
                "temperature": 0.85, "top_p": 0.95,
            }, timeout=60)
            if r.status_code == 429:
                wait = int(r.headers.get("retry-after", backoff))
                log(f"  Groq 429 — wait {wait}s (attempt {attempt})")
                time.sleep(wait)
                backoff = min(backoff * 2, 120)
                continue
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            if attempt < retries:
                time.sleep(backoff)
                backoff = min(backoff * 2, 120)
            else:
                raise
    return ""

def slugify(s, max_len=55):
    s = re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")
    if len(s) > max_len:
        cut = s[:max_len]
        idx = cut.rfind("-")
        s   = cut[:idx] if idx > max_len // 2 else cut
    return s or "untitled"

def generate_seo(subject, category, filename):
    """
    Returns dict with title, slug, h1, meta_desc, tags, description.
    Uses llama-3.1-8b-instant for quick fields, llama-3.3-70b-versatile for description.
    """
    slug_base = slugify(subject)
    angle     = _get_angle(filename)

    # ── Fast model: title, slug, h1, meta, tags ────────────────
    fast_prompt = f"""Subject: {subject}
Category: {category}
Slug base: {slug_base}

Return JSON with exactly these keys:
{{
  "title": "25-35 word SEO title — include specific visual descriptor + {subject} + Transparent PNG Free Download | UltraPNG",
  "slug": "max 55 chars, include 2 visual words + png",
  "h1": "unique 10-15 word heading describing this specific image",
  "meta_desc": "max 155 chars — describe THIS image uniquely, mention use case",
  "tags": "20 comma-separated tags — mix of: subject, color terms, style, use case, canva, flex banner, transparent png, free download, ultrapng, HD"
}}

Rules:
- Title MUST include a specific visual word (color/style/texture) about {subject}
- Slug must NOT be just "{slug_base}-png" — add 2 specific visual words
- h1 must differ from title
- Tags must include at least 6 specific descriptive terms"""

    fast_raw = _groq_call(
        "llama-3.1-8b-instant",
        [{"role": "system", "content": _SYS_FAST},
         {"role": "user",   "content": fast_prompt}],
        max_tokens=500,
    )

    fast = {}
    try:
        j0, j1 = fast_raw.find("{"), fast_raw.rfind("}") + 1
        fast = json.loads(fast_raw[j0:j1]) if j0 >= 0 else {}
    except Exception:
        pass

    # ── Quality model: 300+ word description ──────────────────
    desc_prompt = f"""Write a 350-400 word SEO description for a {subject} transparent PNG image on UltraPNG.com.
Category: {category}

{angle}

Structure (use these exact markdown headers):
## About This {subject} PNG
[150+ words — describe specific visual qualities: color, texture, composition, style. Be specific to THIS subject.]

## Design Applications
[5 bullet points — specific real use cases for THIS subject in graphic design work]

## Technical Details
[2-3 sentences about PNG quality, transparent background, and resolution]

## Frequently Asked Questions
Q: Is this {subject} PNG completely free?
A: [2 sentences]

Q: Can I use this in Canva?
A: [2 sentences]

Rules:
- Do NOT start with "This high-quality" or "This stunning"
- Do NOT use the phrase "perfect for"
- Mention {subject} naturally 4-5 times
- Write as a human expert, not AI
- Total must be 350+ words"""

    description = _groq_call(
        "llama-3.3-70b-versatile",
        [{"role": "system", "content": _SYS_DESC},
         {"role": "user",   "content": desc_prompt}],
        max_tokens=800,
    )

    # Fallback if either call failed
    if not description or len(description.split()) < 100:
        description = _fallback_desc(subject, category)

    return {
        "title":       fast.get("title") or f"{subject} Transparent PNG HD Free Download | UltraPNG",
        "slug":        slugify(fast.get("slug") or f"{slug_base}-png-hd"),
        "h1":          fast.get("h1")    or f"{subject} PNG Transparent Background",
        "meta_desc":   (fast.get("meta_desc") or f"Download {subject} PNG transparent background free HD. UltraPNG.com")[:155],
        "tags":        fast.get("tags")  or f"{subject},png,transparent,free download,HD,{subject} PNG,ultrapng",
        "description": description,
        "word_count":  len(description.split()),
    }

def _fallback_desc(subject, category):
    return f"""## About This {subject} PNG

The {subject} transparent PNG image from UltraPNG.com delivers professional-grade quality for graphic designers, digital marketers, and content creators. Featuring a completely transparent background processed by BiRefNet AI, every edge is precisely clean with natural anti-aliasing that blends seamlessly onto any surface.

The {subject} image maintains full color fidelity and detail at HD resolution, making it equally effective at small icon sizes and large-format print dimensions. Designers working on flex banners, social media content, or product catalogs will find the clean alpha channel works without additional editing in any major design application.

## Design Applications

- Flex banner and large-format hoarding designs for {category} businesses
- Social media posts, Instagram stories, and YouTube thumbnail graphics
- E-commerce product catalog pages and online marketplace listings
- Wedding invitation cards, event posters, and celebration banners
- Canva templates, Google Slides presentations, and PowerPoint designs

## Technical Details

This {subject} PNG uses full alpha channel transparency with AI-refined edges, eliminating halos and fringing common in manual cutouts. The HD resolution prints cleanly at sizes up to 4096px and scales without quality loss for digital use.

## Frequently Asked Questions

Q: Is this {subject} PNG completely free?
A: Yes, completely free for personal and commercial use. No account required, no watermark on the downloaded file.

Q: Can I use this in Canva?
A: Absolutely. Upload directly to Canva via the Uploads panel and the transparent background works instantly on any background color or design."""

# ── HTML Builder ───────────────────────────────────────────────
def _esc(s):
    return (str(s or "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))

def _md_to_html(md):
    if not md:
        return ""
    o = str(md)
    o = re.sub(r"^## (.+)$",  r"<h2>\1</h2>", o, flags=re.MULTILINE)
    o = re.sub(r"^### (.+)$", r"<h3>\1</h3>", o, flags=re.MULTILINE)
    o = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", o)
    o = re.sub(r"^- (.+)$", r"<li>\1</li>", o, flags=re.MULTILINE)
    o = re.sub(r"(<li>.*?</li>\n?)+", lambda m: f"<ul>{m.group()}</ul>", o)
    o = re.sub(r"\n{2,}", "</p><p>", o)
    return f"<p>{o}</p>"

def build_image_page(entry):
    """Returns HTML string for one image page."""
    url      = f"{SITE_URL}/png-library/{entry['category']}/{entry['slug']}/"
    title    = _esc(entry["title"])
    desc     = _esc(entry["meta_desc"])
    h1       = _esc(entry["h1"])
    webp_img = entry.get("webp_preview_url", "")
    enc_dl   = __import__("base64").b64encode(
        entry.get("download_url", "").encode()).decode()
    tags     = [t.strip() for t in entry.get("tags", "").split(",") if t.strip()]
    desc_html = _md_to_html(entry.get("description", ""))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>{title}</title>
<meta name="description" content="{desc}"/>
<meta name="robots" content="index,follow,max-image-preview:large"/>
<link rel="canonical" href="{_esc(url)}"/>
<meta property="og:type" content="website"/>
<meta property="og:url" content="{_esc(url)}"/>
<meta property="og:title" content="{title}"/>
<meta property="og:description" content="{desc}"/>
<meta property="og:image" content="{_esc(webp_img)}"/>
<meta property="og:site_name" content="UltraPNG"/>
<meta name="twitter:card" content="summary_large_image"/>
<link rel="icon" type="image/svg+xml" href="/favicon.svg"/>
<link rel="stylesheet" href="/css/style.css?v=22"/>
<link rel="stylesheet" href="/css/png-library.css?v=10"/>
</head>
<body>
<header><div class="header-inner">
<a href="/" class="logo"><div class="logo-icon">U</div>
<div class="logo-text"><span class="logo-name">Ultra<span>PNG</span></span>
<span class="logo-sub">Free Transparent PNG Images</span></div></a>
<nav><a href="/">Home</a><a href="/png-library/" class="active">PNG Library</a>
<a href="/pages/about.html">About</a><a href="/pages/contact.html" class="nav-contact">Contact</a></nav>
</div></header>
<main class="item-page">
<div class="item-hero">
<div class="item-preview-wrap">
<img src="{_esc(webp_img)}" alt="{_esc(entry.get('alt_text',''))}" loading="lazy" class="item-preview-img"/>
</div>
<div class="item-info">
<h1>{h1}</h1>
<div class="item-tags">{" ".join(f'<span class="tag">{_esc(t)}</span>' for t in tags[:10])}</div>
<div class="download-box">
<button class="btn-download" onclick="startDownload('{enc_dl}')">Download PNG Free</button>
<div id="dl-timer" class="dl-timer" style="display:none"></div>
</div>
</div>
</div>
<article class="item-desc">{desc_html}</article>
</main>
<footer><div class="footer-inner">
<div class="footer-links">
<a href="/png-library/">PNG Library</a><a href="/pages/about.html">About</a>
<a href="/pages/contact.html">Contact</a><a href="/pages/terms.html">Terms</a>
<a href="/pages/privacy.html">Privacy</a></div>
<p>&copy; {datetime.now().year} UltraPNG.com</p>
</div></footer>
<script>
function startDownload(enc){{
  var url=atob(enc),btn=document.querySelector('.btn-download'),
      box=document.getElementById('dl-timer');
  btn.disabled=true; box.style.display='block';
  var s=15;
  var t=setInterval(function(){{
    box.textContent='Download ready in '+s+'s...'; s--;
    if(s<0){{clearInterval(t);box.innerHTML='<a href="'+url+'" download class="btn-dl-now">Download Now!</a>'}}
  }},1000);
}}
</script>
</body>
</html>"""

# ── Repo2 Operations ───────────────────────────────────────────
def repo2_clone():
    if REPO2_DIR.exists():
        subprocess.run(["git", "pull", "--ff-only"], cwd=str(REPO2_DIR),
                       capture_output=True)
        return
    url = f"https://x-access-token:{GITHUB_TOKEN_REPO2}@github.com/{GITHUB_REPO2}.git"
    subprocess.run(["git", "clone", "--depth", "1", url, str(REPO2_DIR)],
                   capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "bot@ultrapng.com"],
                   cwd=str(REPO2_DIR), capture_output=True)
    subprocess.run(["git", "config", "user.name", "UltraPNG Bot"],
                   cwd=str(REPO2_DIR), capture_output=True)

def repo2_load_skip_set():
    """Returns set of all filenames already in Repo2 JSON."""
    data_dir = REPO2_DIR / "data"
    skip     = set()
    if not data_dir.exists():
        return skip
    for jf in data_dir.glob("*.json"):
        if jf.name.startswith("_"):
            continue
        try:
            for e in json.loads(jf.read_text("utf-8")):
                fn = e.get("filename", "")
                if fn:
                    skip.add(fn)
        except Exception:
            pass
    return skip

def repo2_load_category_data(category):
    """Load existing JSON for a category (returns list)."""
    p = REPO2_DIR / "data" / f"{category}.json"
    if p.exists():
        try:
            return json.loads(p.read_text("utf-8"))
        except Exception:
            pass
    return []

def repo2_save_category_data(category, data):
    p = REPO2_DIR / "data" / f"{category}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def repo2_save_html_page(entry):
    out = REPO2_DIR / "png-library" / entry["category"] / entry["slug"] / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_image_page(entry), encoding="utf-8")

def repo2_push(message):
    subprocess.run(["git", "add", "-A"], cwd=str(REPO2_DIR), capture_output=True)
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=str(REPO2_DIR), capture_output=True)
    if result.returncode == 0:
        log("  No changes to push to Repo2")
        return
    subprocess.run(["git", "commit", "-m", message],
                   cwd=str(REPO2_DIR), capture_output=True, check=True)
    subprocess.run(["git", "push"],
                   cwd=str(REPO2_DIR), capture_output=True, check=True)
    log(f"  Repo2 pushed: {message}")

# ── Step A: Check Deleted PNGs ─────────────────────────────────
def step_a_check_deleted(rows):
    """
    Batch-check all PNG file IDs. Mark DELETED in Sheets for missing ones.
    Returns (active_rows, sheet_updates)
    """
    log("Step A: Checking PNG existence in Drive...")
    active_ids = [r["png_file_id"] for r in rows
                  if r.get("status") != "DELETED" and r.get("png_file_id")]

    if not active_ids:
        return rows, []

    exist_map    = batch_check_files_exist(active_ids)
    updates      = []
    active_rows  = []
    deleted_count = 0

    for row in rows:
        fid = row.get("png_file_id", "")
        if row.get("status") == "DELETED":
            continue  # Already marked
        if fid and not exist_map.get(fid, True):
            # Mark as DELETED in Sheets column 8 (status, 0-indexed)
            updates.append({"row": row["row_num"], "col": 8, "value": "DELETED"})
            deleted_count += 1
        else:
            active_rows.append(row)

    if updates:
        sheets_batch_update(updates)
    log(f"  Active: {len(active_rows)} | Newly deleted: {deleted_count}")
    return active_rows, updates

# ── Step B: Manual Drop Scan ───────────────────────────────────
def step_b_manual_drop(all_rows, webp_root_id, png_root_id):
    """
    Scan /manual_drop/ in Drive. For new PNGs:
    - Move to /PNG/{category}/
    - Create WebP → upload to /WebP/{category}/
    - Append new rows to Sheets
    Returns list of new row dicts ready for SEO.
    """
    log("Step B: Scanning manual_drop folder...")
    manual_id = drive_get_folder_id("manual_drop", DRIVE_ROOT_FOLDER_ID)
    files     = drive_list_folder(manual_id)
    if not files:
        log("  manual_drop: empty")
        return []

    existing_filenames = {r.get("filename", "") for r in all_rows}
    new_files = [f for f in files
                 if f["name"].lower().endswith(".png")
                 and f["name"] not in existing_filenames]

    if not new_files:
        log(f"  manual_drop: {len(files)} files, all already processed")
        return []

    log(f"  manual_drop: {len(new_files)} new PNGs found")
    today    = datetime.now().strftime("%Y-%m-%d")
    new_rows = []

    for f in new_files:
        fname    = f["name"]
        fid      = f["id"]
        subject  = filename_to_subject(fname)
        category = detect_category(fname)

        try:
            png_bytes = drive_download_bytes(fid)

            # Upload PNG to organized folder
            cat_png_folder = drive_get_folder_id(category, png_root_id)
            pr = drive_upload(cat_png_folder, fname, png_bytes)
            drive_share(pr["id"])

            # Generate and upload WebP
            webp_bytes, _, _ = make_webp_bytes(png_bytes)
            cat_webp_folder  = drive_get_folder_id(category, webp_root_id)
            wr = drive_upload(cat_webp_folder, Path(fname).stem + ".webp",
                              webp_bytes, "image/webp")
            drive_share(wr["id"])

            # Delete from manual_drop
            drive_delete(fid)

            row = [
                fname, subject, category,
                pr["id"], wr["id"],
                download_url(pr["id"]), preview_url(wr["id"], 800),
                "FALSE", "MANUAL", today,
            ]
            sheets_append_rows([row])
            new_rows.append({
                "filename": fname, "subject_name": subject, "category": category,
                "png_file_id": pr["id"], "webp_file_id": wr["id"],
                "png_url": download_url(pr["id"]), "webp_url": preview_url(wr["id"], 800),
                "seo_done": "FALSE", "status": "MANUAL",
            })
            log(f"  Manual drop processed: {fname} → {category}")

        except Exception as e:
            log(f"  Manual drop FAIL {fname}: {e}")

    return new_rows

# ── Step C: WebP Repair ────────────────────────────────────────
def step_c_webp_repair(active_rows, webp_root_id):
    """
    For rows where PNG exists but WebP is missing → regenerate and upload.
    Returns sheet_updates.
    """
    log("Step C: Checking for missing WebPs...")
    need_repair = [r for r in active_rows
                   if not r.get("webp_file_id") and r.get("png_file_id")]

    if not need_repair:
        log("  No WebP repairs needed")
        return []

    log(f"  Repairing {len(need_repair)} missing WebPs...")
    updates = []

    for row in need_repair:
        try:
            png_bytes        = drive_download_bytes(row["png_file_id"])
            webp_bytes, _, _ = make_webp_bytes(png_bytes)
            cat_webp_folder  = drive_get_folder_id(row["category"], webp_root_id)
            fname            = Path(row["filename"]).stem + ".webp"
            wr               = drive_upload(cat_webp_folder, fname, webp_bytes, "image/webp")
            drive_share(wr["id"])

            # Update Sheets cols 4 (webp_file_id) and 6 (webp_url)
            updates.append({"row": row["row_num"], "col": 4, "value": wr["id"]})
            updates.append({"row": row["row_num"], "col": 6,
                            "value": preview_url(wr["id"], 800)})
            row["webp_file_id"] = wr["id"]
            row["webp_url"]     = preview_url(wr["id"], 800)
            log(f"  Repaired WebP: {row['filename']}")

        except Exception as e:
            log(f"  WebP repair FAIL {row.get('filename','?')}: {e}")

    if updates:
        sheets_batch_update(updates)
    return updates

# ── Step D: SEO Generation ─────────────────────────────────────
def step_d_seo(active_rows, skip_set):
    """
    Generate SEO for rows where seo_done=FALSE AND not in Repo2 skip_set.
    Returns (new_entries, sheet_updates)
    """
    todo = [r for r in active_rows
            if r.get("seo_done", "FALSE").upper() != "TRUE"
            and r.get("status") != "DELETED"
            and r.get("png_file_id")
            and r.get("filename") not in skip_set]

    if not todo:
        log("Step D: No new SEO work needed")
        return [], []

    log(f"Step D: Generating SEO for {len(todo)} images...")

    # Group by category to batch Repo2 JSON writes
    by_category  = {}
    new_entries  = []
    sheet_updates = []
    used_slugs   = set()

    for row in todo:
        filename = row["filename"]
        subject  = row.get("subject_name") or filename_to_subject(filename)
        category = row.get("category", "general")

        try:
            seo = generate_seo(subject, category, filename)

            # Ensure unique slug per category
            slug     = seo["slug"]
            base     = slug
            sfx      = 1
            while f"{category}/{slug}" in used_slugs:
                slug = f"{base}-{sfx}"
                sfx += 1
            used_slugs.add(f"{category}/{slug}")
            seo["slug"] = slug

            entry = {
                "filename":          filename,
                "subject_name":      subject,
                "category":          category,
                "slug":              slug,
                "title":             seo["title"],
                "h1":                seo["h1"],
                "meta_desc":         seo["meta_desc"],
                "alt_text":          f"{subject} Transparent PNG Background Free Download UltraPNG",
                "tags":              seo["tags"],
                "description":       seo["description"],
                "word_count":        seo["word_count"],
                "png_file_id":       row.get("png_file_id", ""),
                "webp_file_id":      row.get("webp_file_id", ""),
                "download_url":      row.get("png_url", ""),
                "preview_url":       row.get("webp_url", ""),
                "webp_preview_url":  row.get("webp_url", ""),
                "date_added":        datetime.now().strftime("%Y-%m-%d"),
            }

            by_category.setdefault(category, []).append(entry)
            new_entries.append(entry)
            sheet_updates.append({"row": row["row_num"], "col": 7, "value": "TRUE"})

            log(f"  SEO done: {filename} → slug={slug} ({seo['word_count']}w)")

        except Exception as e:
            log(f"  SEO FAIL {filename}: {e}")

        time.sleep(0.5)  # Polite rate limit buffer

    # Write to Repo2 JSON + build HTML pages
    for category, entries in by_category.items():
        existing = repo2_load_category_data(category)
        existing.extend(entries)
        repo2_save_category_data(category, existing)
        for entry in entries:
            repo2_save_html_page(entry)

    if sheet_updates:
        sheets_batch_update(sheet_updates)

    log(f"Step D: SEO complete | {len(new_entries)} entries written to Repo2")
    return new_entries, sheet_updates

# ── Main ────────────────────────────────────────────────────────
def main():
    log("=" * 56)
    log("UltraPNG Phase 2 SEO Engine — Start")
    log("=" * 56)

    # Install Pillow if needed (GitHub Actions)
    try:
        import PIL
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "Pillow"],
                       capture_output=True)

    # Clone Repo2
    log("Cloning Repo2...")
    repo2_clone()
    skip_set = repo2_load_skip_set()
    log(f"  Repo2 skip-set: {len(skip_set)} existing filenames")

    # Read ALL Sheets data in ONE call
    log("Reading Google Sheets...")
    all_rows = sheets_read_all()
    log(f"  Sheets rows: {len(all_rows)}")

    # Get Drive root folder IDs (minimal calls)
    png_root  = drive_get_folder_id("PNG",  DRIVE_ROOT_FOLDER_ID)
    webp_root = drive_get_folder_id("WebP", DRIVE_ROOT_FOLDER_ID)

    # Step A: Check deleted PNGs
    active_rows, _ = step_a_check_deleted(all_rows)

    # Step B: Manual drop scan
    new_manual = step_b_manual_drop(all_rows, webp_root, png_root)
    active_rows.extend(new_manual)

    # Step C: WebP repair
    step_c_webp_repair(active_rows, webp_root)

    # Step D: SEO generation + Repo2 push
    new_entries, _ = step_d_seo(active_rows, skip_set)

    if new_entries:
        count = len(new_entries)
        repo2_push(f"Add {count} new PNG entries ({datetime.now().strftime('%Y-%m-%d')})")
    else:
        log("No new entries — Repo2 push skipped")

    log("=" * 56)
    log("Phase 2 COMPLETE ✓")
    log("=" * 56)

main()
