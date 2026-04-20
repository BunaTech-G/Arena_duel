from __future__ import annotations

import json
import queue
import re
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from tkinter import TclError

import customtkinter as ctk

from runtime_utils import runtime_user_file_path
from ui.theme import PALETTE, TYPOGRAPHY, create_button, style_frame


GAME_VERSION = "1.0.0"
DEFAULT_UPDATE_MANIFEST_URL = (
    "https://raw.githubusercontent.com/BunaTech-G/Arena_duel/main/version.json"
)
DEFAULT_UPDATE_PAGE_URL = "https://github.com/BunaTech-G/Arena_duel/releases"
AUTO_UPDATE_STATE_FILENAME = "auto_update_state.json"
AUTO_UPDATE_CHECK_TIMEOUT_SECONDS = 2.5
AUTO_UPDATE_POLL_MS = 80
AUTO_UPDATE_REMIND_LATER_SECONDS = 24 * 60 * 60
AUTO_UPDATE_NOTICE_TEXT = "Une mise à jour est disponible"
WINDOW_BOUND_ATTR = "_arena_auto_update_bound"
WINDOW_AFTER_ATTR = "_arena_auto_update_after_id"
WINDOW_NOTICE_ATTR = "_arena_auto_update_notice"


@dataclass(frozen=True)
class UpdateManifest:
    version: str
    update_url: str
    remind_later_seconds: int | None = None


@dataclass(frozen=True)
class AvailableUpdate:
    version: str
    update_url: str
    remind_later_seconds: int | None = None


@dataclass(frozen=True)
class AutoUpdateState:
    snoozed_version: str = ""
    remind_after_epoch: int = 0


def _parse_version_parts(version_text: str) -> tuple[int, ...]:
    normalized_text = str(version_text or "").strip()
    if not normalized_text:
        return (0,)

    parts = [int(token) for token in re.split(r"[^0-9]+", normalized_text) if token]
    return tuple(parts or [0])


def _normalized_version_parts(version_text: str) -> tuple[int, ...]:
    parts = list(_parse_version_parts(version_text))
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def is_newer_version(remote_version: str, local_version: str) -> bool:
    remote_parts = list(_parse_version_parts(remote_version))
    local_parts = list(_parse_version_parts(local_version))
    max_length = max(len(remote_parts), len(local_parts))

    remote_parts.extend([0] * (max_length - len(remote_parts)))
    local_parts.extend([0] * (max_length - len(local_parts)))
    return tuple(remote_parts) > tuple(local_parts)


def is_same_version(version_a: str, version_b: str) -> bool:
    return _normalized_version_parts(version_a) == _normalized_version_parts(version_b)


def _normalize_optional_url(raw_value: object) -> str:
    return str(raw_value or "").strip()


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
    remind_after_raw = raw_state.get("remind_after_epoch") or 0
    try:
        remind_after_epoch = max(0, int(remind_after_raw))
    except (TypeError, ValueError):
        remind_after_epoch = 0

    if not snoozed_version or remind_after_epoch <= 0:
        return AutoUpdateState()

    return AutoUpdateState(
        snoozed_version=snoozed_version,
        remind_after_epoch=remind_after_epoch,
    )


def save_auto_update_state(
    state: AutoUpdateState,
    path: str | None = None,
) -> str:
    state_file = Path(path or auto_update_state_path())
    payload = {
        "snoozed_version": str(state.snoozed_version or "").strip(),
        "remind_after_epoch": max(0, int(state.remind_after_epoch)),
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
    manifest_url: str = DEFAULT_UPDATE_MANIFEST_URL,
    *,
    default_update_url: str = DEFAULT_UPDATE_PAGE_URL,
    timeout_seconds: float = AUTO_UPDATE_CHECK_TIMEOUT_SECONDS,
) -> UpdateManifest | None:
    normalized_manifest_url = str(manifest_url or "").strip()
    if not normalized_manifest_url:
        return None

    request = urllib.request.Request(
        normalized_manifest_url,
        headers={"User-Agent": f"ArenaDuel/{GAME_VERSION}"},
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
        default_update_url,
    )
    if not update_url:
        update_url = default_update_url

    remind_later_seconds = _parse_manifest_remind_later_seconds(manifest_data)

    return UpdateManifest(
        version=version_text,
        update_url=update_url,
        remind_later_seconds=remind_later_seconds,
    )


def check_for_available_update(
    *,
    current_version: str = GAME_VERSION,
    manifest_url: str = DEFAULT_UPDATE_MANIFEST_URL,
    default_update_url: str = DEFAULT_UPDATE_PAGE_URL,
    timeout_seconds: float = AUTO_UPDATE_CHECK_TIMEOUT_SECONDS,
) -> AvailableUpdate | None:
    manifest = fetch_remote_update_manifest(
        manifest_url,
        default_update_url=default_update_url,
        timeout_seconds=timeout_seconds,
    )
    if manifest is None:
        return None

    if not is_newer_version(manifest.version, current_version):
        return None

    return AvailableUpdate(
        version=manifest.version,
        update_url=manifest.update_url,
        remind_later_seconds=manifest.remind_later_seconds,
    )


def open_update_page(update_url: str) -> bool:
    normalized_url = str(update_url or "").strip()
    if not normalized_url:
        return False

    try:
        return bool(webbrowser.open_new_tab(normalized_url))
    except (OSError, webbrowser.Error):
        return False


class AutoUpdateNotice(ctk.CTkFrame):
    def __init__(
        self,
        master=None,
        *,
        on_update,
        on_later,
    ):
        super().__init__(master, corner_radius=22)
        style_frame(
            self,
            tone="panel_deep",
            border_color=PALETTE["gold_dim"],
            border_width=1,
        )

        self._on_update = on_update
        self._on_later = on_later
        self.update_button = None
        self.later_button = None

        self.grid_columnconfigure(0, weight=1)
        self._build_ui()

    def _build_ui(self) -> None:
        ctk.CTkLabel(
            self,
            text=AUTO_UPDATE_NOTICE_TEXT,
            font=TYPOGRAPHY["body_bold"],
            text_color=PALETTE["text"],
            justify="left",
        ).grid(row=0, column=0, padx=18, pady=(16, 12), sticky="w")

        button_row = ctk.CTkFrame(self, fg_color="transparent")
        button_row.grid(
            row=1,
            column=0,
            padx=18,
            pady=(0, 16),
            sticky="ew",
        )
        button_row.grid_columnconfigure(0, weight=1)
        button_row.grid_columnconfigure(1, weight=1)

        self.update_button = create_button(
            button_row,
            "Mettre à jour",
            self._handle_update,
            variant="primary",
            height=40,
        )
        self.update_button.grid(
            row=0,
            column=0,
            padx=(0, 8),
            sticky="ew",
        )

        self.later_button = create_button(
            button_row,
            "Plus tard",
            self._handle_later,
            variant="ghost",
            height=40,
        )
        self.later_button.grid(
            row=0,
            column=1,
            padx=(8, 0),
            sticky="ew",
        )

    def _handle_update(self) -> None:
        self._on_update()
        self.dismiss()

    def _handle_later(self) -> None:
        self._on_later()
        self.dismiss()

    def dismiss(self) -> None:
        try:
            if self.winfo_exists():
                self.destroy()
        except TclError:
            pass


class AutoUpdateService:
    def __init__(
        self,
        *,
        current_version: str = GAME_VERSION,
        manifest_url: str = DEFAULT_UPDATE_MANIFEST_URL,
        default_update_url: str = DEFAULT_UPDATE_PAGE_URL,
        timeout_seconds: float = AUTO_UPDATE_CHECK_TIMEOUT_SECONDS,
        poll_interval_ms: int = AUTO_UPDATE_POLL_MS,
        remind_later_seconds: int = AUTO_UPDATE_REMIND_LATER_SECONDS,
        state_path: str | None = None,
        now_provider=None,
    ):
        self._current_version = current_version
        self._manifest_url = manifest_url
        self._default_update_url = default_update_url
        self._timeout_seconds = timeout_seconds
        self._poll_interval_ms = poll_interval_ms
        self._remind_later_seconds = max(0, int(remind_later_seconds))
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
        self._snoozed_state = load_auto_update_state(self._state_path)

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

    def _is_update_snoozed(self, update: AvailableUpdate) -> bool:
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

        notice = AutoUpdateNotice(
            window,
            on_update=lambda: self._handle_update_choice(window, update),
            on_later=lambda: self._handle_later_choice(window, update),
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

    def _handle_later_choice(
        self,
        window,
        update: AvailableUpdate,
    ) -> None:
        self._offer_resolved = True
        remind_later_seconds = self._effective_remind_later_seconds(update)

        if remind_later_seconds > 0:
            self._snoozed_state = AutoUpdateState(
                snoozed_version=update.version,
                remind_after_epoch=(self._now_epoch() + remind_later_seconds),
            )
            save_auto_update_state(self._snoozed_state, self._state_path)
        else:
            self._clear_snooze_state()

        self._dismiss_notice(window)

    def _handle_update_choice(
        self,
        window,
        update: AvailableUpdate,
    ) -> None:
        self._offer_resolved = True
        self._clear_snooze_state()
        self._dismiss_notice(window)
        worker = threading.Thread(
            target=open_update_page,
            args=(update.update_url,),
            name="arena-open-update-page",
            daemon=True,
        )
        worker.start()


_AUTO_UPDATE_SERVICE_HOLDER: dict[str, AutoUpdateService | None] = {
    "service": None,
}


def get_auto_update_service() -> AutoUpdateService:
    service = _AUTO_UPDATE_SERVICE_HOLDER["service"]
    if service is None:
        service = AutoUpdateService()
        _AUTO_UPDATE_SERVICE_HOLDER["service"] = service
    return service


def bind_auto_update_window(window) -> None:
    get_auto_update_service().attach_window(window)
