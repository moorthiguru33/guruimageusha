"""
Google Drive Uploader - All credentials hardcoded
Uploads transparent PNGs to png_library_images/ folder
"""

import os, json, time, requests
from pathlib import Path
from typing import Optional

class OAuth2TokenManager:
    TOKEN_URL = "https://oauth2.googleapis.com/token"

    def __init__(self):
        self.client_id     = os.environ.get("GOOGLE_CLIENT_ID",
            "308212866102-sd27dv5pjsr2bff3fioj4frr0ul58a1h.apps.googleusercontent.com")
        self.client_secret = os.environ.get("GOOGLE_CLIENT_SECRET",
            "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")
        self.refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN",
            "1//0gxh2M3u4UXarCgYIARAAGBASNwF-L9IrlxhedoSItkoetIKk8OLpgyNGB-ZrwkCFI-qjTtZZ7ubfo6p7z5_RBsw2QmpXG4BuQn4")
        self._access_token = None
        self._token_expiry = 0
        print("OAuth2 credentials loaded")

    def get_access_token(self):
        if self._access_token and time.time() < self._token_expiry - 60:
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
        data = r.json()
        self._access_token = data["access_token"]
        self._token_expiry = time.time() + data.get("expires_in", 3600)
        print("Access token refreshed!")
        return self._access_token

    @property
    def headers(self):
        return {"Authorization": f"Bearer {self.get_access_token()}"}


class GoogleDriveUploader:
    DRIVE_API  = "https://www.googleapis.com/drive/v3"
    UPLOAD_API = "https://www.googleapis.com/upload/drive/v3"
    ROOT_FOLDER_NAME = "png_library_images"

    def __init__(self, token_manager):
        self.tokens        = token_manager
        self._folder_cache = {}
        self.root_folder_id = None

    def _headers(self):
        return self.tokens.headers

    def find_or_create_folder(self, name, parent_id=None):
        key = f"{parent_id}:{name}"
        if key in self._folder_cache:
            return self._folder_cache[key]
        q = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parent_id:
            q += f" and '{parent_id}' in parents"
        r = requests.get(f"{self.DRIVE_API}/files",
                         headers=self._headers(),
                         params={"q": q, "fields": "files(id,name)"})
        files = r.json().get("files", [])
        if files:
            fid = files[0]["id"]
        else:
            meta = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
            if parent_id:
                meta["parents"] = [parent_id]
            r2 = requests.post(f"{self.DRIVE_API}/files",
                               headers={**self._headers(), "Content-Type": "application/json"},
                               json=meta)
            fid = r2.json()["id"]
            print(f"  Created folder: {name}")
        self._folder_cache[key] = fid
        return fid

    def setup_root(self):
        self.root_folder_id = self.find_or_create_folder(self.ROOT_FOLDER_NAME)
        print(f"Root folder ready: {self.ROOT_FOLDER_NAME} ({self.root_folder_id})")
        return self.root_folder_id

    def get_category_folder(self, category):
        if not self.root_folder_id:
            self.setup_root()
        parent = self.root_folder_id
        for part in category.split("/"):
            parent = self.find_or_create_folder(part, parent)
        return parent

    def upload_file(self, local_path, filename, folder_id, retry=3):
        for attempt in range(retry):
            try:
                with open(local_path, "rb") as f:
                    data = f.read()
                meta = json.dumps({"name": filename, "parents": [folder_id]})
                r = requests.post(
                    f"{self.UPLOAD_API}/files?uploadType=multipart",
                    headers=self._headers(),
                    files=[
                        ("metadata", ("metadata", meta, "application/json")),
                        ("file",     (filename,   data, "image/png"))
                    ]
                )
                if r.status_code in [200, 201]:
                    return r.json()["id"]
                time.sleep(2 ** attempt)
            except Exception as e:
                print(f"  Upload attempt {attempt+1} error: {e}")
                time.sleep(2 ** attempt)
        return None

    def upload_folder(self, local_folder, progress_file="progress/upload_progress.json",
                      skip_existing=True):
        lp = Path(local_folder)
        pp = Path(progress_file)
        pp.parent.mkdir(parents=True, exist_ok=True)
        prog = json.load(open(pp)) if pp.exists() else {"uploaded": [], "failed": []}

        self.setup_root()
        png_files = list(lp.rglob("*.png"))
        print(f"Found {len(png_files)} PNGs to upload")
        stats = {"uploaded": 0, "skipped": 0, "failed": 0}

        for png in png_files:
            rel      = png.relative_to(lp)
            file_key = str(rel)
            if file_key in prog["uploaded"]:
                stats["skipped"] += 1
                continue
            category  = str(rel.parent)
            filename  = rel.name
            folder_id = self.get_category_folder(category)
            fid       = self.upload_file(str(png), filename, folder_id)
            if fid:
                prog["uploaded"].append(file_key)
                stats["uploaded"] += 1
                print(f"  Uploaded [{stats['uploaded']}]: {file_key}")
            else:
                prog["failed"].append(file_key)
                stats["failed"] += 1
            if (stats["uploaded"] + stats["failed"]) % 20 == 0:
                with open(pp, "w") as f: json.dump(prog, f)
            time.sleep(0.1)

        with open(pp, "w") as f: json.dump(prog, f)
        print(f"Upload done: {stats}")
        return stats


if __name__ == "__main__":
    tokens   = OAuth2TokenManager()
    uploader = GoogleDriveUploader(tokens)
    uploader.upload_folder("/kaggle/working/transparent_pngs")
