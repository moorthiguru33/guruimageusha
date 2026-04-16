import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


ULTRADATA_XLSX  = "ultradata.xlsx"
WATERMARK_TEXT  = "www.ultrapng.com"
INSTANT_CAP     = 2000   # safety cap — prevents accidental runaway

# ── MODELSCOPE SETTINGS ────────────────────────────────────────
MS_SLEEP_SEC  = 2.0
MS_RETRY_WAIT = 10.0
MS_ENDPOINT   = "https://api-inference.modelscope.ai/v1/chat/completions"
MS_MODELS     = [
    "Qwen/Qwen2.5-72B-Instruct",
    "Qwen/Qwen2.5-32B-Instruct",
    "Qwen/Qwen2.5-7B-Instruct",
]
_ms_dynamic_sleep = 2.0


# ══════════════════════════════════════════════════════════════
# UTILITIES
# ══════════════════════════════════════════════════════════════

def _word_count(s: str) -> int:
    return len([w for w in re.split(r"\s+", (s or "").strip()) if w])


def _today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def _clean_json_str(raw: str) -> str:
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.I)
    raw = re.sub(r"\s*```$", "", raw.strip())
    raw = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", raw)
    raw = re.sub(r",\s*([}\]])", r"\1", raw)
    return raw


def _repair_truncated_json(raw: str) -> str:
    depth: list = []
    in_str = False
    esc    = False
    for ch in raw:
        if esc:
            esc = False
            continue
        if ch == '\\' and in_str:
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch in ('{', '['):
            depth.append(ch)
        elif ch == '}' and depth and depth[-1] == '{':
            depth.pop()
        elif ch == ']' and depth and depth[-1] == '[':
            depth.pop()
    if not depth and not in_str:
        return raw
    patched = raw.rstrip()
    patched = re.sub(r',\s*$', '', patched)
    if in_str:
        patched += '"'
    for opener in reversed(depth):
        patched += '}' if opener == '{' else ']'
    return patched


# ══════════════════════════════════════════════════════════════
# MODELSCOPE SEO
# ══════════════════════════════════════════════════════════════

def _modelscope_seo(subject_name: str, retries: int = 3) -> Dict[str, str]:
    import requests
    global _ms_dynamic_sleep

    key     = os.environ.get("SCOPE", "").strip()
    subject = (subject_name or "").strip()
    if not key:
        raise RuntimeError("Missing SCOPE API key")
    if not subject:
        raise RuntimeError("Missing subject_name")

    seo_prompt = f"""You are an expert SEO writer for an image download website called UltraPNG.

Subject: {subject}

Write SEO content for a PNG image of "{subject}".

OUTPUT: One valid JSON object with EXACTLY these keys:

"title":
  50–60 characters total (count carefully).
  Format: "[Subject] PNG [key feature] — [short use case]"
  Start with the subject name. Include "PNG" and "transparent background" or "HD".
  Example: "Mosambi PNG Transparent Background — HD Fruit Image Download"

"h1":
  8–14 words. Descriptive page heading for the image.
  Example: "Fresh Mosambi Fruit PNG on Transparent Background HD Quality"

"meta_desc":
  Under 155 characters. Describe the image + one reason to use it.
  Do NOT use "click here", "visit", "check out".

"alt_text":
  Screen-reader description.
  Format: "[color/style] {subject} on transparent background [one detail]"

"tags":
  8–10 comma-separated keywords.
  Mix: subject+png, subject+transparent, subject+hd, subject+clipart, subject+download, etc.

"description":
  EXACTLY 30 SEO keywords, comma-separated.
  ALL keywords must be about "{subject}".
  Pattern: variations of subject + png, hd image, transparent background, photography,
  clipart, free download, vector, illustration, cutout, white background, high quality,
  hd photo, stock image, graphic, digital art, isolated, background free, etc.
  Example for "mosambi":
  "mosambi png, mosambi transparent background, mosambi hd image, mosambi photography,
  mosambi clipart, mosambi fruit png, mosambi cutout, mosambi free download,
  mosambi high quality png, mosambi vector, mosambi illustration, mosambi white background,
  mosambi transparent png download, fresh mosambi png, mosambi fruit image,
  mosambi photo, mosambi graphic, mosambi design, mosambi isolated png,
  mosambi fruit clipart, mosambi hd photo, mosambi background free,
  mosambi fruit vector, mosambi png download, mosambi fruit photography,
  mosambi fruit transparent, mosambi juice png, mosambi fruit hd,
  mosambi stock photo, mosambi digital art"
  COUNT: must be exactly 30 items separated by commas.
  NO sentences. NO "perfect for". NO descriptions. ONLY keywords.

Return ONLY the JSON object. No markdown fences. No extra text."""

    def _parse_seo(content: str) -> Dict[str, str]:
        j0 = content.find("{")
        j1 = content.rfind("}") + 1
        if j0 == -1 or j1 == 0:
            raise ValueError(f"No JSON in response: {content[:200]!r}")
        raw = _clean_json_str(content[j0:j1])
        try:
            data = json.loads(raw, strict=False)
        except json.JSONDecodeError as e:
            repaired = _repair_truncated_json(raw)
            try:
                data = json.loads(repaired, strict=False)
            except json.JSONDecodeError:
                raise ValueError(f"JSON parse failed: {e}") from e

        def _str(val, fallback="") -> str:
            if val is None:
                return fallback
            if isinstance(val, list):
                return ", ".join(str(v).strip() for v in val if v)
            return str(val).strip()

        title     = _str(data.get("title"))
        desc      = _str(data.get("description"))
        h1        = _str(data.get("h1")) or title
        meta_desc = _str(data.get("meta_desc"))
        alt_text  = _str(data.get("alt_text")) or title
        tags      = _str(data.get("tags"))

        if len(meta_desc) > 155:
            meta_desc = meta_desc[:152] + "..."

        kw_count = len([k for k in desc.split(",") if k.strip()])
        if kw_count < 28:
            print(f"\n    [WARN] description has {kw_count} keywords (target 30) — accepted",
                  flush=True)

        return {
            "title":       title,
            "h1":          h1,
            "meta_desc":   meta_desc,
            "alt_text":    alt_text,
            "tags":        tags,
            "description": desc,
        }

    messages = [{"role": "user", "content": seo_prompt}]

    for model_idx, model in enumerate(MS_MODELS):
        last_err = None
        for attempt in range(1, retries + 1):
            try:
                r = requests.post(
                    MS_ENDPOINT,
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type":  "application/json",
                    },
                    json={
                        "model":       model,
                        "temperature": 0.4,
                        "max_tokens":  1200,
                        "messages":    messages,
                    },
                    timeout=120,
                )
                if r.status_code == 429:
                    retry_after = float(r.headers.get("retry-after", "30"))
                    _ms_dynamic_sleep = min(max(retry_after, 5), 60)
                    print(f"\n    [429] {model} — waiting {retry_after:.0f}s ...", flush=True)
                    time.sleep(retry_after + 1)
                    continue
                if r.status_code == 400:
                    try:
                        err_body = r.json()
                    except Exception:
                        err_body = r.text[:300]
                    raise RuntimeError(f"400 Bad Request: {err_body}")
                r.raise_for_status()
                content_str = r.json()["choices"][0]["message"]["content"].strip()
                result = _parse_seo(content_str)
                if model_idx > 0:
                    print(f"    [MS] fallback model used: {model}", flush=True)
                return result

            except Exception as e:
                last_err = e
                if attempt < retries:
                    wait = MS_RETRY_WAIT * attempt
                    print(f"\n    [MS] attempt {attempt}/{retries} failed: {e} — retry in {wait:.0f}s",
                          flush=True)
                    time.sleep(wait)

        print(f"\n    [MS] {model} exhausted: {last_err}", flush=True)

    raise RuntimeError(f"All ModelScope models failed. Last: {last_err}")


# ══════════════════════════════════════════════════════════════
# ULTRADATA XLSX  READ / UPDATE
# ══════════════════════════════════════════════════════════════

def _read_pending_rows(xlsx_path: Path) -> List[Dict[str, str]]:
    """Read ultradata.xlsx — return only rows where seo_status = 'pending'."""
    import openpyxl
    wb = openpyxl.load_workbook(str(xlsx_path))
    ws = wb.active
    if ws.max_row < 2:
        return []

    headers = [str(c.value or "").strip() for c in ws[1]]
    idx     = {h: i for i, h in enumerate(headers)}

    needed = ["subject_name", "filename", "download_url", "preview_url"]
    for h in needed:
        if h not in idx:
            raise RuntimeError(f"ultradata.xlsx missing column: {h}")

    out = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        def _v(col):
            return "" if col not in idx or r[idx[col]] is None else str(r[idx[col]]).strip()

        status = _v("seo_status").lower()
        if status == "completed":
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
    """Mark seo_status = 'completed' for finished rows."""
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
        fn  = str(row[filename_col - 1].value or "").strip()
        cell = row[seo_col - 1]
        if fn in completed_filenames:
            if str(cell.value or "").strip() != "completed":
                cell.value = "completed"
                updated += 1

    wb.save(str(xlsx_path))
    return updated


# ══════════════════════════════════════════════════════════════
# GOOGLE DRIVE — BATCH FILE EXISTENCE CHECK  (minimal API calls)
# ══════════════════════════════════════════════════════════════

def _get_drive_token() -> str:
    """Exchange refresh token for access token — 1 API call only."""
    import requests
    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id":     os.environ.get("GOOGLE_CLIENT_ID",     ""),
            "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
            "refresh_token": os.environ.get("GOOGLE_REFRESH_TOKEN", ""),
            "grant_type":    "refresh_token",
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _extract_drive_id(row: Dict) -> str:
    """
    Extract Google Drive file ID from a row.
    Priority: webp_file_id → download_url query param → /d/ path segment.
    """
    fid = (row.get("webp_file_id") or "").strip()
    if fid:
        return fid
    url = (row.get("download_url") or "").strip()
    m = re.search(r"[?&]id=([A-Za-z0-9_-]{10,})", url)
    if m:
        return m.group(1)
    m = re.search(r"/d/([A-Za-z0-9_-]{10,})", url)
    if m:
        return m.group(1)
    return ""


def _batch_check_drive_files(file_ids: List[str], access_token: str) -> set:
    """
    Batch-check existence of Drive file IDs.
    100 files per batch request → e.g. 1000 files = 10 API calls only.
    Returns set of IDs that EXIST and are accessible.
    """
    import requests
    import uuid

    existing: set = set()
    BATCH_SIZE = 100

    for start in range(0, len(file_ids), BATCH_SIZE):
        chunk      = file_ids[start : start + BATCH_SIZE]
        boundary   = f"batch_{uuid.uuid4().hex}"
        parts      = []

        for fid in chunk:
            parts.append(
                f"--{boundary}\r\n"
                f"Content-Type: application/http\r\n\r\n"
                f"GET /drive/v3/files/{fid}?fields=id HTTP/1.1\r\n"
                f"Host: www.googleapis.com\r\n\r\n"
            )
        body = "".join(parts) + f"--{boundary}--"

        try:
            resp = requests.post(
                "https://www.googleapis.com/batch/drive/v3",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type":  f"multipart/mixed; boundary={boundary}",
                },
                data=body.encode("utf-8"),
                timeout=60,
            )
            if resp.status_code not in (200, 207):
                print(f"  [WARN] Drive batch HTTP {resp.status_code} — skipping chunk",
                      flush=True)
                continue

            # Parse multipart response: extract IDs from HTTP 200 segments only
            for segment in resp.text.split(f"--{boundary}"):
                if "HTTP/1.1 200" in segment:
                    m = re.search(r'"id"\s*:\s*"([^"]+)"', segment)
                    if m:
                        existing.add(m.group(1))

        except Exception as e:
            print(f"  [WARN] Drive batch error: {e}", flush=True)

    return existing


def _filter_pending_by_drive(
    pending: List[Dict], access_token: str
) -> List[Dict]:
    """
    Remove rows whose Drive file does not exist.
    Rows with no extractable file ID are kept as-is (can't verify → don't skip).
    """
    id_to_rows: Dict[str, List] = {}
    no_id_rows: List[Dict]      = []

    for r in pending:
        fid = _extract_drive_id(r)
        if fid:
            id_to_rows.setdefault(fid, []).append(r)
        else:
            no_id_rows.append(r)          # no ID → can't check → keep

    unique_ids  = list(id_to_rows.keys())
    batch_calls = (len(unique_ids) + 99) // 100
    print(f"  Unique Drive IDs   : {len(unique_ids)}  ({batch_calls} batch call(s))",
          flush=True)

    existing_ids = _batch_check_drive_files(unique_ids, access_token)
    missing_ids  = set(unique_ids) - existing_ids

    print(f"  Drive files found  : {len(existing_ids)}", flush=True)
    print(f"  Drive files MISSING: {len(missing_ids)} → skip", flush=True)

    # Keep rows whose Drive file exists
    kept: List[Dict] = []
    for fid, rows in id_to_rows.items():
        if fid in existing_ids:
            kept.extend(rows)

    kept.extend(no_id_rows)

    # Restore original order
    order = {r["filename"]: i for i, r in enumerate(pending)}
    kept.sort(key=lambda r: order.get(r["filename"], 9_999_999))
    return kept


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
        subprocess.run(["git", "pull", "--rebase", "--autostash"],
                       cwd=str(workdir), check=False)
        return workdir
    subprocess.run(["git", "clone", "--depth", "1", repo_url, str(workdir)],
                   check=True)
    return workdir


def _load_existing_entries(repo2_dir: Path, data_dir: str) -> Tuple[Dict[str, Any], List[Path]]:
    """Load all existing JSON entries. Returns (filename→entry dict, sorted file list)."""
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
                     max_entries: int,
                     file_entries: Dict[Path, List]) -> Path:
    """Return the current target JSON file. Creates a new one if last is full."""
    last = files[-1]
    n    = len(file_entries.get(last, []))

    if n < max_entries:
        return last

    # last is full — create next
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
        tmp.write_text(json.dumps(arr, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(f)


def _commit_push_repo2(repo2_dir: Path, cfg: Repo2Config, added: int) -> None:
    subprocess.run(["git", "config", "user.name",  "github-actions[bot]"],
                   cwd=str(repo2_dir), check=True)
    subprocess.run(["git", "config", "user.email",
                    "github-actions[bot]@users.noreply.github.com"],
                   cwd=str(repo2_dir), check=True)

    subprocess.run(["git", "add", cfg.data_dir], cwd=str(repo2_dir), check=True)

    xlsx_in_repo2 = repo2_dir / ULTRADATA_XLSX
    if xlsx_in_repo2.exists():
        subprocess.run(["git", "add", ULTRADATA_XLSX], cwd=str(repo2_dir), check=True)

    diff = subprocess.run(["git", "diff", "--staged", "--quiet"], cwd=str(repo2_dir))
    if diff.returncode == 0:
        print("  Repo2: nothing to commit — already up-to-date.")
        return

    subprocess.run(
        ["git", "commit", "-m", f"seo: add {added} entries [section2]"],
        cwd=str(repo2_dir), check=True
    )

    # Pull latest remote changes before pushing to avoid "fetch first" rejection
    pull_result = subprocess.run(
        ["git", "pull", "--rebase"],
        cwd=str(repo2_dir), capture_output=True, text=True
    )
    if pull_result.returncode != 0:
        print(f"  [WARN] git pull --rebase failed:\n{pull_result.stderr}")

    result = subprocess.run(["git", "push"], cwd=str(repo2_dir),
                             capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [ERROR] git push failed:\n{result.stderr}")
        raise RuntimeError("Repo2 push failed — check REPO2_TOKEN permissions.")

    print(f"  Repo2: pushed {added} SEO entries ✓")


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def main() -> None:
    root = Path(__file__).resolve().parent

    repo2_token = os.environ.get("REPO2_TOKEN", "").strip()
    repo2_slug  = os.environ.get("REPO2_SLUG",  "").strip()
    if not repo2_token or not repo2_slug:
        raise SystemExit("❌  Missing REPO2_TOKEN or REPO2_SLUG in environment")

    max_per_file     = int(os.environ.get("REPO2_MAX_PER_JSON", "200"))
    checkpoint_every = 50   # push to repo every N items (crash safety)

    # ── How many to process ──────────────────────────────────
    count_env = (os.environ.get("S2_COUNT", "") or "").strip()
    requested: int | None = None
    if count_env:
        try:
            v = int(count_env)
            if v > 0:
                requested = min(v, INSTANT_CAP)
        except Exception:
            pass

    print("=" * 60)
    print("  Section 2 — SEO JSON Builder")
    print(f"  Requested count : {requested if requested else 'ALL pending'}")
    print(f"  Safety cap      : {INSTANT_CAP}")
    print(f"  Max per JSON    : {max_per_file}")
    print(f"  Model           : {MS_MODELS[0]}")
    print("=" * 60)

    # ── STEP 1: Clone private ultrapng repo ──────────────────
    print("\n[Step 1] Cloning private ultrapng repo ...")
    cfg       = Repo2Config(token=repo2_token, slug=repo2_slug)
    repo2_dir = _clone_repo2(cfg, root / "_repo2_work")

    # ultradata.xlsx lives in private ultrapng repo
    xlsx = repo2_dir / ULTRADATA_XLSX
    if not xlsx.exists():
        raise SystemExit(
            f"❌  {ULTRADATA_XLSX} not found in {repo2_slug}.\n"
            f"    Please push ultradata.xlsx to the root of that repo."
        )

    # ── STEP 2: Read pending rows ────────────────────────────
    print("\n[Step 2] Reading pending rows from ultradata.xlsx ...")
    pending = _read_pending_rows(xlsx)
    print(f"  Pending rows : {len(pending)}")

    if not pending:
        print("  ✅  Nothing pending — all done.")
        return

    # Deduplicate by filename
    seen: set = set()
    deduped   = []
    for r in pending:
        fn = r.get("filename", "")
        if fn and fn not in seen:
            seen.add(fn)
            deduped.append(r)
    pending = deduped

    # ── STEP 2.5: Drive file existence check ─────────────────
    # Skip rows where the Drive file is missing (avoids useless SEO generation).
    # Uses batch API: 100 files per request → very low API usage.
    print("\n[Step 2.5] Checking Google Drive file existence ...")
    _drive_creds_ok = all(
        os.environ.get(k, "").strip()
        for k in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN")
    )
    if not _drive_creds_ok:
        print("  [SKIP] Drive credentials not set — skipping Drive check.")
    elif not pending:
        print("  Nothing to check.")
    else:
        try:
            drive_token   = _get_drive_token()
            before_count  = len(pending)
            pending       = _filter_pending_by_drive(pending, drive_token)
            skipped_drive = before_count - len(pending)
            print(f"  Skipped (file missing in Drive) : {skipped_drive}", flush=True)
            print(f"  Pending after Drive filter      : {len(pending)}", flush=True)
        except Exception as _e:
            print(f"  [WARN] Drive check error ({_e}) — proceeding without filter.",
                  flush=True)

    # ── STEP 3: Load existing SEO from repo2 ────────────────
    print("\n[Step 3] Loading existing SEO entries from repo2 ...")
    existing, files = _load_existing_entries(repo2_dir, cfg.data_dir)
    print(f"  Existing SEO entries : {len(existing)}")

    # Filter out already-done
    todo = [r for r in pending if r["filename"] not in existing]
    print(f"  Still to generate    : {len(todo)}")

    if not todo:
        print("  ✅  All pending rows already have SEO in repo2.")
        return

    # ── STEP 4: Decide count ─────────────────────────────────
    target = min(requested, len(todo)) if requested else len(todo)
    print(f"\n  ▶  Will generate SEO for {target} item(s) ...")

    # ── STEP 5: Generate SEO ─────────────────────────────────
    print(f"\n[Step 4] Generating SEO ...\n")

    # Pre-load file_entries from disk
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

    for i, r in enumerate(todo, 1):
        if added >= target:
            break

        subject  = r["subject_name"]
        filename = r["filename"]

        print(f"  [{i}/{target}] {subject} ({filename}) ...", end=" ", flush=True)

        try:
            seo = _modelscope_seo(subject)
        except Exception as e:
            print(f"✗ SKIP ({e})")
            continue

        # Build slug
        base_slug = re.sub(r"[^a-z0-9]+", "-", subject.lower()).strip("-") or "untitled"
        fn_digits = re.sub(r"[^0-9]", "", filename)[-4:].zfill(4)
        slug      = f"{base_slug}-{fn_digits}"

        # webp preview URL — built from webp_file_id if available
        webp_fid     = r.get("webp_file_id", "")
        webp_preview = (
            f"https://lh3.googleusercontent.com/d/{webp_fid}=s800"
            if webp_fid else r.get("preview_url", "")
        )

        # Choose target JSON file
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
        added       += 1
        pending_push += 1

        kw = len([k for k in seo["description"].split(",") if k.strip()])
        print(f"✓  title={len(seo['title'])}c  kw={kw}", flush=True)

        # Checkpoint: save + push every N items
        if pending_push >= checkpoint_every:
            print(f"\n  [Checkpoint] Saving {pending_push} entries to repo ...")
            _save_json_files(file_entries)
            _mark_completed(xlsx, completed_filenames)
            _commit_push_repo2(repo2_dir, cfg, pending_push)
            pending_push = 0
            print()

        # Sleep between API calls
        if added < target:
            global _ms_dynamic_sleep
            time.sleep(_ms_dynamic_sleep)
            if _ms_dynamic_sleep > MS_SLEEP_SEC:
                _ms_dynamic_sleep = max(MS_SLEEP_SEC, _ms_dynamic_sleep * 0.85)

    # ── STEP 6: Final save + push ────────────────────────────
    if pending_push > 0 or completed_filenames:
        print(f"\n[Step 5] Final save & push ({pending_push} remaining) ...")
        _save_json_files(file_entries)
        updated = _mark_completed(xlsx, completed_filenames)
        print(f"  ultradata.xlsx: {updated} row(s) marked completed")
        _commit_push_repo2(repo2_dir, cfg, pending_push)

    # ── Summary ──────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  ✅  Section 2 complete")
    print(f"  Added this run    : {added}")
    print(f"  Total in repo2    : {len(existing) + added}")
    remaining = len(todo) - added
    if remaining > 0:
        print(f"  Still pending     : {remaining} (run again to continue)")
    print("=" * 60)


if __name__ == "__main__":
    main()
