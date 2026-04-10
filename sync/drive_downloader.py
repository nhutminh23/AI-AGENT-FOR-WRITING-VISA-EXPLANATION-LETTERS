"""
Drive Downloader – Pull validated folders from Google Drive to local disk.

When a folder passes validation (green), this module downloads all its
files into the local ``input/`` directory, preserving subfolder structure
and tagging with the Drive folder ID for Push-to-Drive reverse lookup.

Downloads run in parallel using ThreadPoolExecutor with the ``requests``
library (thread-safe) instead of ``httplib2`` (NOT thread-safe).
"""
from __future__ import annotations

import io
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests as requests_lib
from googleapiclient.http import MediaIoBaseDownload  # type: ignore

logger = logging.getLogger("sync.downloader")

# Max parallel download threads (Google Drive API allows ~10 QPS per user)
_MAX_WORKERS = 8

# Lock for thread-safe credential refresh
_token_lock = threading.Lock()

# Google Drive export MIME mappings for Google Workspace files
_EXPORT_MIMES = {
    "application/vnd.google-apps.document": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".docx",
    ),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsx",
    ),
    "application/vnd.google-apps.presentation": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".pptx",
    ),
}


class DriveDownloader:
    """Download files from Google Drive folders to local disk."""

    def __init__(
        self,
        drive_service: Any,
        local_root: str | Path,
        credentials: Any = None,
    ):
        """
        Parameters
        ----------
        drive_service
            An authenticated ``googleapiclient`` Drive v3 service object.
            Used for listing files (sequential, thread-safe enough).
        local_root : str | Path
            Local root directory to save downloaded folders into.
            Typically ``input/``.
        credentials : google.oauth2.service_account.Credentials, optional
            Service account credentials for thread-safe downloads via
            ``requests`` library. If None, falls back to sequential
            download using ``googleapiclient`` (httplib2).
        """
        self._service = drive_service
        self._local_root = Path(local_root)
        self._local_root.mkdir(parents=True, exist_ok=True)
        self._credentials = credentials
        logger.info("DriveDownloader ready. Local root: %s", self._local_root)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def download_folder(
        self,
        folder_id: str,
        local_folder_name: str,
    ) -> Path:
        """
        Download all files from a Google Drive folder to local disk.

        Creates a directory named ``{sanitized_name}_{folder_id}`` and
        writes a ``_meta.json`` file inside it so the Push-to-Drive
        feature can find the original Drive folder later.

        Recursively downloads subfolders, preserving structure.

        Parameters
        ----------
        folder_id : str
            Google Drive folder ID to download from.
        local_folder_name : str
            Clean folder name for the local directory (status suffixes
            already stripped). E.g. ``"UC - CHU HIEP CO CHINH - NHAN"``.

        Returns
        -------
        Path
            Absolute path to the created local directory.
        """
        safe_name = self._sanitize_dirname(local_folder_name)
        dir_name = f"{safe_name}_{folder_id}"
        dest = self._local_root / dir_name
        dest.mkdir(parents=True, exist_ok=True)

        # Write _meta.json for Push-to-Drive reverse lookup
        meta_path = dest / "_meta.json"
        meta_data = {
            "drive_folder_id": folder_id,
            "base_name": local_folder_name,
            "local_dir_name": dir_name,
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta_data, f, ensure_ascii=False, indent=2)
        logger.info("  📝 Wrote _meta.json -> %s", meta_path)

        # Download: collect file list first, then parallel download
        t0 = time.perf_counter()
        tasks = self._collect_tasks(folder_id, dest)
        t_list = time.perf_counter() - t0
        logger.info(
            "  📋 Listed %d files in %.1fs. Starting parallel download (%d workers)...",
            len(tasks), t_list, _MAX_WORKERS,
        )

        downloaded = self._download_parallel(tasks)
        elapsed = time.perf_counter() - t0

        logger.info(
            "Download complete: %d files saved to %s (%.1fs total)",
            downloaded, dest, elapsed,
        )
        return dest

    # ------------------------------------------------------------------
    # Phase 1: Collect all download tasks (sequential API listing)
    # ------------------------------------------------------------------
    def _collect_tasks(
        self, folder_id: str, dest_dir: Path
    ) -> list[dict]:
        """
        Recursively list all files in a Drive folder tree.

        Returns a flat list of download tasks::

            [{"file_id": ..., "name": ..., "mime": ..., "dest_dir": Path}, ...]

        Subdirectory creation happens here (must be sequential).
        """
        _FOLDER_MIME = "application/vnd.google-apps.folder"
        files = self._list_files(folder_id)
        tasks: list[dict] = []

        for file_meta in files:
            fid = file_meta["id"]
            fname = file_meta["name"]
            mime = file_meta.get("mimeType", "")

            if mime == _FOLDER_MIME:
                # Create local subfolder and recurse
                sub_dir = dest_dir / self._sanitize_dirname(fname)
                sub_dir.mkdir(parents=True, exist_ok=True)
                tasks.extend(self._collect_tasks(fid, sub_dir))
            else:
                tasks.append({
                    "file_id": fid,
                    "name": fname,
                    "mime": mime,
                    "dest_dir": dest_dir,
                })

        return tasks

    # ------------------------------------------------------------------
    # Phase 2: Download all files in parallel
    # ------------------------------------------------------------------
    def _download_parallel(self, tasks: list[dict]) -> int:
        """Download collected file tasks using a thread pool."""
        if not tasks:
            return 0

        downloaded = 0
        errors = 0

        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
            future_to_name = {
                pool.submit(
                    self._download_single_file,
                    task["file_id"],
                    task["name"],
                    task["mime"],
                    task["dest_dir"],
                ): task["name"]
                for task in tasks
            }

            for future in as_completed(future_to_name):
                fname = future_to_name[future]
                try:
                    future.result()
                    downloaded += 1
                except Exception as exc:
                    errors += 1
                    logger.error("Failed to download '%s': %s", fname, exc)

        if errors:
            logger.warning("  ⚠️ %d/%d files failed to download", errors, len(tasks))

        return downloaded

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _list_files(self, folder_id: str) -> list[dict]:
        """List all files in a Drive folder."""
        results = []
        page_token = None
        while True:
            resp = (
                self._service.files()
                .list(
                    q=f"'{folder_id}' in parents and trashed = false",
                    fields="nextPageToken, files(id, name, mimeType)",
                    pageToken=page_token,
                    pageSize=100,
                )
                .execute()
            )
            results.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return results

    def _get_auth_token(self) -> str | None:
        """Get a valid access token, refreshing if needed (thread-safe)."""
        if not self._credentials:
            return None
        with _token_lock:
            if not self._credentials.valid:
                import google.auth.transport.requests as gauth_requests
                self._credentials.refresh(gauth_requests.Request())
            return self._credentials.token

    def _download_single_file(
        self, file_id: str, file_name: str, mime_type: str, dest_dir: Path
    ) -> None:
        """
        Download or export a single file from Drive.

        Uses ``requests`` library (thread-safe) instead of
        ``httplib2``/``googleapiclient`` which is NOT thread-safe.
        Falls back to ``googleapiclient`` if credentials not available.
        """
        token = self._get_auth_token()

        if token:
            # Thread-safe path: use requests library
            self._download_with_requests(
                file_id, file_name, mime_type, dest_dir, token
            )
        else:
            # Fallback: sequential-safe path using googleapiclient
            self._download_with_apiclient(
                file_id, file_name, mime_type, dest_dir
            )

    def _download_with_requests(
        self,
        file_id: str,
        file_name: str,
        mime_type: str,
        dest_dir: Path,
        token: str,
    ) -> None:
        """Thread-safe download using the requests library."""
        headers = {"Authorization": f"Bearer {token}"}

        if mime_type in _EXPORT_MIMES:
            export_mime, ext = _EXPORT_MIMES[mime_type]
            safe_name = self._safe_filename(file_name) + ext
            url = (
                f"https://www.googleapis.com/drive/v3/files/{file_id}/export"
                f"?mimeType={quote(export_mime, safe='')}"
            )
        else:
            safe_name = self._safe_filename(file_name)
            url = (
                f"https://www.googleapis.com/drive/v3/files/{file_id}"
                f"?alt=media"
            )

        file_path = dest_dir / safe_name
        file_path = self._unique_path(file_path)

        resp = requests_lib.get(url, headers=headers, timeout=120)
        resp.raise_for_status()

        file_path.write_bytes(resp.content)
        logger.debug("  Saved: %s (%d bytes)", file_path.name, len(resp.content))

    def _download_with_apiclient(
        self,
        file_id: str,
        file_name: str,
        mime_type: str,
        dest_dir: Path,
    ) -> None:
        """Fallback sequential download using googleapiclient (NOT thread-safe)."""
        if mime_type in _EXPORT_MIMES:
            export_mime, ext = _EXPORT_MIMES[mime_type]
            safe_name = self._safe_filename(file_name) + ext
            request = self._service.files().export_media(
                fileId=file_id, mimeType=export_mime
            )
        else:
            safe_name = self._safe_filename(file_name)
            request = self._service.files().get_media(fileId=file_id)

        file_path = dest_dir / safe_name
        file_path = self._unique_path(file_path)

        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)

        done = False
        while not done:
            status, done = downloader.next_chunk()

        file_path.write_bytes(fh.getvalue())
        logger.debug("  Saved: %s (%d bytes)", file_path.name, len(fh.getvalue()))

    @staticmethod
    def _sanitize_dirname(name: str) -> str:
        """Remove characters invalid for Windows directory names."""
        invalid = '<>:"/\\|?*'
        for ch in invalid:
            name = name.replace(ch, "_")
        return name.strip(". ")

    @staticmethod
    def _safe_filename(name: str) -> str:
        """Sanitize a filename for the local filesystem."""
        invalid = '<>:"/\\|?*'
        for ch in invalid:
            name = name.replace(ch, "_")
        return name.strip()

    @staticmethod
    def _unique_path(path: Path) -> Path:
        """If path exists, append (1), (2), etc. to avoid overwrite."""
        if not path.exists():
            return path
        stem = path.stem
        suffix = path.suffix
        parent = path.parent
        counter = 1
        while True:
            new_path = parent / f"{stem} ({counter}){suffix}"
            if not new_path.exists():
                return new_path
            counter += 1
