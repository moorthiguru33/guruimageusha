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
# GROQ SEO GENERATOR  (model fallback + retry-after support)
# ══════════════════════════════════════════════════════════════

def _groq_generate(subject_name: str, web_snippets: List[str],
                   retries: int = 3) -> Tuple[str, str]:
    """
    Generate SEO title (20+ words) + description (300+ words).

    Model priority:
      1. llama-3.3-70b-versatile  — best quality (primary)
      2. llama-3.1-8b-instant     — fallback if primary hits 429

    Respects Groq 429 retry-after header automatically.
    """
    import requests

    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Missing GROQ_API_KEY")
    subject = (subject_name or "").strip()
    if not subject:
        raise RuntimeError("Missing subject_name")

    context = "\n".join(f"- {s}" for s in (web_snippets or [])[:8])
    sys_prompt = (
        "You are an expert SEO content writer optimized for Google AdSense compliance. "
        "Write unique, helpful, non-spammy content. Avoid keyword stuffing. "
        "No prohibited claims, no adult content, no medical claims unless clearly general. "
        "Output strictly JSON with keys: title, description."
    )
    user_prompt = f"""
Subject name: {subject}

Optional web context snippets (use only for general grounding; do NOT copy verbatim):
{context or "- (none)"}

Requirements:
- title: minimum 20 words, natural English, includes the subject name once.
- description: minimum 300 words, high quality, unique, helpful, AdSense-safe.
- Must be about a transparent PNG image and its best uses (design, printing, Canva, etc.).
- Do not mention AI, Groq, or web search.
- Return ONLY valid JSON. No markdown.
""".strip()

    for model_idx, model in enumerate(GROQ_MODELS):
        last_err = None
        for attempt in range(1, retries + 1):
            try:
                r = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}",
                             "Content-Type": "application/json"},
                    json={
                        "model": model,
                        "temperature": 0.6,
                        "messages": [
                            {"role": "system", "content": sys_prompt},
                            {"role": "user",   "content": user_prompt},
                        ],
                    },
                    timeout=90,
                )

                # ── Respect retry-after on 429 ──────────────
                if r.status_code == 429:
                    retry_after = float(r.headers.get("retry-after", "60"))
                    print(f"\n    [GROQ] 429 on {model} — waiting {retry_after:.0f}s ...",
                          flush=True)
                    time.sleep(retry_after + 2)
                    continue

                r.raise_for_status()
                content = r.json()["choices"][0]["message"]["content"].strip()
                j0, j1  = content.find("{"), content.rfind("}") + 1
                if j0 == -1 or j1 == 0:
                    raise ValueError("No JSON in response")
                data  = json.loads(content[j0:j1])
                title = (data.get("title") or "").strip()
                desc  = (data.get("description") or "").strip()
                # Accept whatever the model returns — no retry for short content
                if _word_count(title) < 5:
                    raise RuntimeError(f"Title empty or unusable: {_word_count(title)} words")
                if _word_count(desc) < 50:
                    raise RuntimeError(f"Description empty or unusable: {_word_count(desc)} words")
                if model_idx > 0:
                    print(f"    [GROQ] used fallback model: {model}", flush=True)
                return title, desc

            except Exception as e:
                last_err = e
                if attempt < retries:
                    wait = GROQ_SLEEP_SEC * attempt * 2
                    print(f"\n    [GROQ] attempt {attempt}/{retries} on {model} failed: {e}"
                          f" — retry in {wait:.0f}s", flush=True)
                    time.sleep(wait)

        print(f"\n    [GROQ] {model} exhausted after {retries} attempts: {last_err}",
              flush=True)

    raise RuntimeError(f"All GROQ models failed. Last: {last_err}")


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
    out = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        row = {h: ("" if r[idx[h]] is None else str(r[idx[h]]).strip()) for h in needed}
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
    h = {"Authorization": f"Bearer {token}"}
    q = (f"'{folder_id}' in parents and trashed=false and "
         f"(mimeType='image/png' or name contains '.png')")
    r = requests.get("https://www.googleapis.com/drive/v3/files",
                     headers=h,
                     params={"q": q, "fields": "files(id,name,parents,mimeType)"},
                     timeout=30)
    r.raise_for_status()
    return r.json().get("files", [])


def _drive_list_folders(token: str, folder_id: str) -> List[Dict[str, str]]:
    import requests
    h = {"Authorization": f"Bearer {token}"}
    q = (f"'{folder_id}' in parents and trashed=false and "
         f"mimeType='application/vnd.google-apps.folder'")
    r = requests.get("https://www.googleapis.com/drive/v3/files",
                     headers=h,
                     params={"q": q, "fields": "files(id,name)"},
                     timeout=30)
    r.raise_for_status()
    return r.json().get("files", [])


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
        subject = r["subject_name"]
        print(f"  [{i}/{len(missing)}] {subject} ...", end=" ", flush=True)
        try:
            snippets    = _ddg_snippets(subject + " PNG")
            title, desc = _groq_generate(subject, snippets)
            target      = _ensure_capacity(files, repo2_dir, cfg.data_dir, max_per_file)
            if target not in file_entries:
                file_entries[target] = []
            file_entries[target].append({
                "subject_name": subject,
                "filename":     r["filename"],
                "download_url": r["download_url"],
                "preview_url":  r["preview_url"],
                "title":        title,
                "description":  desc,
            })
            added += 1
            print("✓")
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
