import json
import os
import re
import subprocess
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple


ULTRADATA_XLSX = "ultradata.xlsx"
WATERMARK_TEXT = "www.ultrapng.com"


def _word_count(s: str) -> int:
    return len([w for w in re.split(r"\s+", (s or "").strip()) if w])


def _ddg_snippets(query: str, limit: int = 6) -> List[str]:
    """
    Free web search (no key): DuckDuckGo HTML endpoint parsing.
    Best-effort; returns short snippets for grounding/uniqueness.
    """
    import requests

    q = (query or "").strip()
    if not q:
        return []
    url = "https://duckduckgo.com/html/"
    r = requests.post(url, data={"q": q}, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    if not r.ok:
        return []
    html = r.text
    # crude snippet extraction; avoids external parsers
    snippets = re.findall(r'class="result__snippet".*?>(.*?)</a>', html, flags=re.S | re.I)
    cleaned = []
    for s in snippets:
        s = re.sub(r"<.*?>", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        if s and s not in cleaned:
            cleaned.append(s)
        if len(cleaned) >= limit:
            break
    return cleaned


def _groq_generate(subject_name: str, web_snippets: List[str]) -> Tuple[str, str]:
    """
    Generates SEO title (20+ words) + description (300+ words) using Groq Chat Completions.
    Env: GROQ_API_KEY
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

    # Using Groq OpenAI-compatible endpoint
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
            "temperature": 0.6,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
        },
        timeout=90,
    )
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"].strip()
    j0, j1 = content.find("{"), content.rfind("}") + 1
    data = json.loads(content[j0:j1])
    title = (data.get("title") or "").strip()
    desc = (data.get("description") or "").strip()

    if _word_count(title) < 20:
        raise RuntimeError(f"Title too short: {_word_count(title)} words")
    if _word_count(desc) < 300:
        raise RuntimeError(f"Description too short: {_word_count(desc)} words")
    return title, desc


def _read_ultradata_rows(xlsx_path: Path) -> List[Dict[str, str]]:
    import openpyxl

    wb = openpyxl.load_workbook(str(xlsx_path))
    ws = wb.active
    if ws.max_row < 2:
        return []

    headers = [str(c.value or "").strip() for c in ws[1]]
    idx = {h: i for i, h in enumerate(headers)}
    needed = ["subject_name", "filename", "download_url", "preview_url"]
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
        "date_added",
        "subject_name",
        "category",
        "subcategory",
        "filename",
        "png_file_id",
        "webp_file_id",
        "download_url",
        "preview_url",
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
            r.get("date_added", ""),
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


def _drive_token() -> str:
    import requests

    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
            "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
            "refresh_token": os.environ.get("GOOGLE_REFRESH_TOKEN", ""),
            "grant_type": "refresh_token",
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
    r = requests.get(
        "https://www.googleapis.com/drive/v3/files",
        headers=h,
        params={"q": q, "fields": "files(id,name)"},
        timeout=30,
    )
    r.raise_for_status()
    files = r.json().get("files", [])
    if files:
        return files[0]["id"]
    meta = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent:
        meta["parents"] = [parent]
    c = requests.post(
        "https://www.googleapis.com/drive/v3/files",
        headers={**h, "Content-Type": "application/json"},
        json=meta,
        timeout=30,
    )
    c.raise_for_status()
    return c.json()["id"]


def _drive_list_png(token: str, folder_id: str) -> List[Dict[str, str]]:
    import requests

    h = {"Authorization": f"Bearer {token}"}
    q = f"'{folder_id}' in parents and trashed=false and (mimeType='image/png' or name contains '.png')"
    r = requests.get(
        "https://www.googleapis.com/drive/v3/files",
        headers=h,
        params={"q": q, "fields": "files(id,name,parents,mimeType)"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("files", [])


def _drive_list_folders(token: str, folder_id: str) -> List[Dict[str, str]]:
    import requests

    h = {"Authorization": f"Bearer {token}"}
    q = f"'{folder_id}' in parents and trashed=false and mimeType='application/vnd.google-apps.folder'"
    r = requests.get(
        "https://www.googleapis.com/drive/v3/files",
        headers=h,
        params={"q": q, "fields": "files(id,name)"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("files", [])


def _drive_download(token: str, file_id: str) -> bytes:
    import requests

    h = {"Authorization": f"Bearer {token}"}
    r = requests.get(
        f"https://www.googleapis.com/drive/v3/files/{file_id}",
        headers=h,
        params={"alt": "media"},
        timeout=120,
    )
    r.raise_for_status()
    return r.content


def _drive_upload(token: str, folder_id: str, name: str, data: bytes, mime: str) -> Dict[str, str]:
    import requests

    h = {"Authorization": f"Bearer {token}"}
    boundary = "----UltraPNGS2"
    metadata = json.dumps({"name": name, "parents": [folder_id]})
    body = (
        f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{metadata}\r\n"
        f"--{boundary}\r\nContent-Type: {mime}\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--".encode()
    r = requests.post(
        "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,name",
        headers={**h, "Content-Type": f'multipart/related; boundary="{boundary}"'},
        data=body,
        timeout=120,
    )
    r.raise_for_status()
    return r.json()


def _drive_share(token: str, file_id: str) -> None:
    import requests

    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    requests.post(
        f"https://www.googleapis.com/drive/v3/files/{file_id}/permissions",
        headers=h,
        json={"role": "reader", "type": "anyone"},
        timeout=30,
    )


def _drive_move(token: str, file_id: str, add_parent: str, remove_parent: str) -> None:
    import requests

    h = {"Authorization": f"Bearer {token}"}
    r = requests.patch(
        f"https://www.googleapis.com/drive/v3/files/{file_id}",
        headers=h,
        params={"addParents": add_parent, "removeParents": remove_parent, "fields": "id"},
        timeout=30,
    )
    r.raise_for_status()


def _preview_url(fid: str, size: int = 800) -> str:
    return f"https://lh3.googleusercontent.com/d/{fid}=s{size}"


def _download_url(fid: str) -> str:
    return f"https://drive.usercontent.google.com/download?id={fid}&export=download&authuser=0"


def _make_webp_preview(png_bytes: bytes) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    with Image.open(io.BytesIO(png_bytes)).convert("RGBA") as img_rgba:
        w, h = img_rgba.size
        if max(w, h) > 800:
            ratio = 800 / max(w, h)
            img_rgba = img_rgba.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        w, h = img_rgba.size
        bg = Image.new("RGB", (w, h), (255, 255, 255))
        drw = ImageDraw.Draw(bg)
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
        wm_draw = ImageDraw.Draw(wm_layer)
        for y in range(-h, h + 110, 110):
            for x in range(-w, w + 110, 110):
                wm_draw.text((x, y), WATERMARK_TEXT, fill=(0, 0, 0, 42), font=fnt)
        wm_rot = wm_layer.rotate(-30, expand=False)
        bg_rgba = bg.convert("RGBA")
        bg_rgba.alpha_composite(wm_rot)
        out = bg_rgba.convert("RGB")
        d2 = ImageDraw.Draw(out)
        d2.rectangle([0, h - 36, w, h], fill=(13, 13, 20))
        d2.text((w // 2 - 72, h - 26), WATERMARK_TEXT, fill=(245, 166, 35), font=fnt)

        buf = io.BytesIO()
        out.save(buf, "WEBP", quality=82, method=4)
        return buf.getvalue()


def _process_manual_drop_and_update_ultradata(xlsx_path: Path) -> List[Dict[str, str]]:
    token = _drive_token()
    manual_root = _drive_folder(token, "manual drop")
    png_root = _drive_folder(token, "png_library_images")
    prev_root = _drive_folder(token, "png_library_previews")
    library_manual = _drive_folder(token, "manual_drop", png_root)
    preview_manual = _drive_folder(token, "manual_drop", prev_root)

    files = _drive_list_png(token, manual_root)
    if not files:
        return []

    new_rows: List[Dict[str, str]] = []
    for f in files:
        fid = f["id"]
        name = f.get("name", "untitled.png")
        old_parent = (f.get("parents") or [manual_root])[0]
        png_bytes = _drive_download(token, fid)
        webp_bytes = _make_webp_preview(png_bytes)
        webp = _drive_upload(token, preview_manual, Path(name).stem + ".webp", webp_bytes, "image/webp")
        _drive_share(token, webp["id"])
        _drive_move(token, fid, library_manual, old_parent)
        _drive_share(token, fid)
        subject = Path(name).stem.replace("_", " ").replace("-", " ").title()
        new_rows.append(
            {
                "date_added": "",
                "subject_name": subject,
                "category": "manual_drop",
                "subcategory": "manual_drop",
                "filename": name,
                "png_file_id": fid,
                "webp_file_id": webp["id"],
                "download_url": _download_url(fid),
                "preview_url": _preview_url(webp["id"], 800),
            }
        )
    if new_rows:
        _append_ultradata_rows(xlsx_path, new_rows)
    return new_rows


def _library_file_names() -> set:
    token = _drive_token()
    png_root = _drive_folder(token, "png_library_images")
    names = set()
    queue = [png_root]
    while queue:
        current = queue.pop(0)
        for f in _drive_list_png(token, current):
            names.add((f.get("name") or "").strip())
        for sf in _drive_list_folders(token, current):
            queue.append(sf["id"])
    return names


@dataclass
class Repo2Config:
    token: str
    slug: str
    data_dir: str = "data"


def _clone_repo2(cfg: Repo2Config, workdir: Path) -> Path:
    repo_url = f"https://x-access-token:{cfg.token}@github.com/{cfg.slug}.git"
    if workdir.exists():
        subprocess.run(["git", "pull", "--rebase", "--autostash"], cwd=str(workdir), check=False)
        subprocess.run(["git", "remote", "set-url", "origin", repo_url], cwd=str(workdir), check=False)
        return workdir
    subprocess.run(["git", "clone", "--depth", "1", repo_url, str(workdir)], check=True)
    return workdir


def _load_repo2_entries(repo2_dir: Path, data_dir: str) -> Tuple[Dict[str, Any], List[Path]]:
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


def _save_repo2_files(repo2_dir: Path, data_dir: str, file_entries: Dict[Path, List[Dict[str, Any]]]) -> None:
    for f, arr in file_entries.items():
        tmp = f.with_suffix(f.suffix + ".tmp")
        tmp.write_text(json.dumps(arr, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(f)


def _ensure_capacity(files: List[Path], repo2_dir: Path, data_dir: str, max_entries: int) -> Path:
    last = files[-1]
    try:
        arr = json.loads(last.read_text(encoding="utf-8"))
        n = len(arr) if isinstance(arr, list) else 0
    except Exception:
        n = 0
    if n < max_entries:
        return last

    m = re.match(r"json(\d+)\.json$", last.name)
    nxt = (int(m.group(1)) + 1) if m else (len(files) + 1)
    newf = (repo2_dir / data_dir / f"json{nxt}.json")
    newf.write_text("[]", encoding="utf-8")
    files.append(newf)
    return newf


def main() -> None:
    root = Path(__file__).resolve().parent
    xlsx = root / ULTRADATA_XLSX
    if not xlsx.exists():
        raise SystemExit(f"Missing {ULTRADATA_XLSX} in repo root")

    repo2_token = os.environ.get("REPO2_TOKEN", "").strip()
    repo2_slug = os.environ.get("REPO2_SLUG", "").strip()
    if not repo2_token or not repo2_slug:
        raise SystemExit("Missing REPO2_TOKEN or REPO2_SLUG")

    max_per_file = int(os.environ.get("REPO2_MAX_PER_JSON", "200"))

    # Manual drop processing first (Section 2 responsibility)
    _process_manual_drop_and_update_ultradata(xlsx)

    rows = _read_ultradata_rows(xlsx)
    if not rows:
        print("ultradata.xlsx: no rows")
        return

    library_names = _library_file_names()
    rows = [r for r in rows if r.get("filename", "") in library_names]

    cfg = Repo2Config(token=repo2_token, slug=repo2_slug)
    repo2_dir = _clone_repo2(cfg, root / "_repo2_work")

    existing, files = _load_repo2_entries(repo2_dir, cfg.data_dir)
    missing = [r for r in rows if r["filename"] not in existing]

    print(f"Repo2 existing: {len(existing)}")
    print(f"Ultradata rows: {len(rows)}")
    print(f"Missing SEO entries: {len(missing)}")

    if not missing:
        return

    # Load file contents into memory for write-back
    file_entries: Dict[Path, List[Dict[str, Any]]] = {}
    for f in files:
        try:
            arr = json.loads(f.read_text(encoding="utf-8"))
            file_entries[f] = arr if isinstance(arr, list) else []
        except Exception:
            file_entries[f] = []

    added = 0
    for r in missing:
        subject = r["subject_name"]
        snippets = _ddg_snippets(subject + " PNG")
        title, desc = _groq_generate(subject, snippets)

        target = _ensure_capacity(files, repo2_dir, cfg.data_dir, max_per_file)
        if target not in file_entries:
            file_entries[target] = []
        file_entries[target].append(
            {
                "subject_name": subject,
                "filename": r["filename"],
                "download_url": r["download_url"],
                "preview_url": r["preview_url"],
                "title": title,
                "description": desc,
            }
        )
        added += 1

    _save_repo2_files(repo2_dir, cfg.data_dir, file_entries)

    # Commit + push
    subprocess.run(["git", "status", "--porcelain"], cwd=str(repo2_dir), check=False)
    subprocess.run(["git", "add", cfg.data_dir], cwd=str(repo2_dir), check=True)
    diff = subprocess.run(["git", "diff", "--staged", "--quiet"], cwd=str(repo2_dir))
    if diff.returncode != 0:
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=str(repo2_dir), check=True)
        subprocess.run(
            ["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"],
            cwd=str(repo2_dir),
            check=True,
        )
        subprocess.run(["git", "commit", "-m", f"seo: add {added} entries from ultradata"], cwd=str(repo2_dir), check=True)
        subprocess.run(["git", "push"], cwd=str(repo2_dir), check=True)

    print(f"Added SEO entries: {added}")


if __name__ == "__main__":
    main()

