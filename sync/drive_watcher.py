"""
Drive Watcher – The main orchestrator (Traffic Light System).

Polls Google Drive every N seconds, detects folders ending with "-DONE",
validates their contents, and takes action:
  - Missing docs  → Red folder  + rename with missing list
  - All present   → Green folder + auto-download to local ``input/``

Usage::

    python -m sync.drive_watcher
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
load_dotenv(override=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("sync.watcher")

# ---------------------------------------------------------------------------
# Local imports (after path setup)
# ---------------------------------------------------------------------------
from sync.validator import extract_base_name, _load_rules
from sync.drive_ui_hacker import DriveUIHacker
from sync.drive_downloader import DriveDownloader


# ---------------------------------------------------------------------------
# State persistence (simple JSON file to avoid re-processing)
# ---------------------------------------------------------------------------
_STATE_FILE = Path(__file__).parent / "_state.json"


def _load_state() -> dict:
    """Load processing state from disk."""
    if _STATE_FILE.exists():
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"processed": {}}


def _save_state(state: dict) -> None:
    """Persist processing state to disk."""
    with open(_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Trigger detection
# ---------------------------------------------------------------------------
_DONE_PATTERN = re.compile(r"-\s*done\s*$", re.IGNORECASE)
_CHECK_PATTERN = re.compile(r"-\s*check\s*$", re.IGNORECASE)


def is_done_trigger(folder_name: str) -> bool:
    """
    Check if a folder name ends with ``-DONE`` (case insensitive).

    Works even with emoji prefixes (e.g. ``"🚨 UC - A - DONE"``).
    Sale only needs to change the SUFFIX back to ``-DONE`` —
    the emoji prefix from a previous error state is automatically stripped.
    """
    return bool(_DONE_PATTERN.search(folder_name.strip()))


def is_check_trigger(folder_name: str) -> bool:
    """
    Check if a folder name ends with ``-CHECK`` (case insensitive).

    Triggered when IT pushes files back to Drive and renames with -CHECK.
    """
    return bool(_CHECK_PATTERN.search(folder_name.strip()))


def _normalize_drive_text(text: str) -> str:
    """Normalize Drive folder text for accent-insensitive status matching."""
    # Vietnamese 'đ' does not decompose with NFKD, normalize it explicitly.
    raw = (text or "").replace("đ", "d").replace("Đ", "D")
    folded = unicodedata.normalize("NFKD", raw)
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    folded = folded.lower()
    folded = re.sub(r"\s+", " ", folded)
    return folded.strip()


# ---------------------------------------------------------------------------
# Main watcher loop
# ---------------------------------------------------------------------------
class DriveWatcher:
    """
    Orchestrates the full Traffic Light flow:

    1. Poll Google Drive for folders ending in ``-DONE``
    2. Validate document completeness
    3. Update folder color + name
    4. Download to local if valid
    """

    def __init__(
        self,
        credentials_path: str,
        local_input_dir: str | Path,
        root_folder_name: str = "HỒ SƠ VISA 2026",
        poll_interval: int = 10,
        translation_parent_name: str = "Dịch Thuật",
        translation_parent_id: str = "",
        translation_done_prefix: str = "DONE",
    ):
        self._credentials_path = credentials_path
        self._local_input_dir = Path(local_input_dir)
        self._root_folder_name = root_folder_name
        self._poll_interval = poll_interval
        self._translation_parent_name = translation_parent_name
        self._translation_parent_id = (translation_parent_id or "").strip()
        self._translation_done_prefix = translation_done_prefix

        # Components
        self._ui = DriveUIHacker(credentials_path)
        self._downloader = DriveDownloader(
            self._ui._service, self._local_input_dir,
            credentials=self._ui._creds,
        )
        self._rules = _load_rules()
        self._state = _load_state()

        # Cache root folder ID
        self._root_id: str | None = None

    def _ensure_root_folder(self) -> str:
        """Find and cache the root folder ID."""
        if self._root_id is None:
            self._root_id = self._ui.find_root_folder(self._root_folder_name)
            if not self._root_id:
                raise RuntimeError(
                    f"Cannot find root folder '{self._root_folder_name}' on Google Drive. "
                    "Make sure the folder is shared with the Service Account email."
                )
        return self._root_id

    def run_forever(self) -> None:
        """Start the infinite polling loop."""
        logger.info("=" * 60)
        logger.info("  DRIVE WATCHER - Traffic Light System")
        logger.info("  Root folder : %s", self._root_folder_name)
        logger.info("  Translation parent: %s", self._translation_parent_name)
        logger.info("  Local input : %s", self._local_input_dir)
        logger.info("  Poll interval: %ds", self._poll_interval)
        logger.info("=" * 60)

        while True:
            try:
                self._poll_once()
            except KeyboardInterrupt:
                logger.info("Shutting down gracefully...")
                _save_state(self._state)
                break
            except Exception as exc:
                logger.error("Poll cycle error: %s", exc, exc_info=True)

            time.sleep(self._poll_interval)

    def _poll_once(self) -> None:
        """Single poll cycle: scan all subfolders, act on -DONE or -CHECK ones."""
        root_id = self._ensure_root_folder()
        subfolders = self._ui.list_subfolders(root_id)

        # Dedicated parent folder for translation flow
        translation_parent = self._resolve_translation_parent_folder(subfolders)

        for folder in subfolders:
            fid = folder["id"]
            fname = folder["name"]
            modified = folder.get("modifiedTime", "")

            # Skip the dedicated translation parent itself; we scan its children separately.
            if translation_parent and fid == translation_parent["id"]:
                continue

            # Skip if already processed with same modifiedTime
            prev = self._state["processed"].get(fid)
            if prev and prev.get("modifiedTime") == modified:
                continue

            if is_done_trigger(fname):
                logger.info("--- Found -DONE trigger: %s ---", fname)
                self._process_folder(fid, fname, modified)
            elif is_check_trigger(fname):
                logger.info("--- Found -CHECK trigger: %s ---", fname)
                self._process_check(fid, fname, modified)

        # Translation-only flow: child folders under the dedicated translation parent.
        if translation_parent:
            self._poll_translation_subfolders(translation_parent["id"])

    def _is_translation_parent_folder(self, folder_name: str) -> bool:
        """Check if a folder is the dedicated parent for translation-only flow."""
        return _normalize_drive_text(folder_name) == _normalize_drive_text(self._translation_parent_name)

    def _resolve_translation_parent_folder(self, root_subfolders: list[dict]) -> dict | None:
        """
        Resolve translation parent folder with this priority:
        1. Child folder under configured root by name (preferred)
        2. Explicit folder ID from env (DRIVE_TRANSLATION_FOLDER_ID)
        3. Global exact-name fallback (for legacy layouts outside root)
        """
        # 1) Preferred: translation folder as a direct child of root
        for folder in root_subfolders:
            if self._is_translation_parent_folder(folder.get("name", "")):
                self._translation_parent_id = folder["id"]
                return folder

        # 2) Explicit ID fallback
        if self._translation_parent_id:
            try:
                meta = self._ui._service.files().get(
                    fileId=self._translation_parent_id,
                    fields="id,name,mimeType",
                ).execute()
                if meta.get("mimeType") == "application/vnd.google-apps.folder":
                    return {"id": meta["id"], "name": meta.get("name", self._translation_parent_name)}
            except Exception as exc:
                logger.warning(
                    "Cannot access translation parent by ID %s: %s",
                    self._translation_parent_id,
                    exc,
                )

        # 3) Global name fallback for legacy structures not under root
        fallback_id = self._ui.find_root_folder(self._translation_parent_name)
        if fallback_id and fallback_id != self._root_id:
            self._translation_parent_id = fallback_id
            logger.info(
                "Using translation parent outside root: %s (%s)",
                self._translation_parent_name,
                fallback_id,
            )
            return {"id": fallback_id, "name": self._translation_parent_name}

        return None

    def _has_translation_done_marker(self, folder_name: str) -> bool:
        """DONE can be either prefix (`DONE - ...`) or suffix (`... - DONE`)."""
        normalized_name = _normalize_drive_text(folder_name)
        done_token = _normalize_drive_text(self._translation_done_prefix) or "done"
        if re.search(rf"^{re.escape(done_token)}(?:\\b|\\s*[-_])", normalized_name):
            return True
        return bool(re.search(rf"(?:[-_\\s]){re.escape(done_token)}$", normalized_name))

    @staticmethod
    def _is_translation_splitting_status(folder_name: str) -> bool:
        """Status while files are in input/split processing."""
        normalized_name = _normalize_drive_text(folder_name)
        return "dang tach file" in normalized_name

    @staticmethod
    def _canonical_translation_splitting_name(folder_name: str) -> str:
        """Build canonical split-status name with a single suffix."""
        base_name = extract_base_name(folder_name)
        return f"🔍 {base_name} - Đang tách file"

    @staticmethod
    def _is_translation_ready_status(folder_name: str) -> bool:
        """Status indicating files are ready for translation workspace sync."""
        normalized_name = _normalize_drive_text(folder_name)
        return "dang dich" in normalized_name

    def _poll_translation_subfolders(self, parent_folder_id: str) -> None:
        """Handle dedicated translation folders under ``Dịch Thuật`` parent."""
        subfolders = self._ui.list_subfolders(parent_folder_id)

        for folder in subfolders:
            fid = folder["id"]
            fname = folder["name"]
            modified = folder.get("modifiedTime", "")
            prev = self._state["processed"].get(fid, {})

            # Translation flow is complete; do not re-process.
            if self._has_translation_done_marker(fname):
                continue

            # Phase 2: already pushed from input and marked as translating.
            if self._is_translation_ready_status(fname):
                if prev.get("translation_workspace_ready"):
                    continue
                logger.info("--- Found translation-ready trigger: %s ---", fname)
                self._process_translation_ready(fid, fname, modified)
                continue

            # Still in split phase; wait for push-back stage.
            if self._is_translation_splitting_status(fname):
                canonical_name = self._canonical_translation_splitting_name(fname)
                if _normalize_drive_text(fname) != _normalize_drive_text(canonical_name):
                    try:
                        self._ui.rename(fid, canonical_name)
                        logger.info("  Normalized split-status folder name: %s -> %s", fname, canonical_name)
                    except Exception as exc:
                        logger.warning("  Failed to normalize split-status name for %s: %s", fid, exc)
                continue

            # New folder dropped into translation parent (no DONE marker yet).
            if prev and prev.get("modifiedTime") == modified:
                continue

            logger.info("--- Found translation incoming folder: %s ---", fname)
            self._process_translation_incoming(fid, fname, modified)

    def _tag_local_meta(self, local_path: Path, **extra: str) -> None:
        """Persist extra metadata in ``_meta.json`` for downstream routes."""
        meta_path = local_path / "_meta.json"
        if not meta_path.exists():
            return

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            meta.update(extra)
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.warning("  Failed to enrich _meta.json at %s: %s", meta_path, exc)

    def _process_translation_incoming(self, folder_id: str, folder_name: str, modified_time: str) -> None:
        """Translation-only Stage 1: auto-download new folders without DONE marker."""
        base_name = extract_base_name(folder_name)
        logger.info("  Translation base name: %s", base_name)

        try:
            self._ui.mark_splitting(folder_id, base_name)
        except Exception as exc:
            logger.error("  Failed to mark splitting on Drive: %s", exc)

        try:
            local_path = self._downloader.download_folder(folder_id, base_name)
            self._tag_local_meta(local_path, flow_type="translation")
            logger.info("  📁 Translation input downloaded to: %s", local_path)
        except Exception as exc:
            logger.error("  ❌ Translation input download failed: %s", exc)
            self._ui.mark_error(folder_id, base_name, "LỖI khi tải về")
            self._state["processed"][folder_id] = {
                "name": folder_name,
                "modifiedTime": modified_time,
                "valid": False,
                "flow_type": "translation",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            _save_state(self._state)
            return

        self._state["processed"][folder_id] = {
            "name": folder_name,
            "modifiedTime": modified_time,
            "valid": True,
            "flow_type": "translation",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        _save_state(self._state)

    def _process_translation_ready(self, folder_id: str, folder_name: str, modified_time: str) -> None:
        """Translation-only Stage 2: sync a ``Đang dịch`` folder into local workspace."""
        base_name = extract_base_name(folder_name)
        logger.info("  Translation ready base name: %s", base_name)

        source_folder_id = folder_id
        subfolders = self._ui.list_files_in_folder(folder_id)
        for item in subfolders:
            if (item.get("mimeType") == "application/vnd.google-apps.folder"
                    and item["name"].lower().strip() == "final"):
                source_folder_id = item["id"]
                break

        try:
            self._prepare_translation_workspace(folder_id, base_name, source_folder_id)
            self._state["processed"][folder_id] = {
                "name": folder_name,
                "modifiedTime": modified_time,
                "valid": True,
                "flow_type": "translation",
                "translation_workspace_ready": True,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            _save_state(self._state)
        except Exception as exc:
            logger.error("  ❌ Translation workspace prep failed: %s", exc, exc_info=True)
            self._state["processed"][folder_id] = {
                "name": folder_name,
                "modifiedTime": modified_time,
                "valid": False,
                "flow_type": "translation",
                "translation_workspace_ready": False,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            _save_state(self._state)

    def _process_folder(self, folder_id: str, folder_name: str, modified_time: str) -> None:
        """
        Stage 1 (-DONE): Always download to local input/ without validation.

        Validation is deferred to Stage 2 (-CHECK) after IT processes files.
        """

        # 1. Extract base name (strip -DONE and any prior status)
        base_name = extract_base_name(folder_name)
        logger.info("  Base name: %s", base_name)

        # 2. Mark on Drive as "Đang check..."
        try:
            self._ui.mark_downloading(folder_id, base_name)
        except Exception as exc:
            logger.error("  Failed to mark downloading on Drive: %s", exc)

        # 3. Download ALL files to local input/{name}_{id}/
        try:
            local_path = self._downloader.download_folder(folder_id, base_name)
            logger.info("  📁 Downloaded to: %s", local_path)
        except Exception as exc:
            logger.error("  ❌ Download failed: %s", exc)
            self._ui.mark_error(folder_id, base_name, "LỖI khi tải về")
            # Still record state to avoid infinite retry loop
            self._state["processed"][folder_id] = {
                "name": folder_name,
                "modifiedTime": modified_time,
                "valid": False,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            _save_state(self._state)
            return

        # 4. Record state
        self._state["processed"][folder_id] = {
            "name": folder_name,
            "modifiedTime": modified_time,
            "valid": True,  # downloaded successfully
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        _save_state(self._state)

    # ------------------------------------------------------------------
    # Stage 2: -CHECK validation
    # ------------------------------------------------------------------
    def _process_check(self, folder_id: str, folder_name: str, modified_time: str) -> None:
        """Validate a folder triggered by -CHECK (second stage after IT processing)."""

        base_name = extract_base_name(folder_name)
        logger.info("  Base name: %s", base_name)

        # Look for a 'Final' subfolder
        subfolders = self._ui.list_files_in_folder(folder_id)
        final_folder = None
        for item in subfolders:
            if (item.get("mimeType") == "application/vnd.google-apps.folder"
                    and item["name"].lower().strip() == "final"):
                final_folder = item
                break

        if not final_folder:
            logger.warning("  No 'Final' subfolder found. Skipping -CHECK.")
            self._ui.mark_error(folder_id, base_name, "THIẾU thư mục Final")
            self._state["processed"][folder_id] = {
                "name": folder_name, "modifiedTime": modified_time,
                "valid": False, "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            _save_state(self._state)
            return

        # Get ALL files from Final/ recursively
        files = self._ui.list_all_files_recursive(final_folder["id"])
        filenames = [f["name"] for f in files]
        logger.info("  Files in Final/ (%d): %s", len(filenames), filenames)

        # Smart validation: extract person names from filenames
        from sync.validator import validate_folder_smart
        result = validate_folder_smart(folder_name, filenames, self._rules)
        logger.info(
            "  Smart Validation: valid=%s, country=%s, summary=%s",
            result["valid"], result["country_label"], result["summary"],
        )

        if result["valid"]:
            logger.info("  ✅ CHECK PASSED → Marking green + preparing translation workspace")
            self._ui.mark_success(folder_id, base_name)

            # --- NEW: Create Translate folder on Drive & download for translation ---
            try:
                self._prepare_translation_workspace(folder_id, base_name, final_folder["id"])
            except Exception as exc:
                logger.error("  ⚠️ Translation workspace prep failed (non-fatal): %s", exc, exc_info=True)
        else:
            logger.info("  ❌ CHECK FAILED: %s", result["summary"])
            self._ui.mark_error(folder_id, base_name, result["summary"])

        # Record state
        self._state["processed"][folder_id] = {
            "name": folder_name,
            "modifiedTime": modified_time,
            "valid": result["valid"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        _save_state(self._state)

    # ------------------------------------------------------------------
    # Stage 2.5: Prepare translation workspace after CHECK passes
    # ------------------------------------------------------------------
    def _prepare_translation_workspace(
        self, root_folder_id: str, base_name: str, source_folder_id: str,
    ) -> None:
        """
        Prepare translation workspace from a Drive source folder (usually ``Final/``):

          1. Create a 'Translate' subfolder inside the source folder on Drive.
          2. Download the entire source structure (incl Translate) to
           ``translation_workspace/{base_name}/`` on local disk.
        3. Write ``_files_meta.json`` with full Drive ID mapping.
        """
        from config import Config

        # 1. Create 'Translate' folder inside Final/ on Drive
        #    (Check if it already exists first)
        existing = self._ui.list_files_in_folder(source_folder_id)
        translate_folder_id = None
        for item in existing:
            if (item.get("mimeType") == "application/vnd.google-apps.folder"
                    and item["name"].strip().lower() == "translate"):
                translate_folder_id = item["id"]
                logger.info("  📁 Translate folder already exists on Drive: %s", translate_folder_id)
                break

        if not translate_folder_id:
            translate_folder_id = self._ui.create_subfolder(source_folder_id, "Translate")
            logger.info("  📁 Created Translate folder on Drive: %s", translate_folder_id)

        # 2. Download Final/ to translation_workspace/{base_name}/Final/
        workspace_root = Path(Config.TRANSLATION_WORKSPACE_DIR)
        workspace_root.mkdir(parents=True, exist_ok=True)

        # Use the downloader with ID mapping
        dest = self._downloader.download_folder_for_translation(
            folder_id=source_folder_id,
            local_folder_name=base_name,
            dest_root=workspace_root,
        )

        # 3. Enrich _files_meta.json with root folder ID for status changes
        meta_path = dest / "_files_meta.json"
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            meta["root_folder_id"] = root_folder_id
            meta["final_folder_id"] = source_folder_id
            meta["source_folder_id"] = source_folder_id
            meta["translate_folder_id"] = translate_folder_id
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

        logger.info("  ✅ Translation workspace ready at: %s", dest)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main() -> None:
    """Entry point when running ``python -m sync.drive_watcher``."""

    # Resolve credentials path
    creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
    if not Path(creds_path).exists():
        logger.error(
            "Google credentials file not found: %s\n"
            "Please set GOOGLE_CREDENTIALS_PATH in .env or place credentials.json "
            "in the project root.\n"
            "Guide: https://console.cloud.google.com/iam-admin/serviceaccounts",
            creds_path,
        )
        sys.exit(1)

    # Resolve local input directory
    project_root = Path(__file__).parent.parent
    local_input = project_root / "input"

    # Load polling config from rules
    rules = _load_rules()
    poll_interval = rules.get("polling_interval_seconds", 10)
    root_folder = rules.get("root_folder_name", "HỒ SƠ VISA 2026")
    translation_parent = os.getenv("DRIVE_TRANSLATION_FOLDER", "Dịch Thuật")
    translation_parent_id = os.getenv("DRIVE_TRANSLATION_FOLDER_ID", "")
    translation_done_prefix = os.getenv("DRIVE_TRANSLATION_DONE_PREFIX", "DONE")

    watcher = DriveWatcher(
        credentials_path=creds_path,
        local_input_dir=local_input,
        root_folder_name=root_folder,
        poll_interval=poll_interval,
        translation_parent_name=translation_parent,
        translation_parent_id=translation_parent_id,
        translation_done_prefix=translation_done_prefix,
    )
    watcher.run_forever()


if __name__ == "__main__":
    main()
