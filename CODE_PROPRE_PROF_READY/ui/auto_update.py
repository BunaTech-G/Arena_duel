from __future__ import annotations

import hashlib
import json
import os
import queue
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from tkinter import TclError

import customtkinter as ctk

from runtime_utils import (
    load_runtime_config,
    runtime_file_path,
    runtime_user_file_path,
)
from ui.theme import (
    PALETTE,
    TYPOGRAPHY,
    apply_window_icon,
    create_badge,
    create_button,
    present_window,
    style_checkbox,
    style_frame,
    style_window,
)


DEFAULT_GAME_VERSION = "1.0.0"
LOCAL_VERSION_METADATA_FILENAME = "version.json"
DEFAULT_UPDATE_MANIFEST_URL = (
    "https://raw.githubusercontent.com/BunaTech-G/Arena_duel/main/version.json"
)
DEFAULT_UPDATE_PAGE_URL = "https://github.com/BunaTech-G/Arena_duel/releases"
AUTO_UPDATE_STATE_FILENAME = "auto_update_state.json"
AUTO_UPDATE_CHECK_TIMEOUT_SECONDS = 2.5
AUTO_UPDATE_POLL_MS = 80
AUTO_UPDATE_REMIND_LATER_SECONDS = 24 * 60 * 60
AUTO_UPDATE_REPROMPT_AFTER_LAUNCHES = 2
AUTO_UPDATE_BADGE_TEXT = "Nouvelle version"
AUTO_UPDATE_NOTICE_TEXT = "Une mise à jour est disponible"
AUTO_UPDATE_NOTICE_DETAIL_TEXT = (
    "Installe-la maintenant ou plus tard. Tu peux aussi masquer cette "
    "version jusqu'à la prochaine mise à jour."
)
AUTO_UPDATE_NOTICE_MIN_WIDTH = 380
AUTO_UPDATE_NOTICE_MAX_WIDTH = 560
AUTO_UPDATE_NOTICE_SIDE_MARGIN = 18
AUTO_UPDATE_PROMPT_TITLE = "Arena Duel - Mise à jour"
AUTO_UPDATE_PROMPT_HEADING_TEMPLATE = "Version {version} prête à installer"
AUTO_UPDATE_PROMPT_SUBTITLE = (
    "Téléchargement vérifié. Vous pouvez installer la mise à jour maintenant "
    "ou la faire plus tard."
)
AUTO_UPDATE_CURRENT_VERSION_LABEL = "Version actuelle"
AUTO_UPDATE_AVAILABLE_VERSION_LABEL = "Version disponible"
AUTO_UPDATE_CHANGELOG_TITLE = "Nouveautés de cette version"
AUTO_UPDATE_ACTIONS_TITLE = "Choisir une action"
AUTO_UPDATE_ACTIONS_DETAIL = "Installe maintenant ou reviens au menu."
AUTO_UPDATE_PRIMARY_ACTION_TEXT = "Installer maintenant"
AUTO_UPDATE_SECONDARY_ACTION_TEXT = "Plus tard"
AUTO_UPDATE_NOTICE_DISMISS_ACTION_TEXT = "Ne plus afficher cette version"
AUTO_UPDATE_DISMISS_CHECKBOX_TEMPLATE = (
    "Ne plus afficher ce message pour la version {version}"
)
AUTO_UPDATE_DISMISS_HINT_TEXT = (
    "La notification reviendra uniquement si une version plus récente est détectée."
)
AUTO_UPDATE_PROMPT_WIDTH = 680
AUTO_UPDATE_PROMPT_HEIGHT = 560
AUTO_UPDATE_PROMPT_CLOSE_DELAY_MS = 140
AUTO_UPDATE_DOWNLOAD_POLL_MS = 80
AUTO_UPDATE_MANIFEST_URL_ENV = "ARENA_DUEL_UPDATE_MANIFEST_URL"
AUTO_UPDATE_PAGE_URL_ENV = "ARENA_DUEL_UPDATE_PAGE_URL"
AUTO_UPDATE_MANIFEST_URL_CONFIG_KEY = "update_manifest_url"
AUTO_UPDATE_PAGE_URL_CONFIG_KEY = "update_page_url"
AUTO_UPDATE_DOWNLOAD_DIRNAME = "updates"
AUTO_UPDATE_DOWNLOAD_TIMEOUT_SECONDS = 30.0
AUTO_UPDATE_DOWNLOAD_CHUNK_SIZE = 64 * 1024
AUTO_UPDATE_DOWNLOAD_TITLE = "Téléchargement en cours"
AUTO_UPDATE_DOWNLOAD_DETAIL = "Préparation de l'installateur Windows..."
AUTO_UPDATE_DOWNLOAD_BROWSER_FALLBACK_TEXT = "Page de mise à jour ouverte"
AUTO_UPDATE_DOWNLOAD_BROWSER_FALLBACK_DETAIL = (
    "Le téléchargement direct a laissé place à la page de mise à jour GitHub."
)
LOCAL_INSTALLER_SUFFIXES = {".exe", ".msi", ".bat", ".cmd"}
WINDOW_BOUND_ATTR = "_arena_auto_update_bound"
WINDOW_AFTER_ATTR = "_arena_auto_update_after_id"
WINDOW_NOTICE_ATTR = "_arena_auto_update_notice"


@lru_cache(maxsize=1)
def _audio_module():
    from game import audio as audio_module

    return audio_module


def init_audio():
    return _audio_module().init_audio()


def play_alert():
    return _audio_module().play_alert()


def play_click():
    return _audio_module().play_click()


def play_transition():
    return _audio_module().play_transition()


def _schedule_window_sound(
    widget,
    *,
    tone: str = "alert",
    delay_ms: int = 70,
) -> None:
    if getattr(widget, "tk", None) is None:
        return

    def _play_sound() -> None:
        try:
            if not widget.winfo_exists():
                return
        except TclError:
            return

        init_audio()
        if tone == "click":
            play_click()
            return
        if tone == "transition":
            play_transition()
            return
        play_alert()

    try:
        widget.after(delay_ms, _play_sound)
    except (AttributeError, TclError):
        pass


@dataclass(frozen=True)
class UpdateManifest:
    version: str
    update_url: str
    remind_later_seconds: int | None = None
    installer_sha256: str | None = None
    release_notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class AvailableUpdate:
    version: str
    update_url: str
    remind_later_seconds: int | None = None
    installer_sha256: str | None = None
    release_notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class AutoUpdateState:
    snoozed_version: str = ""
    remind_after_epoch: int = 0
    launches_until_prompt: int = 0
    dismissed_version: str = ""


@dataclass(frozen=True)
class DownloadProgressSnapshot:
    bytes_downloaded: int = 0
    total_bytes: int | None = None


def _load_local_version_manifest(version_path: str | None = None) -> dict:
    manifest_path = Path(
        version_path or runtime_file_path(LOCAL_VERSION_METADATA_FILENAME)
    )

    try:
        with open(manifest_path, "r", encoding="utf-8") as file_handle:
            payload = json.load(file_handle)
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(payload, dict):
        return {}

    return payload


def current_game_version(version_path: str | None = None) -> str:
    manifest_data = _load_local_version_manifest(version_path)
    version_text = str(manifest_data.get("version") or "").strip()
    return version_text or DEFAULT_GAME_VERSION


def _defer_action_text() -> str:
    return AUTO_UPDATE_SECONDARY_ACTION_TEXT


def _notice_action_text() -> str:
    return AUTO_UPDATE_NOTICE_DETAIL_TEXT


def _prompt_heading_text(update: AvailableUpdate) -> str:
    return AUTO_UPDATE_PROMPT_HEADING_TEMPLATE.format(version=update.version)


def _prompt_action_text() -> str:
    return AUTO_UPDATE_ACTIONS_DETAIL


def _dismiss_checkbox_text(update: AvailableUpdate) -> str:
    return AUTO_UPDATE_DISMISS_CHECKBOX_TEMPLATE.format(version=update.version)


def _update_user_agent(current_version: str | None = None) -> str:
    normalized_version = str(current_version or current_game_version()).strip()
    return f"ArenaDuel/{normalized_version or DEFAULT_GAME_VERSION}"


def _try_parse_version_parts(version_text: str) -> tuple[int, ...] | None:
    normalized_text = str(version_text or "").strip()
    if not normalized_text or re.search(r"\d", normalized_text) is None:
        return None

    parts = [int(token) for token in re.split(r"[^0-9]+", normalized_text) if token]
    if not parts:
        return None

    return tuple(parts)


def _parse_version_parts(version_text: str) -> tuple[int, ...]:
    return _try_parse_version_parts(version_text) or (0,)


def _normalized_version_parts(version_text: str) -> tuple[int, ...]:
    parts = list(_parse_version_parts(version_text))
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def compare_semver(version_a: str, version_b: str) -> int | None:
    parts_a = _try_parse_version_parts(version_a)
    parts_b = _try_parse_version_parts(version_b)
    if parts_a is None or parts_b is None:
        return None

    normalized_a = list(parts_a)
    normalized_b = list(parts_b)
    max_length = max(len(normalized_a), len(normalized_b))
    normalized_a.extend([0] * (max_length - len(normalized_a)))
    normalized_b.extend([0] * (max_length - len(normalized_b)))

    tuple_a = tuple(normalized_a)
    tuple_b = tuple(normalized_b)
    if tuple_a < tuple_b:
        return -1
    if tuple_a > tuple_b:
        return 1
    return 0


def _is_valid_semver_text(version_text: str) -> bool:
    return compare_semver(version_text, version_text) is not None


def is_newer_version(remote_version: str, local_version: str) -> bool:
    comparison = compare_semver(remote_version, local_version)
    return comparison is not None and comparison > 0


def is_same_version(version_a: str, version_b: str) -> bool:
    comparison = compare_semver(version_a, version_b)
    return comparison is not None and comparison == 0


def _normalize_optional_url(raw_value: object) -> str:
    normalized_value = str(raw_value or "").strip()
    if not normalized_value:
        return ""

    parsed_url = urllib.parse.urlparse(normalized_value)
    if parsed_url.scheme and len(parsed_url.scheme) > 1:
        return normalized_value

    path_candidate = Path(normalized_value).expanduser()
    if (
        path_candidate.exists()
        or path_candidate.is_absolute()
        or normalized_value.startswith((".", "~"))
    ):
        try:
            return path_candidate.resolve(strict=False).as_uri()
        except ValueError:
            return normalized_value

    return normalized_value


def configured_update_manifest_url() -> str:
    runtime_config = load_runtime_config(include_session_overrides=False)
    return (
        _normalize_optional_url(os.environ.get(AUTO_UPDATE_MANIFEST_URL_ENV))
        or _normalize_optional_url(
            runtime_config.get(AUTO_UPDATE_MANIFEST_URL_CONFIG_KEY)
        )
        or DEFAULT_UPDATE_MANIFEST_URL
    )


def configured_update_page_url() -> str:
    runtime_config = load_runtime_config(include_session_overrides=False)
    return (
        _normalize_optional_url(os.environ.get(AUTO_UPDATE_PAGE_URL_ENV))
        or _normalize_optional_url(runtime_config.get(AUTO_UPDATE_PAGE_URL_CONFIG_KEY))
        or DEFAULT_UPDATE_PAGE_URL
    )


def _parse_manifest_remind_later_seconds(
    manifest_data: dict,
) -> int | None:
    seconds_raw = manifest_data.get("remind_later_seconds")
    if seconds_raw not in {None, ""}:
        try:
            remind_later_seconds = int(seconds_raw)
        except (TypeError, ValueError):
            remind_later_seconds = 0

        if remind_later_seconds > 0:
            return remind_later_seconds

    hours_raw = manifest_data.get("remind_later_hours")
    if hours_raw in {None, ""}:
        return None

    try:
        remind_later_hours = float(hours_raw)
    except (TypeError, ValueError):
        return None

    if remind_later_hours <= 0:
        return None

    return max(1, int(remind_later_hours * 60 * 60))


def _resolve_manifest_update_url(
    manifest_data: dict,
    default_update_url: str,
) -> str:
    candidate_keys: list[str] = []
    if sys.platform.startswith("win"):
        candidate_keys.extend(
            [
                "windows_installer_url",
                "windows_download_url",
            ]
        )

    candidate_keys.extend(
        [
            "installer_url",
            "download_url",
            "update_url",
        ]
    )

    for candidate_key in candidate_keys:
        candidate_url = _normalize_optional_url(manifest_data.get(candidate_key))
        if candidate_url:
            return candidate_url

    return str(default_update_url or "").strip()


def _normalize_optional_sha256(raw_value: object) -> str | None:
    normalized_value = str(raw_value or "").strip().lower()
    if not normalized_value:
        return None

    if re.fullmatch(r"[0-9a-f]{64}", normalized_value) is None:
        return None

    return normalized_value


def _resolve_manifest_installer_sha256(manifest_data: dict) -> str | None:
    for candidate_key in (
        "windows_installer_sha256",
        "installer_sha256",
        "download_sha256",
        "sha256",
    ):
        candidate_hash = _normalize_optional_sha256(manifest_data.get(candidate_key))
        if candidate_hash:
            return candidate_hash

    return None


def _normalize_release_notes(raw_value: object) -> tuple[str, ...]:
    if isinstance(raw_value, str):
        candidates = raw_value.splitlines()
    elif isinstance(raw_value, (list, tuple, set)):
        candidates = list(raw_value)
    else:
        return ()

    normalized_notes: list[str] = []

    def _service_current_version_text(service) -> str:
        current_version = getattr(service, "current_version", None)
        if isinstance(current_version, str) and current_version.strip():
            return current_version.strip()
        return current_game_version()

    for candidate in candidates:
        normalized_note = re.sub(r"^[-*\s]+", "", str(candidate or "").strip())
        if normalized_note:
            normalized_notes.append(normalized_note)

    return tuple(normalized_notes[:12])


def _resolve_manifest_release_notes(manifest_data: dict) -> tuple[str, ...]:
    for candidate_key in (
        "release_notes",
        "release_notes_lines",
        "notes",
        "changes",
        "changelog",
    ):
        notes = _normalize_release_notes(manifest_data.get(candidate_key))
        if notes:
            return notes

    return ()


def _local_installer_path(update_url: str) -> Path | None:
    normalized_url = _normalize_optional_url(update_url)
    if not normalized_url:
        return None

    parsed_url = urllib.parse.urlparse(normalized_url)
    if parsed_url.scheme == "file":
        local_path = urllib.request.url2pathname(parsed_url.path)
        if parsed_url.netloc and not local_path.startswith("\\\\"):
            local_path = f"\\\\{parsed_url.netloc}{local_path}"
        path_candidate = Path(local_path)
    elif not parsed_url.scheme or len(parsed_url.scheme) == 1:
        path_candidate = Path(normalized_url).expanduser()
    else:
        return None

    try:
        resolved_path = path_candidate.resolve(strict=False)
    except OSError:
        resolved_path = path_candidate

    if resolved_path.suffix.lower() not in LOCAL_INSTALLER_SUFFIXES:
        return None

    return resolved_path


def _is_remote_windows_installer_url(update_url: str) -> bool:
    normalized_url = _normalize_optional_url(update_url)
    if not normalized_url:
        return False

    parsed_url = urllib.parse.urlparse(normalized_url)
    if parsed_url.scheme not in {"http", "https"}:
        return False

    installer_name = _remote_installer_filename(normalized_url)
    if not installer_name:
        return False

    return Path(installer_name).suffix.lower() in LOCAL_INSTALLER_SUFFIXES


def _remote_installer_filename(update_url: str) -> str | None:
    parsed_url = urllib.parse.urlparse(_normalize_optional_url(update_url))
    candidate_name = Path(
        urllib.request.url2pathname(parsed_url.path or "")
    ).name.strip()
    if not candidate_name:
        return None

    candidate_suffix = Path(candidate_name).suffix.lower()
    if candidate_suffix not in LOCAL_INSTALLER_SUFFIXES:
        return None

    return candidate_name


def _response_content_length(response) -> int | None:
    header_value = None
    headers = getattr(response, "headers", None)
    if headers is not None:
        try:
            header_value = headers.get("Content-Length")
        except AttributeError:
            header_value = None

    if not header_value:
        getheader = getattr(response, "getheader", None)
        if getheader is not None:
            try:
                header_value = getheader("Content-Length")
            except TypeError:
                header_value = None

    try:
        content_length = int(header_value)
    except (TypeError, ValueError):
        return None

    if content_length <= 0:
        return None

    return content_length


def _format_download_size(size_in_bytes: int) -> str:
    normalized_size = max(0, int(size_in_bytes))
    units = ("o", "Ko", "Mo", "Go")
    size_value = float(normalized_size)
    selected_unit = units[0]

    for unit in units:
        selected_unit = unit
        if size_value < 1024 or unit == units[-1]:
            break
        size_value /= 1024

    if selected_unit == "o":
        return f"{int(size_value)} {selected_unit}"
    return f"{size_value:.1f} {selected_unit}"


def _format_download_progress(snapshot: DownloadProgressSnapshot) -> str:
    downloaded_text = _format_download_size(snapshot.bytes_downloaded)
    if snapshot.total_bytes is None:
        return f"{downloaded_text} téléchargés"

    total_text = _format_download_size(snapshot.total_bytes)
    return f"{downloaded_text} / {total_text}"


def _file_sha256(file_path: Path) -> str | None:
    digest = hashlib.sha256()

    try:
        with open(file_path, "rb") as file_handle:
            while True:
                chunk = file_handle.read(AUTO_UPDATE_DOWNLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                digest.update(chunk)
    except OSError:
        return None

    return digest.hexdigest()


def _installer_hash_matches(
    installer_path: Path,
    installer_sha256: str | None,
) -> bool:
    expected_hash = _normalize_optional_sha256(installer_sha256)
    if expected_hash is None:
        return True

    actual_hash = _file_sha256(installer_path)
    if actual_hash is None:
        return False

    return actual_hash == expected_hash


def _download_remote_installer(
    update_url: str,
    *,
    timeout_seconds: float = AUTO_UPDATE_DOWNLOAD_TIMEOUT_SECONDS,
    progress_callback=None,
    installer_sha256: str | None = None,
) -> Path | None:
    normalized_url = _normalize_optional_url(update_url)
    if not normalized_url:
        return None

    parsed_url = urllib.parse.urlparse(normalized_url)
    if parsed_url.scheme not in {"http", "https"}:
        return None

    installer_name = _remote_installer_filename(normalized_url)
    if not installer_name:
        return None

    download_dir = Path(runtime_user_file_path(AUTO_UPDATE_DOWNLOAD_DIRNAME))
    target_path = download_dir / installer_name
    temp_path = target_path.with_suffix(f"{target_path.suffix}.download")
    request = urllib.request.Request(
        normalized_url,
        headers={"User-Agent": _update_user_agent()},
    )

    try:
        download_dir.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            content_length = _response_content_length(response)
            bytes_downloaded = 0
            if progress_callback is not None:
                progress_callback(bytes_downloaded, content_length)
            with open(temp_path, "wb") as file_handle:
                while True:
                    chunk = response.read(AUTO_UPDATE_DOWNLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    file_handle.write(chunk)
                    bytes_downloaded += len(chunk)
                    if progress_callback is not None:
                        progress_callback(bytes_downloaded, content_length)

        if not _installer_hash_matches(temp_path, installer_sha256):
            try:
                temp_path.unlink()
            except OSError:
                pass
            return None

        temp_path.replace(target_path)
    except (
        OSError,
        ValueError,
        urllib.error.URLError,
    ):
        try:
            temp_path.unlink()
        except OSError:
            pass
        return None

    return target_path


def auto_update_state_path() -> str:
    return runtime_user_file_path(AUTO_UPDATE_STATE_FILENAME)


def load_auto_update_state(path: str | None = None) -> AutoUpdateState:
    state_file = Path(path or auto_update_state_path())
    if not state_file.exists():
        return AutoUpdateState()

    try:
        with open(state_file, "r", encoding="utf-8") as file_handle:
            raw_state = json.load(file_handle)
    except (OSError, json.JSONDecodeError):
        return AutoUpdateState()

    if not isinstance(raw_state, dict):
        return AutoUpdateState()

    snoozed_version = str(raw_state.get("snoozed_version") or "").strip()
    dismissed_version = str(raw_state.get("dismissed_version") or "").strip()
    remind_after_raw = raw_state.get("remind_after_epoch") or 0
    launches_until_prompt_raw = raw_state.get("launches_until_prompt") or 0
    try:
        remind_after_epoch = max(0, int(remind_after_raw))
    except (TypeError, ValueError):
        remind_after_epoch = 0

    try:
        launches_until_prompt = max(0, int(launches_until_prompt_raw))
    except (TypeError, ValueError):
        launches_until_prompt = 0

    if (
        not snoozed_version
        and remind_after_epoch <= 0
        and launches_until_prompt <= 0
        and not dismissed_version
    ):
        return AutoUpdateState()

    return AutoUpdateState(
        snoozed_version=snoozed_version,
        remind_after_epoch=remind_after_epoch,
        launches_until_prompt=launches_until_prompt,
        dismissed_version=dismissed_version,
    )


def normalize_auto_update_state(state: AutoUpdateState) -> AutoUpdateState:
    dismissed_version = str(state.dismissed_version or "").strip()
    if dismissed_version and not _is_valid_semver_text(dismissed_version):
        dismissed_version = ""

    if (
        state.remind_after_epoch > 0
        and state.launches_until_prompt <= 0
        and state.snoozed_version
        and not dismissed_version
    ):
        return AutoUpdateState(
            snoozed_version=state.snoozed_version,
            remind_after_epoch=0,
            launches_until_prompt=0,
            dismissed_version=dismissed_version,
        )

    if dismissed_version != str(state.dismissed_version or "").strip():
        return AutoUpdateState(
            snoozed_version=state.snoozed_version,
            remind_after_epoch=state.remind_after_epoch,
            launches_until_prompt=state.launches_until_prompt,
            dismissed_version=dismissed_version,
        )

    return state


def get_dismissed_version(path: str | None = None) -> str:
    raw_state = load_auto_update_state(path)
    normalized_state = normalize_auto_update_state(raw_state)
    if normalized_state != raw_state:
        save_auto_update_state(normalized_state, path)
    return str(normalized_state.dismissed_version or "").strip()


def set_dismissed_version(version: str, path: str | None = None) -> str:
    normalized_version = str(version or "").strip()
    if normalized_version and not _is_valid_semver_text(normalized_version):
        normalized_version = ""

    state = AutoUpdateState(dismissed_version=normalized_version)
    save_auto_update_state(state, path)
    return normalized_version


def save_auto_update_state(
    state: AutoUpdateState,
    path: str | None = None,
) -> str:
    state_file = Path(path or auto_update_state_path())
    payload = {
        "snoozed_version": str(state.snoozed_version or "").strip(),
        "remind_after_epoch": max(0, int(state.remind_after_epoch)),
        "launches_until_prompt": max(0, int(state.launches_until_prompt)),
        "dismissed_version": str(state.dismissed_version or "").strip(),
    }

    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(state_file, "w", encoding="utf-8") as file_handle:
            json.dump(payload, file_handle, ensure_ascii=False, indent=2)
    except OSError:
        return str(state_file)

    return str(state_file)


def clear_auto_update_state(path: str | None = None) -> str:
    state_file = Path(path or auto_update_state_path())
    try:
        state_file.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass
    return str(state_file)


def fetch_remote_update_manifest(
    manifest_url: str | None = None,
    *,
    default_update_url: str | None = None,
    timeout_seconds: float = AUTO_UPDATE_CHECK_TIMEOUT_SECONDS,
) -> UpdateManifest | None:
    normalized_manifest_url = _normalize_optional_url(
        manifest_url or configured_update_manifest_url()
    )
    if not normalized_manifest_url:
        return None

    resolved_default_update_url = _normalize_optional_url(
        default_update_url or configured_update_page_url()
    )

    request = urllib.request.Request(
        normalized_manifest_url,
        headers={"User-Agent": _update_user_agent()},
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout_seconds,
        ) as response:
            payload = response.read().decode("utf-8")
        manifest_data = json.loads(payload)
    except (
        OSError,
        UnicodeDecodeError,
        ValueError,
        urllib.error.URLError,
    ):
        return None

    if not isinstance(manifest_data, dict):
        return None

    version_text = str(manifest_data.get("version") or "").strip()
    if not version_text:
        return None

    update_url = _resolve_manifest_update_url(
        manifest_data,
        resolved_default_update_url,
    )
    if not update_url:
        update_url = resolved_default_update_url

    remind_later_seconds = _parse_manifest_remind_later_seconds(manifest_data)
    installer_sha256 = _resolve_manifest_installer_sha256(manifest_data)
    release_notes = _resolve_manifest_release_notes(manifest_data)

    return UpdateManifest(
        version=version_text,
        update_url=update_url,
        remind_later_seconds=remind_later_seconds,
        installer_sha256=installer_sha256,
        release_notes=release_notes,
    )


def check_for_available_update(
    *,
    current_version: str | None = None,
    manifest_url: str | None = None,
    default_update_url: str | None = None,
    timeout_seconds: float = AUTO_UPDATE_CHECK_TIMEOUT_SECONDS,
) -> AvailableUpdate | None:
    resolved_current_version = str(current_version or current_game_version()).strip()
    manifest = fetch_remote_update_manifest(
        manifest_url,
        default_update_url=default_update_url,
        timeout_seconds=timeout_seconds,
    )
    if manifest is None:
        return None

    if not is_newer_version(manifest.version, resolved_current_version):
        return None

    return AvailableUpdate(
        version=manifest.version,
        update_url=manifest.update_url,
        remind_later_seconds=manifest.remind_later_seconds,
        installer_sha256=manifest.installer_sha256,
        release_notes=manifest.release_notes,
    )


def _notice_detail_text(update: AvailableUpdate) -> str:
    if not update.release_notes:
        return _notice_action_text()

    first_note = update.release_notes[0]
    if len(update.release_notes) == 1:
        return f"Nouveauté : {first_note}"

    return f"{len(update.release_notes)} nouveautés, dont : {first_note}"


def _service_current_version_text(service) -> str:
    current_version = getattr(service, "current_version", None)
    if isinstance(current_version, str) and current_version.strip():
        return current_version.strip()
    return current_game_version()


def open_update_page(
    update_url: str,
    *,
    installer_sha256: str | None = None,
) -> bool:
    normalized_url = _normalize_optional_url(update_url)
    if not normalized_url:
        return False

    local_installer_path = _local_installer_path(normalized_url)
    if local_installer_path is not None and sys.platform.startswith("win"):
        if not _installer_hash_matches(local_installer_path, installer_sha256):
            return False
        try:
            os.startfile(str(local_installer_path))
            return True
        except (AttributeError, OSError):
            pass

    if sys.platform.startswith("win"):
        downloaded_installer_path = _download_remote_installer(
            normalized_url,
            installer_sha256=installer_sha256,
        )
        if downloaded_installer_path is not None:
            try:
                os.startfile(str(downloaded_installer_path))
                return True
            except (AttributeError, OSError):
                pass

    try:
        return bool(webbrowser.open_new_tab(normalized_url))
    except (OSError, webbrowser.Error):
        return False


def _center_fixed_window(window, *, width: int, height: int) -> None:
    screen_width = max(width, window.winfo_screenwidth())
    screen_height = max(height, window.winfo_screenheight())
    origin_x = max(0, (screen_width - width) // 2)
    origin_y = max(0, (screen_height - height) // 2 - 20)

    window.geometry(f"{width}x{height}+{origin_x}+{origin_y}")
    try:
        window.resizable(False, False)
        window.minsize(width, height)
        window.maxsize(width, height)
    except TclError:
        pass


def cancel_pending_after_callbacks(widget) -> None:
    try:
        callback_ids = widget.tk.call("after", "info")
    except (AttributeError, TclError):
        return

    if not callback_ids:
        return

    if isinstance(callback_ids, str):
        callback_ids = (callback_ids,)

    for callback_id in tuple(callback_ids):
        try:
            widget.after_cancel(callback_id)
        except TclError:
            continue


def _enable_accessible_focus_ring(
    widget, *, focus_color: str = PALETTE["gold_hover"]
) -> None:
    try:
        normal_border_color = widget.cget("border_color")
        normal_border_width = int(widget.cget("border_width") or 0)
    except (AttributeError, TclError, TypeError, ValueError):
        return

    try:
        widget.configure(takefocus=True)
    except (AttributeError, TclError, ValueError):
        pass

    def _handle_focus_in(_event=None) -> None:
        try:
            widget.configure(
                border_color=focus_color,
                border_width=max(2, normal_border_width),
            )
        except TclError:
            pass

    def _handle_focus_out(_event=None) -> None:
        try:
            widget.configure(
                border_color=normal_border_color,
                border_width=normal_border_width,
            )
        except TclError:
            pass

    try:
        widget.bind("<FocusIn>", _handle_focus_in, add="+")
        widget.bind("<FocusOut>", _handle_focus_out, add="+")
    except TclError:
        return


class AutoUpdateNotice(ctk.CTkFrame):
    def __init__(
        self,
        master=None,
        *,
        update: AvailableUpdate,
        on_update,
        on_later,
        on_never,
        width: int = AUTO_UPDATE_NOTICE_MIN_WIDTH,
    ):
        super().__init__(master, corner_radius=22, width=width)
        style_frame(
            self,
            tone="panel_deep",
            border_color=PALETTE["gold_dim"],
            border_width=1,
        )

        self._on_update = on_update
        self._on_later = on_later
        self._on_never = on_never
        self._update = update
        self.update_button = None
        self.later_button = None
        self.dismiss_button = None
        self.detail_label = None

        self.grid_columnconfigure(0, weight=1)
        self._build_ui()

    def _build_ui(self) -> None:
        create_badge(self, AUTO_UPDATE_BADGE_TEXT, tone="gold").grid(
            row=0,
            column=0,
            padx=22,
            pady=(18, 10),
            sticky="w",
        )

        ctk.CTkLabel(
            self,
            text=AUTO_UPDATE_NOTICE_TEXT,
            font=TYPOGRAPHY["body_bold"],
            text_color=PALETTE["text"],
            justify="left",
            wraplength=340,
        ).grid(row=1, column=0, padx=22, pady=(0, 8), sticky="ew")

        ctk.CTkLabel(
            self,
            text=_prompt_heading_text(self._update),
            font=TYPOGRAPHY["small_bold"],
            text_color=PALETTE["gold"],
            justify="left",
            wraplength=340,
        ).grid(row=2, column=0, padx=22, pady=(0, 6), sticky="ew")

        self.detail_label = ctk.CTkLabel(
            self,
            text=_notice_detail_text(self._update),
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            justify="left",
            wraplength=340,
        )
        self.detail_label.grid(
            row=3,
            column=0,
            padx=22,
            pady=(0, 14),
            sticky="ew",
        )

        button_row = ctk.CTkFrame(self, fg_color="transparent")
        button_row.grid(
            row=4,
            column=0,
            padx=22,
            pady=(0, 18),
            sticky="ew",
        )
        button_row.grid_columnconfigure(0, weight=1)
        button_row.grid_columnconfigure(1, weight=1)

        self.update_button = create_button(
            button_row,
            AUTO_UPDATE_PRIMARY_ACTION_TEXT,
            self._handle_update,
            variant="primary",
            height=44,
        )
        self.update_button.grid(
            row=0,
            column=0,
            padx=(0, 8),
            sticky="ew",
        )
        _enable_accessible_focus_ring(self.update_button)

        self.later_button = create_button(
            button_row,
            _defer_action_text(),
            self._handle_later,
            variant="secondary",
            height=44,
        )
        self.later_button.grid(
            row=0,
            column=1,
            padx=(8, 0),
            sticky="ew",
        )
        _enable_accessible_focus_ring(self.later_button)

        self.dismiss_button = create_button(
            button_row,
            AUTO_UPDATE_NOTICE_DISMISS_ACTION_TEXT,
            self._handle_never,
            variant="subtle",
            height=40,
        )
        self.dismiss_button.grid(
            row=1,
            column=0,
            columnspan=2,
            padx=0,
            pady=(10, 0),
            sticky="ew",
        )
        _enable_accessible_focus_ring(self.dismiss_button)

    def _handle_update(self) -> None:
        play_transition()
        self._on_update()
        self.dismiss()

    def _handle_later(self) -> None:
        play_click()
        self._on_later()
        self.dismiss()

    def _handle_never(self) -> None:
        play_click()
        self._on_never()
        self.dismiss()

    def dismiss(self) -> None:
        try:
            if self.winfo_exists():
                self.destroy()
        except TclError:
            pass


class AutoUpdatePromptApp(ctk.CTk):
    def __init__(
        self,
        service,
        update: AvailableUpdate,
    ):
        super().__init__()
        self._service = service
        self._update = update
        self.selection: str | None = None
        self._close_after_id = None
        self._download_poll_after_id = None
        self._download_queue: "queue.SimpleQueue[tuple]" = queue.SimpleQueue()
        self.update_button = None
        self.later_button = None
        self.dismiss_checkbox = None
        self.dismiss_hint_label = None
        self.dismiss_shell = None
        self._dismiss_current_version_var = ctk.BooleanVar(value=False)
        self.shell = None
        self.hero_shell = None
        self.actions_shell = None
        self.title_label = None
        self.version_label = None
        self.detail_label = None
        self.current_version_card = None
        self.available_version_card = None
        self.button_row = None
        self.progress_shell = None
        self.progress_bar = None
        self.progress_value_label = None
        self.progress_status_label = None
        self.notes_shell = None
        self._progress_mode = "determinate"

        style_window(self)
        self.configure(fg_color=PALETTE["launcher_blend"])
        self.title(AUTO_UPDATE_PROMPT_TITLE)
        apply_window_icon(self, default=True, retry_after_ms=220)
        _center_fixed_window(
            self,
            width=AUTO_UPDATE_PROMPT_WIDTH,
            height=AUTO_UPDATE_PROMPT_HEIGHT,
        )
        self.protocol("WM_DELETE_WINDOW", self._handle_later)

        self._build_ui()
        present_window(self)
        try:
            if self.update_button is not None:
                self.update_button.focus_set()
        except TclError:
            pass
        _schedule_window_sound(self, tone="alert")

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        shell = ctk.CTkFrame(self, corner_radius=28)
        style_frame(
            shell,
            tone="panel_deep",
            border_color=PALETTE["gold_dim"],
            border_width=1,
        )
        shell.grid(row=0, column=0, padx=22, pady=22, sticky="nsew")
        shell.grid_columnconfigure(0, weight=1)
        self.shell = shell

        create_badge(shell, AUTO_UPDATE_BADGE_TEXT, tone="gold").grid(
            row=0,
            column=0,
            padx=26,
            pady=(24, 12),
            sticky="w",
        )

        hero_shell = ctk.CTkFrame(shell, corner_radius=22)
        style_frame(
            hero_shell,
            tone="panel",
            border_color=PALETTE["gold_dim"],
            border_width=1,
        )
        hero_shell.grid(row=1, column=0, padx=26, pady=(0, 18), sticky="ew")
        hero_shell.grid_columnconfigure(0, weight=1)
        hero_shell.grid_columnconfigure(1, weight=1)
        self.hero_shell = hero_shell

        self.title_label = ctk.CTkLabel(
            hero_shell,
            text=_prompt_heading_text(self._update),
            font=TYPOGRAPHY["section"],
            text_color=PALETTE["text"],
            justify="left",
            wraplength=520,
        )
        self.title_label.grid(
            row=0, column=0, columnspan=2, padx=22, pady=(18, 10), sticky="w"
        )

        self.version_label = ctk.CTkLabel(
            hero_shell,
            text=AUTO_UPDATE_PROMPT_SUBTITLE,
            font=TYPOGRAPHY["body_bold"],
            text_color=PALETTE["gold"],
            justify="left",
            wraplength=520,
        )
        self.version_label.grid(
            row=1, column=0, columnspan=2, padx=22, pady=(0, 16), sticky="w"
        )

        self.current_version_card = self._build_version_card(
            hero_shell,
            row=2,
            column=0,
            label_text=AUTO_UPDATE_CURRENT_VERSION_LABEL,
            value_text=_service_current_version_text(self._service),
        )
        self.available_version_card = self._build_version_card(
            hero_shell,
            row=2,
            column=1,
            label_text=AUTO_UPDATE_AVAILABLE_VERSION_LABEL,
            value_text=self._update.version,
        )

        actions_shell = ctk.CTkFrame(shell, corner_radius=18)
        style_frame(
            actions_shell,
            tone="panel",
            border_color=PALETTE["divider"],
            border_width=1,
        )
        actions_shell.grid(
            row=2,
            column=0,
            padx=26,
            pady=(0, 26),
            sticky="ew",
        )
        actions_shell.grid_columnconfigure(0, weight=1)
        self.actions_shell = actions_shell

        ctk.CTkLabel(
            actions_shell,
            text=AUTO_UPDATE_ACTIONS_TITLE,
            font=TYPOGRAPHY["small_bold"],
            text_color=PALETTE["gold"],
            justify="left",
        ).grid(row=0, column=0, padx=18, pady=(16, 8), sticky="w")

        self.detail_label = ctk.CTkLabel(
            actions_shell,
            text=_prompt_action_text(),
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            justify="left",
            wraplength=500,
        )
        self.detail_label.grid(row=1, column=0, padx=18, pady=(0, 14), sticky="w")

        button_row = ctk.CTkFrame(actions_shell, fg_color="transparent")
        button_row.grid(
            row=2,
            column=0,
            padx=18,
            pady=(0, 18),
            sticky="ew",
        )
        button_row.grid_columnconfigure(0, weight=1)
        button_row.grid_columnconfigure(1, weight=1)
        self.button_row = button_row

        self.update_button = create_button(
            button_row,
            AUTO_UPDATE_PRIMARY_ACTION_TEXT,
            self._handle_update,
            variant="primary",
            height=50,
        )
        self.update_button.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        _enable_accessible_focus_ring(self.update_button)

        self.later_button = create_button(
            button_row,
            _defer_action_text(),
            self._handle_later,
            variant="secondary",
            height=50,
        )
        self.later_button.grid(row=0, column=1, padx=(10, 0), sticky="ew")
        _enable_accessible_focus_ring(self.later_button)

        dismiss_shell = ctk.CTkFrame(actions_shell, fg_color="transparent")
        dismiss_shell.grid(
            row=3,
            column=0,
            padx=18,
            pady=(0, 18),
            sticky="ew",
        )
        dismiss_shell.grid_columnconfigure(0, weight=1)
        self.dismiss_shell = dismiss_shell

        self.dismiss_checkbox = ctk.CTkCheckBox(
            dismiss_shell,
            text=_dismiss_checkbox_text(self._update),
            variable=self._dismiss_current_version_var,
            onvalue=True,
            offvalue=False,
            fg_color=PALETTE["gold"],
            hover_color=PALETTE["gold_hover"],
            border_color=PALETTE["border_strong"],
            text_color=PALETTE["text"],
            font=TYPOGRAPHY["small_bold"],
        )
        style_checkbox(self.dismiss_checkbox)
        self.dismiss_checkbox.grid(row=0, column=0, sticky="w")
        _enable_accessible_focus_ring(self.dismiss_checkbox)

        self.dismiss_hint_label = ctk.CTkLabel(
            dismiss_shell,
            text=AUTO_UPDATE_DISMISS_HINT_TEXT,
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            justify="left",
            wraplength=500,
        )
        self.dismiss_hint_label.grid(row=1, column=0, pady=(6, 0), sticky="w")

        if self._update.release_notes:
            self._build_release_notes_ui(shell, row=3)

    def _build_version_card(
        self,
        parent,
        *,
        row: int,
        column: int,
        label_text: str,
        value_text: str,
    ):
        card = ctk.CTkFrame(parent, corner_radius=18)
        style_frame(
            card,
            tone="panel_soft",
            border_color=PALETTE["divider"],
            border_width=1,
        )
        card.grid(
            row=row,
            column=column,
            padx=(22, 10) if column == 0 else (10, 22),
            pady=(0, 20),
            sticky="ew",
        )
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text=label_text,
            font=TYPOGRAPHY["small_bold"],
            text_color=PALETTE["text_soft"],
            justify="left",
        ).grid(row=0, column=0, padx=16, pady=(14, 4), sticky="w")

        ctk.CTkLabel(
            card,
            text=value_text,
            font=TYPOGRAPHY["subtitle"],
            text_color=PALETTE["text"],
            justify="left",
            wraplength=180,
        ).grid(row=1, column=0, padx=16, pady=(0, 14), sticky="w")
        return card

    def _build_release_notes_ui(self, shell, *, row: int) -> None:
        notes_shell = ctk.CTkFrame(shell, corner_radius=18)
        style_frame(
            notes_shell,
            tone="panel",
            border_color=PALETTE["divider"],
            border_width=0,
        )
        notes_shell.grid(row=row, column=0, padx=26, pady=(0, 20), sticky="ew")
        notes_shell.grid_columnconfigure(0, weight=1)
        self.notes_shell = notes_shell

        ctk.CTkLabel(
            notes_shell,
            text=AUTO_UPDATE_CHANGELOG_TITLE,
            font=TYPOGRAPHY["small_bold"],
            text_color=PALETTE["gold"],
            justify="left",
        ).grid(row=0, column=0, padx=18, pady=(16, 10), sticky="w")

        notes_body = ctk.CTkFrame(notes_shell, corner_radius=14)
        style_frame(
            notes_body,
            tone="panel_soft",
            border_color=PALETTE["divider"],
            border_width=1,
        )
        notes_body.grid(row=1, column=0, padx=18, pady=(0, 16), sticky="ew")
        notes_body.grid_columnconfigure(0, weight=1)

        displayed_notes = tuple(self._update.release_notes[:3])
        hidden_notes_count = max(
            0, len(self._update.release_notes) - len(displayed_notes)
        )

        for row_index, note in enumerate(displayed_notes):
            note_row = ctk.CTkFrame(notes_body, fg_color="transparent")
            note_row.grid(row=row_index, column=0, padx=12, pady=(0, 6), sticky="ew")
            note_row.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                note_row,
                text="•",
                font=TYPOGRAPHY["small_bold"],
                text_color=PALETTE["gold"],
                justify="left",
            ).grid(row=0, column=0, padx=(0, 8), sticky="nw")

            ctk.CTkLabel(
                note_row,
                text=note,
                font=TYPOGRAPHY["small"],
                text_color=PALETTE["text_soft"],
                justify="left",
                wraplength=390,
            ).grid(row=0, column=1, sticky="ew")

        if hidden_notes_count > 0:
            ctk.CTkLabel(
                notes_body,
                text=(
                    f"+ {hidden_notes_count} autre{'s' if hidden_notes_count > 1 else ''} "
                    f"nouveauté{'s' if hidden_notes_count > 1 else ''}"
                ),
                font=TYPOGRAPHY["small_bold"],
                text_color=PALETTE["gold"],
                justify="left",
            ).grid(
                row=len(displayed_notes),
                column=0,
                padx=16,
                pady=(2, 12),
                sticky="w",
            )

    def _set_actions_enabled(self, enabled: bool) -> None:
        new_state = "normal" if enabled else "disabled"
        for widget in (self.update_button, self.later_button, self.dismiss_checkbox):
            if widget is None:
                continue
            try:
                if widget.winfo_exists():
                    widget.configure(state=new_state)
            except TclError:
                continue

    def _set_progress_mode(self, mode: str) -> None:
        if self.progress_bar is None or self._progress_mode == mode:
            return

        try:
            if self._progress_mode == "indeterminate":
                self.progress_bar.stop()
            self.progress_bar.configure(mode=mode)
            if mode == "indeterminate":
                self.progress_bar.start()
            self._progress_mode = mode
        except TclError:
            pass

    def _ensure_progress_ui(self) -> None:
        if self.progress_shell is not None:
            try:
                self.progress_shell.grid()
            except TclError:
                pass
            return

        if self.actions_shell is None:
            return

        progress_shell = ctk.CTkFrame(self.actions_shell, fg_color="transparent")
        progress_shell.grid(
            row=2,
            column=0,
            padx=18,
            pady=(0, 18),
            sticky="ew",
        )
        progress_shell.grid_columnconfigure(0, weight=1)
        self.progress_shell = progress_shell

        self.progress_bar = ctk.CTkProgressBar(progress_shell, height=14)
        self.progress_bar.grid(row=0, column=0, sticky="ew")
        self.progress_bar.set(0)

        self.progress_value_label = ctk.CTkLabel(
            progress_shell,
            text="0 o téléchargés",
            font=TYPOGRAPHY["small_bold"],
            text_color=PALETTE["gold"],
            justify="left",
        )
        self.progress_value_label.grid(
            row=1,
            column=0,
            pady=(10, 4),
            sticky="w",
        )

        self.progress_status_label = ctk.CTkLabel(
            progress_shell,
            text=AUTO_UPDATE_DOWNLOAD_DETAIL,
            font=TYPOGRAPHY["small"],
            text_color=PALETTE["text_soft"],
            justify="left",
            wraplength=500,
        )
        self.progress_status_label.grid(row=2, column=0, sticky="w")

    def _show_download_state(self, detail_text: str) -> None:
        if self.title_label is not None:
            self.title_label.configure(text=AUTO_UPDATE_DOWNLOAD_TITLE)
        if self.version_label is not None:
            self.version_label.configure(
                text=f"Version {self._update.version} en préparation."
            )
        if self.detail_label is not None:
            self.detail_label.configure(text=detail_text)
        if self.button_row is not None:
            self.button_row.grid_remove()
        if self.dismiss_shell is not None:
            self.dismiss_shell.grid_remove()
        self._ensure_progress_ui()

    def _cancel_download_poll(self) -> None:
        if self._download_poll_after_id is None:
            return

        try:
            self.after_cancel(self._download_poll_after_id)
        except TclError:
            pass
        self._download_poll_after_id = None

    def _schedule_download_poll(
        self, delay_ms: int = AUTO_UPDATE_DOWNLOAD_POLL_MS
    ) -> None:
        self._cancel_download_poll()
        try:
            self._download_poll_after_id = self.after(
                delay_ms, self._poll_download_queue
            )
        except TclError:
            self._download_poll_after_id = None

    def _apply_download_progress(
        self,
        bytes_downloaded: int,
        total_bytes: int | None,
    ) -> None:
        self._ensure_progress_ui()
        if self.progress_bar is None:
            return

        snapshot = DownloadProgressSnapshot(
            bytes_downloaded=max(0, int(bytes_downloaded)),
            total_bytes=(None if total_bytes is None else max(0, int(total_bytes))),
        )

        if snapshot.total_bytes:
            self._set_progress_mode("determinate")
            self.progress_bar.set(
                min(1.0, snapshot.bytes_downloaded / snapshot.total_bytes)
            )
        else:
            self._set_progress_mode("indeterminate")

        if self.progress_value_label is not None:
            self.progress_value_label.configure(
                text=_format_download_progress(snapshot)
            )
        if self.progress_status_label is not None:
            self.progress_status_label.configure(
                text="Téléchargement de l'installateur Windows..."
            )

    def _download_and_launch_worker(self) -> None:
        normalized_url = _normalize_optional_url(self._update.update_url)

        def _report_progress(bytes_downloaded: int, total_bytes: int | None) -> None:
            self._download_queue.put(("progress", bytes_downloaded, total_bytes))

        installer_path = _download_remote_installer(
            normalized_url,
            progress_callback=_report_progress,
            installer_sha256=self._update.installer_sha256,
        )
        if installer_path is not None:
            try:
                os.startfile(str(installer_path))
                self._download_queue.put(("done", True, str(installer_path), False))
                return
            except (AttributeError, OSError):
                pass

        try:
            browser_opened = bool(webbrowser.open_new_tab(normalized_url))
        except (OSError, webbrowser.Error):
            browser_opened = False

        self._download_queue.put(("done", browser_opened, None, browser_opened))

    def _finish_download_flow(
        self,
        success: bool,
        installer_path: str | None,
        used_browser: bool,
    ) -> None:
        self._cancel_download_poll()
        self._set_progress_mode("determinate")

        if success:
            if self.progress_bar is not None and not used_browser:
                self.progress_bar.set(1)
            if self.progress_status_label is not None:
                self.progress_status_label.configure(
                    text=(
                        "La page de mise à jour s'ouvre dans le navigateur."
                        if used_browser
                        else "L'installateur Windows va s'ouvrir."
                    )
                )
            if self.progress_value_label is not None:
                self.progress_value_label.configure(
                    text=(
                        AUTO_UPDATE_DOWNLOAD_BROWSER_FALLBACK_TEXT
                        if used_browser
                        else (
                            Path(installer_path).name
                            if installer_path
                            else "Installateur prêt"
                        )
                    )
                )
            if self.detail_label is not None:
                self.detail_label.configure(
                    text=(
                        AUTO_UPDATE_DOWNLOAD_BROWSER_FALLBACK_DETAIL
                        if used_browser
                        else "Téléchargement terminé. Arena Duel passe maintenant la main à l'installateur."
                    )
                )
            self._schedule_close_prompt()
            return

        if self.progress_shell is not None:
            self.progress_shell.grid_remove()
        if self.button_row is not None:
            self.button_row.grid()
        if self.dismiss_shell is not None:
            self.dismiss_shell.grid()
        self.selection = None
        self._set_actions_enabled(True)
        if self.title_label is not None:
            self.title_label.configure(text=AUTO_UPDATE_NOTICE_TEXT)
        if self.version_label is not None:
            self.version_label.configure(
                text=f"Version {self._update.version} prête à être installée."
            )
        if self.detail_label is not None:
            self.detail_label.configure(
                text=(
                    "Impossible d'ouvrir la mise à jour. Réessaie ou reporte cette mise à jour pour continuer vers le menu."
                )
            )
        play_alert()

    def _poll_download_queue(self) -> None:
        self._download_poll_after_id = None
        while True:
            try:
                event = self._download_queue.get_nowait()
            except queue.Empty:
                break

            event_type = event[0]
            if event_type == "progress":
                _, bytes_downloaded, total_bytes = event
                self._apply_download_progress(bytes_downloaded, total_bytes)
                continue

            if event_type == "done":
                _, success, installer_path, used_browser = event
                self._finish_download_flow(success, installer_path, used_browser)
                return

        self._schedule_download_poll()

    def _start_remote_download_flow(self) -> None:
        self._show_download_state(AUTO_UPDATE_DOWNLOAD_DETAIL)
        self._apply_download_progress(0, None)
        self._schedule_download_poll(0)
        worker = threading.Thread(
            target=self._download_and_launch_worker,
            name="arena-remote-update-download",
            daemon=True,
        )
        worker.start()

    def _schedule_close_prompt(self) -> None:
        if self._close_after_id is not None:
            try:
                self.after_cancel(self._close_after_id)
            except TclError:
                pass
            self._close_after_id = None

        try:
            self._close_after_id = self.after(
                AUTO_UPDATE_PROMPT_CLOSE_DELAY_MS,
                self._close_prompt,
            )
        except TclError:
            self._close_prompt()

    def _handle_update(self) -> None:
        if self.selection is not None:
            return

        play_transition()
        self.selection = "update"
        self._set_actions_enabled(False)
        if sys.platform.startswith("win") and _is_remote_windows_installer_url(
            self._update.update_url
        ):
            self._start_remote_download_flow()
            return
        self._service.launch_update(self._update)
        self._schedule_close_prompt()

    def _handle_later(self) -> None:
        if self.selection is not None:
            return

        play_click()
        self.selection = "later"
        self._set_actions_enabled(False)
        dismiss_current_version = False
        if self._dismiss_current_version_var is not None:
            try:
                dismiss_current_version = bool(self._dismiss_current_version_var.get())
            except TclError:
                dismiss_current_version = False

        if dismiss_current_version:
            self._service.dismiss_update_offer(self._update)
        else:
            self._service.defer_update(self._update)
        self._schedule_close_prompt()

    def _close_prompt(self) -> None:
        self._close_after_id = None
        try:
            self.quit()
        except TclError:
            pass

        self.destroy()

    def destroy(self):
        if self._close_after_id is not None:
            try:
                self.after_cancel(self._close_after_id)
            except TclError:
                pass
            self._close_after_id = None

        self._cancel_download_poll()
        if self.progress_bar is not None and self._progress_mode == "indeterminate":
            try:
                self.progress_bar.stop()
            except TclError:
                pass

        cancel_pending_after_callbacks(self)
        try:
            super().destroy()
        except TclError:
            pass


class AutoUpdateService:
    def __init__(
        self,
        *,
        current_version: str | None = None,
        manifest_url: str | None = None,
        default_update_url: str | None = None,
        timeout_seconds: float = AUTO_UPDATE_CHECK_TIMEOUT_SECONDS,
        poll_interval_ms: int = AUTO_UPDATE_POLL_MS,
        remind_later_seconds: int = AUTO_UPDATE_REMIND_LATER_SECONDS,
        reprompt_after_launches: int = AUTO_UPDATE_REPROMPT_AFTER_LAUNCHES,
        state_path: str | None = None,
        now_provider=None,
    ):
        self._current_version = str(current_version or current_game_version()).strip()
        self._manifest_url = manifest_url or configured_update_manifest_url()
        self._default_update_url = default_update_url or configured_update_page_url()
        self._timeout_seconds = timeout_seconds
        self._poll_interval_ms = poll_interval_ms
        self._remind_later_seconds = max(0, int(remind_later_seconds))
        self._reprompt_after_launches = max(1, int(reprompt_after_launches))
        self._state_path = state_path or auto_update_state_path()
        self._now_provider = now_provider or time.time
        self._result_queue: "queue.SimpleQueue[AvailableUpdate | None]" = (
            queue.SimpleQueue()
        )
        self._check_started = False
        self._check_completed = False
        self._available_update: AvailableUpdate | None = None
        self._offer_resolved = False
        self._notice_window = None
        self._snoozed_state = normalize_auto_update_state(
            load_auto_update_state(self._state_path)
        )
        self._persist_state()
        self._consume_launch_reprompt()

    @property
    def current_version(self) -> str:
        return self._current_version

    def start_background_check(self) -> None:
        if self._check_started:
            return

        self._check_started = True
        worker = threading.Thread(
            target=self._worker,
            name="arena-auto-update",
            daemon=True,
        )
        worker.start()

    def _worker(self) -> None:
        update = check_for_available_update(
            current_version=self._current_version,
            manifest_url=self._manifest_url,
            default_update_url=self._default_update_url,
            timeout_seconds=self._timeout_seconds,
        )
        self._result_queue.put(update)

    def _run_check_now(self) -> AvailableUpdate | None:
        self._check_started = True
        self._available_update = check_for_available_update(
            current_version=self._current_version,
            manifest_url=self._manifest_url,
            default_update_url=self._default_update_url,
            timeout_seconds=self._timeout_seconds,
        )
        self._check_completed = True
        return self._available_update

    def attach_window(self, window) -> None:
        if window is None:
            return

        self.start_background_check()
        if bool(getattr(window, WINDOW_BOUND_ATTR, False)):
            return

        setattr(window, WINDOW_BOUND_ATTR, True)
        window.bind(
            "<Destroy>",
            lambda event, ref=window: self._cancel_window_poll(ref, event),
            add="+",
        )
        self._schedule_window_poll(window, delay_ms=0)

    def _cancel_window_poll(self, window, event=None) -> None:
        if event is not None and getattr(event, "widget", None) is not window:
            return

        callback_id = getattr(window, WINDOW_AFTER_ATTR, None)
        if callback_id is None:
            return

        try:
            window.after_cancel(callback_id)
        except TclError:
            pass
        setattr(window, WINDOW_AFTER_ATTR, None)

    def _schedule_window_poll(self, window, *, delay_ms: int) -> None:
        self._cancel_window_poll(window)
        try:
            callback_id = window.after(
                delay_ms,
                lambda ref=window: self._poll_window(ref),
            )
        except TclError:
            return

        setattr(window, WINDOW_AFTER_ATTR, callback_id)

    def _drain_results(self) -> None:
        while True:
            try:
                update = self._result_queue.get_nowait()
            except queue.Empty:
                break

            self._available_update = update
            self._check_completed = True

    def _now_epoch(self) -> int:
        try:
            return max(0, int(self._now_provider()))
        except (TypeError, ValueError):
            return max(0, int(time.time()))

    def _clear_snooze_state(self) -> None:
        clear_auto_update_state(self._state_path)
        self._snoozed_state = AutoUpdateState()

    def _persist_state(self) -> None:
        save_auto_update_state(self._snoozed_state, self._state_path)

    def _consume_launch_reprompt(self) -> None:
        launches_until_prompt = max(0, int(self._snoozed_state.launches_until_prompt))
        if launches_until_prompt <= 0 or not self._snoozed_state.snoozed_version:
            return

        self._snoozed_state = AutoUpdateState(
            snoozed_version=self._snoozed_state.snoozed_version,
            remind_after_epoch=self._snoozed_state.remind_after_epoch,
            launches_until_prompt=max(0, launches_until_prompt - 1),
            dismissed_version=self._snoozed_state.dismissed_version,
        )
        self._persist_state()

    def _is_update_dismissed(self, update: AvailableUpdate) -> bool:
        dismissed_version = get_dismissed_version(self._state_path)
        if (
            dismissed_version
            != str(self._snoozed_state.dismissed_version or "").strip()
        ):
            self._snoozed_state = AutoUpdateState(
                snoozed_version=self._snoozed_state.snoozed_version,
                remind_after_epoch=self._snoozed_state.remind_after_epoch,
                launches_until_prompt=self._snoozed_state.launches_until_prompt,
                dismissed_version=dismissed_version,
            )

        if not dismissed_version:
            return False

        comparison = compare_semver(update.version, dismissed_version)
        if comparison is None:
            set_dismissed_version("", self._state_path)
            self._snoozed_state = AutoUpdateState(
                snoozed_version=self._snoozed_state.snoozed_version,
                remind_after_epoch=self._snoozed_state.remind_after_epoch,
                launches_until_prompt=self._snoozed_state.launches_until_prompt,
                dismissed_version="",
            )
            return False

        return comparison <= 0

    def _is_update_snoozed(self, update: AvailableUpdate) -> bool:
        if self._is_update_dismissed(update):
            return True

        if self._snoozed_state.launches_until_prompt > 0 and is_same_version(
            update.version, self._snoozed_state.snoozed_version
        ):
            return True

        remind_after_epoch = self._snoozed_state.remind_after_epoch
        if remind_after_epoch <= 0:
            return False

        if remind_after_epoch <= self._now_epoch():
            self._clear_snooze_state()
            return False

        return is_same_version(
            update.version,
            self._snoozed_state.snoozed_version,
        )

    def _poll_window(self, window) -> None:
        try:
            if not window.winfo_exists():
                return
        except TclError:
            return

        setattr(window, WINDOW_AFTER_ATTR, None)
        self._drain_results()

        if self._available_update is not None and not self._offer_resolved:
            if self._is_update_snoozed(self._available_update):
                return
            self._present_notice(window, self._available_update)
            return

        if not self._check_completed and not self._offer_resolved:
            self._schedule_window_poll(
                window,
                delay_ms=self._poll_interval_ms,
            )

    def _present_notice(self, window, update: AvailableUpdate) -> None:
        current_notice_window = self._notice_window
        if current_notice_window is not None:
            try:
                current_notice = getattr(
                    current_notice_window,
                    WINDOW_NOTICE_ATTR,
                    None,
                )
                if (
                    current_notice_window.winfo_exists()
                    and current_notice is not None
                    and current_notice.winfo_exists()
                ):
                    return
            except TclError:
                pass

            self._notice_window = None

        if bool(getattr(window, WINDOW_NOTICE_ATTR, None)):
            return

        notice_width = self._notice_width_for_window(window)
        notice = AutoUpdateNotice(
            window,
            update=update,
            on_update=lambda: self._handle_update_choice(window, update),
            on_later=lambda: self._handle_later_choice(window, update),
            on_never=lambda: self._handle_never_choice(window, update),
            width=notice_width,
        )
        setattr(window, WINDOW_NOTICE_ATTR, notice)
        self._notice_window = window
        notice.place(
            relx=0.5,
            rely=1.0,
            anchor="s",
            x=0,
            y=-18,
        )
        notice.lift()
        _schedule_window_sound(notice, tone="alert")

    def _notice_width_for_window(self, window) -> int:
        try:
            window.update_idletasks()
        except (AttributeError, TclError):
            pass

        window_width = 0
        for width_getter_name in ("winfo_width", "winfo_reqwidth"):
            width_getter = getattr(window, width_getter_name, None)
            if width_getter is None:
                continue

            try:
                window_width = max(window_width, int(width_getter()))
            except (TypeError, ValueError, TclError):
                continue

        if window_width <= 0:
            window_width = AUTO_UPDATE_NOTICE_MAX_WIDTH

        padded_width = window_width - (AUTO_UPDATE_NOTICE_SIDE_MARGIN * 2)
        return max(
            AUTO_UPDATE_NOTICE_MIN_WIDTH,
            min(padded_width, AUTO_UPDATE_NOTICE_MAX_WIDTH),
        )

    def _dismiss_notice(self, window) -> None:
        notice = getattr(window, WINDOW_NOTICE_ATTR, None)
        if notice is None:
            return

        setattr(window, WINDOW_NOTICE_ATTR, None)
        if self._notice_window is window:
            self._notice_window = None
        notice.dismiss()

    def _effective_remind_later_seconds(
        self,
        update: AvailableUpdate,
    ) -> int:
        if update.remind_later_seconds is not None:
            return max(0, int(update.remind_later_seconds))
        return self._remind_later_seconds

    def startup_available_update(self) -> AvailableUpdate | None:
        if not self._check_completed:
            self._drain_results()

        if not self._check_completed:
            self._run_check_now()

        update = self._available_update
        if update is None:
            return None
        if self._offer_resolved:
            return None
        if self._is_update_snoozed(update):
            return None
        return update

    def defer_update(self, update: AvailableUpdate) -> None:
        self._offer_resolved = True
        self._snoozed_state = AutoUpdateState(
            snoozed_version=update.version,
            remind_after_epoch=0,
            launches_until_prompt=self._reprompt_after_launches,
            dismissed_version="",
        )
        self._persist_state()

    def dismiss_update_offer(self, update: AvailableUpdate) -> None:
        self._offer_resolved = True
        dismissed_version = set_dismissed_version(update.version, self._state_path)
        self._snoozed_state = AutoUpdateState(dismissed_version=dismissed_version)

    def launch_update(self, update: AvailableUpdate) -> None:
        self._offer_resolved = True
        self._clear_snooze_state()
        worker = threading.Thread(
            target=open_update_page,
            args=(update.update_url,),
            kwargs={"installer_sha256": update.installer_sha256},
            name="arena-open-update-page",
            daemon=True,
        )
        worker.start()

    def _handle_later_choice(
        self,
        window,
        update: AvailableUpdate,
    ) -> None:
        self.defer_update(update)
        self._dismiss_notice(window)

    def _handle_never_choice(
        self,
        window,
        update: AvailableUpdate,
    ) -> None:
        self.dismiss_update_offer(update)
        self._dismiss_notice(window)

    def _handle_update_choice(
        self,
        window,
        update: AvailableUpdate,
    ) -> None:
        self.launch_update(update)
        self._dismiss_notice(window)


_AUTO_UPDATE_SERVICE_HOLDER: dict[str, AutoUpdateService | None] = {
    "service": None,
}


def get_auto_update_service() -> AutoUpdateService:
    service = _AUTO_UPDATE_SERVICE_HOLDER["service"]
    if service is None:
        service = AutoUpdateService()
        _AUTO_UPDATE_SERVICE_HOLDER["service"] = service
    return service


def run_startup_update_gate() -> None:
    service = get_auto_update_service()
    update = service.startup_available_update()
    if update is None:
        return

    prompt = AutoUpdatePromptApp(service, update)
    prompt.mainloop()


def bind_auto_update_window(window) -> None:
    get_auto_update_service().attach_window(window)
