"""
Google Drive Uploader - Full credentials hardcoded
Folder: png_library_images/
"""

import os, json, time, requests
from pathlib import Path
from typing import Optional

# ── Credentials (hardcoded) ──────────────────────────────
GOOGLE_CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID",
    "308212866102-sd27dv5pjsr2bff3fioj4frr0ul58a1h.apps.googleusercontent.com")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET",
    "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")
GOOGLE_REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN",
    "1//0gxh2M3u4UXarCgYIARAAGBASNwF-L9IrlxhedoSItkoetIKk8OLpgyNGB-ZrwkCFI-qjTtZZ7ubfo6p7z5_RBsw2QmpXG4BuQn4")

class OAuth2TokenManager:
    TOKEN_URL = "https://oauth2.googleapis.com/token"

    def __init__(self):
        self.client_id     = GOOGLE_CLIENT_ID
        self.client_secret = GOOGLE_CLIENT_SECRET
        self.refresh_token = GOOGLE_REFRESH_TOKEN
        self._access_token = None
        self._expiry       = 0
        print("OAuth2 credentials loaded")

    def get_access_token(self):
        if self._access_token and time.time() < self._expiry - 60:
            return self._access_token
        print("Refreshing access token...")
        r = requests.post(self.TOKEN_URL, data={
            "client_id":     self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type":    "refresh_token"
        })
        if r.status_code != 200:
            raise Exception(f"Token refresh failed: {r.text}")
        d = r.json()
        self._access_token = d["access_token"]
        self._expiry       = time.time() + d.get("expires_in", 3600)
        print("Access token refreshed!")
        return self._access_token

    @property
    def headers(self):
        return {"Authorization": f"Bearer {self.get_access_token()}"}


class GoogleDriveUploader:
    DRIVE_API  = "https://www.googleapis.com/drive/v3"
    UPLOAD_API = "https://www.googleapis.com/upload/drive/v3"
    ROOT_NAME  = "png_library_images"

    def __init__(self, token_manager):
        self.tokens        = token_manager
        self._folder_cache = {}
        self.root_id       = None

    def _h(self): return self.tokens.headers

    def find_or_create_folder(self, name, parent_id=None):
        key = f"{parent_id}:{name}"
        if key in self._folder_cache:
            return self._folder_cache[key]
        q = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parent_id: q += f" and '{parent_id}' in parents"
        r = requests.get(f"{self.DRIVE_API}/files", headers=self._h(),
                         params={"q": q, "fields": "files(id,name)"})
        files = r.json().get("files", [])
        if files:
            fid = files[0]["id"]
        else:
            meta = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
            if parent_id: meta["parents"] = [parent_id]
            r2  = requests.post(f"{self.DRIVE_API}/files",
                                headers={**self._h(), "Content-Type": "application/json"},
                                json=meta)
            fid = r2.json()["id"]
            print(f"  Created folder: {name}")
        self._folder_cache[key] = fid
        return fid

    def setup_root(self):
        self.root_id = self.find_or_create_folder(self.ROOT_NAME)
        print(f"Root folder ready: {self.ROOT_NAME} ({self.root_id})")
        return self.root_id

    def get_category_folder(self, category):
        if not self.root_id: self.setup_root()
        parent = self.root_id
        for part in category.split("/"):
            parent = self.find_or_create_folder(part, parent)
        return parent

    def file_exists(self, filename, parent_id):
        q = f"name='{filename}' and '{parent_id}' in parents and trashed=false"
        r = requests.get(f"{self.DRIVE_API}/files", headers=self._h(),
                         params={"q": q, "fields": "files(id)"})
        return len(r.json().get("files", [])) > 0

    def upload_file(self, local_path, filename, folder_id, retry=3):
        for attempt in range(retry):
            try:
                with open(local_path, "rb") as f: data = f.read()
                meta = json.dumps({"name": filename, "parents": [folder_id]})
                r = requests.post(
                    f"{self.UPLOAD_API}/files?uploadType=multipart",
                    headers=self._h(),
                    files=[
                        ("metadata", ("metadata", meta, "application/json")),
                        ("file",     (filename, data, "image/png"))
                    ]
                )
                if r.status_code in [200, 201]:
                    return r.json()["id"]
                time.sleep(2 ** attempt)
            except Exception as e:
                print(f"  Upload error attempt {attempt+1}: {e}")
                time.sleep(2 ** attempt)
        return None

    def upload_folder(self, local_folder, progress_file="progress/upload_progress.json",
                      skip_existing=True):
        local_path = Path(local_folder)
        prog_path  = Path(progress_file)
        prog_path.parent.mkdir(parents=True, exist_ok=True)
        uploaded   = json.load(open(prog_path)).get("uploaded", []) if prog_path.exists() else []
        done_set   = set(uploaded)

        self.setup_root()
        pngs  = list(local_path.rglob("*.png"))
        print(f"Found {len(pngs)} PNGs to upload")
        stats = {"uploaded": 0, "skipped": 0, "failed": 0}

        for png in pngs:
            rel      = str(png.relative_to(local_path))
            category = str(png.relative_to(local_path).parent)
            filename = png.name
            if rel in done_set: stats["skipped"] += 1; continue
            folder_id = self.get_category_folder(category)
            if skip_existing and self.file_exists(filename, folder_id):
                done_set.add(rel); stats["skipped"] += 1; continue
            fid = self.upload_file(str(png), filename, folder_id)
            if fid:
                done_set.add(rel); stats["uploaded"] += 1
                print(f"  Uploaded [{stats['uploaded']}]: {rel}")
            else:
                stats["failed"] += 1; print(f"  FAIL: {rel}")
            if stats["uploaded"] % 20 == 0:
                json.dump({"uploaded": list(done_set)}, open(prog_path, "w"))
            time.sleep(0.1)

        json.dump({"uploaded": list(done_set)}, open(prog_path, "w"))
        print(f"Upload done: {stats}")
        return stats


if __name__ == "__main__":
    tokens   = OAuth2TokenManager()
    uploader = GoogleDriveUploader(tokens)
    uploader.upload_folder("/kaggle/working/transparent_pngs")
