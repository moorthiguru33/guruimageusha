#!/usr/bin/env python3
"""
inject_creds_pending.py
────────────────────────
Reads pending_pipeline.py, prepends os.environ credential lines,
and pushes the assembled notebook to Kaggle for GPU execution.

Updated on 14-Apr-2026 — GH_TOKEN & GH_OWNER now properly injected.
"""

import os
import sys
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime

# ── Required secrets (set in GitHub → Settings → Secrets) ─────
def _require(key):
    val = os.environ.get(key, "").strip()
    if not val:
        print(f"❌  Missing required env var: {key}")
        sys.exit(1)
    return val

GOOGLE_CLIENT_ID     = _require("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = _require("GOOGLE_CLIENT_SECRET")
GOOGLE_REFRESH_TOKEN = _require("GOOGLE_REFRESH_TOKEN")
GH_TOKEN             = _require("GH_TOKEN")          # ← NEW
GH_OWNER             = _require("GH_OWNER")          # ← NEW
KAGGLE_USERNAME      = _require("KAGGLE_USERNAME")
KAGGLE_KEY           = _require("KAGGLE_KEY")

# ── Optional vars (set in GitHub → Settings → Variables) ──────
RUN_ITEMS_COUNT     = os.environ.get("RUN_ITEMS_COUNT",     "50")
WATERMARK_TEXT      = os.environ.get("WATERMARK_TEXT",      "www.ultrapng.com")
UPSCALE_FACTOR      = os.environ.get("UPSCALE_FACTOR",      "2")
PENDING_FOLDER_NAME = os.environ.get("PENDING_FOLDER_NAME", "pending")
MAX_INPUT_SIZE      = os.environ.get("MAX_INPUT_SIZE",      "1200")
REMBG_MODEL         = os.environ.get("REMBG_MODEL",         "birefnet-general")
NOTEBOOK_SLUG       = os.environ.get("KAGGLE_NOTEBOOK_SLUG","pending-drive-pipeline")

# ══════════════════════════════════════════════════════════════════
# 1. Read pipeline source
# ══════════════════════════════════════════════════════════════════
PIPELINE_FILE = Path(__file__).parent / "pending_pipeline.py"
if not PIPELINE_FILE.exists():
    print(f"❌  pending_pipeline.py not found at {PIPELINE_FILE}")
    sys.exit(1)

pipeline_code = PIPELINE_FILE.read_text(encoding="utf-8")

# ══════════════════════════════════════════════════════════════════
# 2. Build credential block (prepended to script)
# ══════════════════════════════════════════════════════════════════
creds_block = f"""\
# ── AUTO-INJECTED BY inject_creds_pending.py  (do not edit) ──
import os
os.environ["GOOGLE_CLIENT_ID"]     = {json.dumps(GOOGLE_CLIENT_ID)}
os.environ["GOOGLE_CLIENT_SECRET"] = {json.dumps(GOOGLE_CLIENT_SECRET)}
os.environ["GOOGLE_REFRESH_TOKEN"] = {json.dumps(GOOGLE_REFRESH_TOKEN)}
os.environ["GH_TOKEN"]             = {json.dumps(GH_TOKEN)}
os.environ["GH_OWNER"]             = {json.dumps(GH_OWNER)}
os.environ["RUN_ITEMS_COUNT"]      = {json.dumps(RUN_ITEMS_COUNT)}
os.environ["WATERMARK_TEXT"]       = {json.dumps(WATERMARK_TEXT)}
os.environ["UPSCALE_FACTOR"]       = {json.dumps(UPSCALE_FACTOR)}
os.environ["PENDING_FOLDER_NAME"]  = {json.dumps(PENDING_FOLDER_NAME)}
os.environ["MAX_INPUT_SIZE"]       = {json.dumps(MAX_INPUT_SIZE)}
os.environ["REMBG_MODEL"]          = {json.dumps(REMBG_MODEL)}
# ─────────────────────────────────────────────────────────────────
"""

full_code = creds_block + "\n" + pipeline_code

# ══════════════════════════════════════════════════════════════════
# 3. Configure Kaggle CLI credentials
# ══════════════════════════════════════════════════════════════════
kaggle_dir = Path.home() / ".kaggle"
kaggle_dir.mkdir(exist_ok=True)
kaggle_cfg = kaggle_dir / "kaggle.json"
kaggle_cfg.write_text(
    json.dumps({"username": KAGGLE_USERNAME, "key": KAGGLE_KEY}),
    encoding="utf-8"
)
kaggle_cfg.chmod(0o600)
print(f"✅  Kaggle credentials written → {kaggle_cfg}")

# ══════════════════════════════════════════════════════════════════
# 4. Build Kaggle kernel push package in a temp dir
# ══════════════════════════════════════════════════════════════════
work_dir = Path(tempfile.mkdtemp(prefix="kaggle_push_"))
code_file = "pending_pipeline_injected.py"

kernel_meta = {
    "id":                   f"{KAGGLE_USERNAME}/{NOTEBOOK_SLUG}",
    "title":                "Pending Drive Pipeline",
    "code_file":            code_file,
    "language":             "python",
    "kernel_type":          "script",
    "is_private":           True,
    "enable_gpu":           True,
    "enable_internet":      True,
    "dataset_sources":      [],
    "competition_sources":  [],
    "kernel_sources":       [],
}

(work_dir / "kernel-metadata.json").write_text(
    json.dumps(kernel_meta, indent=2), encoding="utf-8"
)
(work_dir / code_file).write_text(full_code, encoding="utf-8")

print(f"  Kernel ID   : {KAGGLE_USERNAME}/{NOTEBOOK_SLUG}")
print(f"  Code file   : {code_file}")
print(f"  Total chars : {len(full_code):,}")

# ══════════════════════════════════════════════════════════════════
# 5. Push to Kaggle
# ══════════════════════════════════════════════════════════════════
print(f"\nPushing to Kaggle at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ...")
result = subprocess.run(
    ["kaggle", "kernels", "push", "-p", str(work_dir)],
    capture_output=True, text=True
)
print(result.stdout)
if result.returncode != 0:
    print("STDERR:", result.stderr)
    if "already exists" in result.stderr.lower() or "409" in result.stderr:
        print("⚠️  Conflict — kernel may already be running. Check Kaggle manually.")
    else:
        shutil.rmtree(str(work_dir), ignore_errors=True)
        sys.exit(result.returncode)

print(f"\n✅  Pushed successfully!")
print(f"    View at: https://www.kaggle.com/{KAGGLE_USERNAME}/{NOTEBOOK_SLUG}")

# ── Cleanup ────────────────────────────────────────────────────
shutil.rmtree(str(work_dir), ignore_errors=True)
