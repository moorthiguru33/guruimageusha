"""
Google Drive Uploader
All credentials come from environment variables (GitHub Secrets)
No hardcoded keys here!
"""

import os, json, time, requests
from pathlib import Path


class OAuth2TokenManager:
    TOKEN_URL = "https://oauth2.googleapis.com/token"

    def __init__(self):
        self.client_id     = os.environ.get("GOOGLE_CLIENT_ID", "")
        self.client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
        self.refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN", "")

        if not all([self.client_id, self.client_secret, self.refresh_token]):
            raise ValueError("Missing Google credentials in environment variables!")

        self._access_token = None
        self._token_expiry = 0
        print("OAuth2 credentials loaded from env")

    def get_access_token(self):
        if self._access_token and time.time() < self._token_expiry - 60:
            return self._access_token
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
    ROOT_NAME  = "png_library_images"

    def __init__(self, token_manager):
        self.tokens  = token_manager
        self._cache  = {}
        self.root_id = None

    def _h(self):
        return self.tokens.headers

    def find_or_create_folder(self, name, parent=None):
        key = f"{parent}:{name}"
        if key in self._cache:
            return self._cache[key]
        q = (f"name='{name}' and mimeType='application/vnd.google-apps.folder'"
             f" and trashed=false")
        if parent:
            q += f" and '{parent}' in parents"
        r = requests.get(f"{self.DRIVE_API}/files",
                         headers=self._h(),
                         params={"q": q, "fields": "files(id)"})
        files = r.json().get("files", [])
        if files:
            fid = files[0]["id"]
        else:
            meta = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
            if parent:
                meta["parents"] = [parent]
            r2  = requests.post(f"{self.DRIVE_API}/files",
                                headers={**self._h(), "Content-Type": "application/json"},
                                json=meta)
            fid = r2.json()["id"]
            print(f"  Created folder: {name}")
        self._cache[key] = fid
        return fid

    def setup_root(self):
        self.root_id = self.find_or_create_folder(self.ROOT_NAME)
        print(f"Root folder ready: {self.ROOT_NAME} ({self.root_id})")

    def get_folder(self, category):
        if not self.root_id:
            self.setup_root()
        parent = self.root_id
        for part in category.split("/"):
            if not part:
                continue
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
                    headers=self._h(),
                    files=[("metadata", ("m", meta, "application/json")),
                           ("file",     (filename, data, "image/png"))]
                )
                if r.status_code in [200, 201]:
                    return r.json()["id"]
                time.sleep(2 ** attempt)
            except Exception as e:
                print(f"  Upload attempt {attempt+1} error: {e}")
                time.sleep(2 ** attempt)
        return None

    def upload_folder(self, local_folder,
                      progress_file="progress/upload_progress.json"):
        lp   = Path(local_folder)
        pp   = Path(progress_file)
        pp.parent.mkdir(parents=True, exist_ok=True)
        prog = json.load(open(pp)) if pp.exists() else {"uploaded": [], "failed": []}
        uploaded = set(prog["uploaded"])

        self.setup_root()
        png_files = list(lp.rglob("*.png"))
        print(f"Found {len(png_files)} PNGs to upload")
        stats = {"uploaded": 0, "skipped": 0, "failed": 0}

        for png in png_files:
            rel      = png.relative_to(lp)
            file_key = str(rel)
            if file_key in uploaded:
                stats["skipped"] += 1
                continue
            category  = str(rel.parent)
            folder_id = self.get_folder(category)
            fid       = self.upload_file(str(png), rel.name, folder_id)
            if fid:
                prog["uploaded"].append(file_key)
                uploaded.add(file_key)
                stats["uploaded"] += 1
                if stats["uploaded"] % 50 == 0:
                    with open(pp, "w") as f: json.dump(prog, f)
                    print(f"  Uploaded: {stats['uploaded']}")
            else:
                prog["failed"].append(file_key)
                stats["failed"] += 1
                print(f"  FAIL: {file_key}")
            time.sleep(0.05)

        with open(pp, "w") as f: json.dump(prog, f)
        print(f"Upload done: {stats}")
        return stats


if __name__ == "__main__":
    tokens   = OAuth2TokenManager()
    uploader = GoogleDriveUploader(tokens)
    uploader.upload_folder("/kaggle/working/transparent_pngs")
