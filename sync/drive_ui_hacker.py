"""
Drive UI Hacker – Rename Google Drive folders with emoji status prefixes.

Uses the Google Drive API v3 to rename folders with visual indicators:
  - 🚨 THIẾU (...)  → Missing documents
  - ✅ Đang dịch     → All documents present
  - 🔍 Đang kiểm tra → Processing
"""
from __future__ import annotations

import logging

from googleapiclient.discovery import build  # type: ignore
from googleapiclient.discovery import build  # type: ignore
from google.oauth2.credentials import Credentials  # type: ignore
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
from google.auth.transport.requests import Request  # type: ignore
import os

logger = logging.getLogger("sync.drive_ui")


# Scopes needed for Drive API
SCOPES = ["https://www.googleapis.com/auth/drive"]


class DriveUIHacker:
    """Manipulate Google Drive folder metadata (color + name) and upload files via OAuth."""

    def __init__(self, credentials_path: str):
        """
        Parameters
        ----------
        credentials_path : str
            Path to the client_secret.json key file.
        """
        creds = None
        token_path = "token.json"
        
        # 1. Try to load existing token
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            
        # 2. If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(token_path, "w") as token:
                token.write(creds.to_json())
                
        self._creds = creds
        self._service = build("drive", "v3", credentials=self._creds)
        logger.info("DriveUIHacker initialised with OAuth credentials")

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------
    def _update_folder(self, folder_id: str, body: dict) -> dict:
        """Update a folder's metadata on Google Drive."""
        try:
            result = (
                self._service.files()
                .update(fileId=folder_id, body=body, fields="id,name")
                .execute()
            )
            logger.info(
                "Updated folder %s: name=%s",
                folder_id,
                result.get("name"),
            )
            return result
        except Exception as exc:
            logger.error("Failed to update folder %s: %s", folder_id, exc)
            raise

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def rename(self, folder_id: str, new_name: str) -> dict:
        """Rename a folder on Google Drive."""
        return self._update_folder(folder_id, {"name": new_name})

    def mark_error(self, folder_id: str, base_name: str, summary: str) -> dict:
        """
        Mark a folder as ERROR with emoji + missing-document info in the name.

        Uses emoji prefix visible to ALL users (unlike folderColorRgb which
        is per-user / invisible to non-owners).

        Example: ``"🚨 UC - NGUYEN VAN A - NHAN - THIẾU (Passport)"``
        """
        new_name = f"🚨 {base_name} - {summary}"
        return self.rename(folder_id, new_name)

    def mark_success(self, folder_id: str, base_name: str) -> dict:
        """
        Mark a folder as SUCCESS with emoji + status.

        Example: ``"✅ UC - NGUYEN VAN A - NHAN - Đang dịch"``
        """
        new_name = f"✅ {base_name} - Đang dịch"
        return self.rename(folder_id, new_name)

    def mark_processing(self, folder_id: str, base_name: str) -> dict:
        """
        Mark a folder as PROCESSING with emoji while being checked.

        Example: ``"🔍 UC - NGUYEN VAN A - NHAN - Đang kiểm tra..."``
        """
        new_name = f"🔍 {base_name} - Đang kiểm tra..."
        return self.rename(folder_id, new_name)

    def mark_downloading(self, folder_id: str, base_name: str) -> dict:
        """
        Mark a folder after Sale triggers -DONE. IT is now checking files.

        Example: ``"🔍 UC - NGUYEN VAN A - NHAN - Đang check đã đủ file chưa ?"``
        """
        new_name = f"🔍 {base_name} - Đang check đã đủ file chưa ?"
        return self.rename(folder_id, new_name)

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    def list_files_in_folder(self, folder_id: str) -> list[dict]:
        """
        List all files inside a folder (non-recursive, single level).

        Returns list of dicts with keys: ``id``, ``name``, ``mimeType``.
        """
        results = []
        page_token = None

        while True:
            response = (
                self._service.files()
                .list(
                    q=f"'{folder_id}' in parents and trashed = false",
                    fields="nextPageToken, files(id, name, mimeType)",
                    pageToken=page_token,
                    pageSize=100,
                )
                .execute()
            )
            results.extend(response.get("files", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return results

    def list_all_files_recursive(self, folder_id: str) -> list[dict]:
        """
        Recursively list ALL files in a folder and its subfolders.

        Digs into every subfolder to collect all documents regardless
        of how deep Sale organizes them. For example::

            ÚC - CHÚ HIỆP CÔ CHÍNH - NHÂN/
            ├── HỒ SƠ BÁC HIỆP/
            │   ├── passport.pdf      ← found
            │   └── cccd.jpg          ← found
            ├── HỒ SƠ CÔ CHÍNH/
            │   └── passport.pdf      ← found
            └── to_khai.docx          ← found

        Returns list of dicts with keys: ``id``, ``name``, ``mimeType``.
        """
        _FOLDER_MIME = "application/vnd.google-apps.folder"
        all_files = []
        items = self.list_files_in_folder(folder_id)

        for item in items:
            if item["mimeType"] == _FOLDER_MIME:
                # It's a subfolder → dig deeper
                logger.debug("  ↳ Entering subfolder: %s", item["name"])
                all_files.extend(self.list_all_files_recursive(item["id"]))
            else:
                all_files.append(item)

        return all_files

    def find_root_folder(self, folder_name: str) -> str | None:
        """
        Find a shared folder by exact name.

        Returns the folder ID or None.
        """
        response = (
            self._service.files()
            .list(
                q=(
                    f"name = '{folder_name}' "
                    "and mimeType = 'application/vnd.google-apps.folder' "
                    "and trashed = false"
                ),
                fields="files(id, name)",
                pageSize=5,
            )
            .execute()
        )
        files = response.get("files", [])
        if files:
            logger.info("Found root folder '%s' -> %s", folder_name, files[0]["id"])
            return files[0]["id"]
        logger.warning("Root folder '%s' not found!", folder_name)
        return None

    def list_subfolders(self, parent_folder_id: str) -> list[dict]:
        """
        List all immediate sub-folders of a parent folder.

        Returns list of dicts with keys: ``id``, ``name``,
        ``modifiedTime``, ``folderColorRgb``.
        """
        results = []
        page_token = None

        while True:
            response = (
                self._service.files()
                .list(
                    q=(
                        f"'{parent_folder_id}' in parents "
                        "and mimeType = 'application/vnd.google-apps.folder' "
                        "and trashed = false"
                    ),
                    fields="nextPageToken, files(id, name, modifiedTime)",
                    pageToken=page_token,
                    pageSize=100,
                )
                .execute()
            )
            results.extend(response.get("files", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return results

    # ------------------------------------------------------------------
    # Upload helpers (Push-to-Drive)
    # ------------------------------------------------------------------
    def create_subfolder(self, parent_id: str, folder_name: str) -> str:
        """
        Create a subfolder inside a parent folder on Google Drive.

        Returns the new folder's ID.
        """
        body = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }
        result = self._service.files().create(
            body=body, fields="id"
        ).execute()
        folder_id = result["id"]
        logger.info("Created subfolder '%s' -> %s", folder_name, folder_id)
        return folder_id

    def upload_file(
        self, parent_id: str, file_path: str, file_name: str | None = None
    ) -> str:
        """
        Upload a local file to a specific Drive folder.

        Returns the new file's ID.
        """
        import mimetypes
        from googleapiclient.http import MediaFileUpload  # type: ignore

        if file_name is None:
            file_name = os.path.basename(file_path)

        mime_type, _ = mimetypes.guess_type(file_path)
        mime_type = mime_type or "application/octet-stream"

        body = {"name": file_name, "parents": [parent_id]}
        media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)

        result = self._service.files().create(
            body=body, media_body=media, fields="id"
        ).execute()
        file_id = result["id"]
        logger.debug("Uploaded '%s' -> %s", file_name, file_id)
        return file_id

    def mark_done_translating(self, folder_id: str, base_name: str) -> dict:
        """
        Mark a folder as DONE TRANSLATING → move to 'Đang khai' phase.

        Example: ``"✅ UC - NGUYEN VAN A - NHAN - Đang khai"``
        """
        new_name = f"✅ {base_name} - Đang khai"
        return self.rename(folder_id, new_name)

    def rename_file(self, file_id: str, new_name: str) -> dict:
        """
        Rename a single file on Google Drive.

        Used to mark translated originals as ``[Đã dịch] - {original_name}``.
        """
        try:
            result = (
                self._service.files()
                .update(fileId=file_id, body={"name": new_name}, fields="id,name")
                .execute()
            )
            logger.info("Renamed file %s -> %s", file_id, result.get("name"))
            return result
        except Exception as exc:
            logger.error("Failed to rename file %s: %s", file_id, exc)
            raise

    # Alias for backward compatibility
    upload_file_to_folder = upload_file
