from __future__ import annotations

import signal
import sys
import threading
from collections.abc import Callable, Iterable
from tkinter import TclError


ShutdownStep = Callable[[], bool | None]


def window_exists(window) -> bool:
    if window is None:
        return False

    try:
        return bool(window.winfo_exists())
    except TclError:
        return False


def close_window_gracefully(
    window,
    *,
    shutdown_kwargs: dict | None = None,
    user_initiated: bool = False,
    request_close_kwargs: dict | None = None,
) -> bool:
    if not window_exists(window):
        return True

    request_close = getattr(window, "request_close", None)
    if user_initiated and callable(request_close):
        try:
            if request_close_kwargs:
                return request_close(**request_close_kwargs) is not False
            return request_close() is not False
        except TypeError:
            try:
                return request_close() is not False
            except (AttributeError, OSError, RuntimeError, TclError, ValueError):
                pass
        except (AttributeError, OSError, RuntimeError, TclError, ValueError):
            pass

    shutdown = getattr(window, "shutdown", None)
    if callable(shutdown):
        try:
            if shutdown_kwargs:
                return shutdown(**shutdown_kwargs) is not False
            return shutdown() is not False
        except TypeError:
            try:
                return shutdown() is not False
            except (AttributeError, OSError, RuntimeError, TclError, ValueError):
                return True
        except (AttributeError, OSError, RuntimeError, TclError, ValueError):
            return True

    try:
        window.destroy()
    except TclError:
        pass
    return True


def _iter_pending_after_callback_ids(root):
    if not window_exists(root):
        return ()

    try:
        callback_ids = root.tk.call("after", "info")
    except TclError:
        return ()

    if not callback_ids:
        return ()
    if isinstance(callback_ids, str):
        return (callback_ids,)
    if isinstance(callback_ids, (tuple, list)):
        return tuple(callback_ids)
    return ()


def _iter_window_tree(root):
    if not window_exists(root):
        return ()

    windows = [root]

    try:
        child_windows = list(root.winfo_children())
    except TclError:
        child_windows = []

    for child in child_windows:
        windows.extend(_iter_window_tree(child))

    return tuple(windows)


def _cancel_owned_after_callbacks(window) -> None:
    callback_ids = getattr(window, "_arena_after_callback_ids", None)
    if not callback_ids:
        return

    for callback_id in tuple(callback_ids):
        try:
            window.after_cancel(callback_id)
        except TclError:
            pass
        callback_ids.discard(callback_id)


def _cancel_customtkinter_after_callbacks(root) -> None:
    callback_name_suffixes = (
        "update",
        "check_dpi_scaling",
        "click_animation",
        "_windows_set_titlebar_icon",
        "_set_scaled_min_max",
        "_revert_withdraw_after_windows_set_titlebar_color",
    )

    for callback_id in _iter_pending_after_callback_ids(root):
        try:
            callback_info = root.tk.call("after", "info", callback_id)
        except TclError:
            continue

        if not callback_info:
            continue

        callback_name = str(callback_info[0])
        if not callback_name.endswith(callback_name_suffixes):
            continue

        try:
            root.after_cancel(callback_id)
        except TclError:
            continue


def destroy_root_window_gracefully(window) -> bool:
    if not window_exists(window):
        return True

    _cancel_owned_after_callbacks(window)
    _cancel_customtkinter_after_callbacks(window)

    try:
        window.quit()
    except (AttributeError, TclError):
        pass

    try:
        window.destroy()
    except TclError:
        pass
    return True


def close_embedded_root_gracefully(root) -> bool:
    if not window_exists(root):
        return True

    for window in reversed(_iter_window_tree(root)):
        _cancel_owned_after_callbacks(window)
        _cancel_customtkinter_after_callbacks(window)
        _cancel_pending_after_callbacks(window)

    try:
        root.quit()
    except (AttributeError, TclError):
        pass

    try:
        root.destroy()
    except TclError:
        pass
    return True


def prepare_hidden_root_window(root) -> bool:
    if root is None:
        return False

    if sys.platform.startswith("win"):
        for attr_name, value in (
            ("_deactivate_windows_window_header_manipulation", True),
            ("_window_exists", True),
        ):
            try:
                setattr(root, attr_name, value)
            except AttributeError:
                pass

        for args in (("-toolwindow", True), ("-alpha", 0)):
            try:
                root.attributes(*args)
            except (AttributeError, TclError):
                pass

    try:
        root.withdraw()
    except (AttributeError, TclError):
        return False
    return True


def open_window_gracefully(
    window,
    *,
    parent=None,
    hide_parent: bool = False,
) -> None:
    if hide_parent and window_exists(parent):
        try:
            parent.withdraw()
            parent.update_idletasks()
        except TclError:
            pass

    if not window_exists(window):
        return

    try:
        from ui.theme import present_window

        present_window(window)
        return
    except (AttributeError, ImportError, OSError, RuntimeError, TclError, ValueError):
        pass

    try:
        window.deiconify()
        window.update_idletasks()
        window.lift()
        window.focus_force()
    except TclError:
        pass


def _cancel_pending_after_callbacks(root) -> None:
    if not window_exists(root):
        return

    try:
        callback_ids = root.tk.call("after", "info")
    except TclError:
        return

    if not callback_ids:
        return

    if isinstance(callback_ids, str):
        callback_ids = (callback_ids,)

    for callback_id in callback_ids:
        try:
            root.after_cancel(callback_id)
        except TclError:
            continue


def build_graceful_shutdown(
    root,
    *,
    steps: Iterable[ShutdownStep],
    destroy_root: bool = True,
) -> Callable[[], None]:
    shutdown_in_progress = False
    shutdown_completed = False
    shutdown_steps = tuple(steps)

    def _shutdown() -> None:
        nonlocal shutdown_completed, shutdown_in_progress
        if shutdown_completed or shutdown_in_progress:
            return

        try:
            shutdown_in_progress = True

            for step in shutdown_steps:
                try:
                    if step() is False:
                        return
                except (AttributeError, OSError, RuntimeError, TclError, ValueError):
                    pass

            if destroy_root and window_exists(root):
                destroy_root_window_gracefully(root)

            shutdown_completed = True
        finally:
            if not shutdown_completed:
                shutdown_in_progress = False

    return _shutdown


def install_signal_shutdown(
    root,
    shutdown_callback: Callable[[], None],
) -> Callable[[], None]:
    if threading.current_thread() is not threading.main_thread():
        return lambda: None

    handled_signals = [signal.SIGINT]
    for signal_name in ("SIGTERM", "SIGBREAK"):
        if hasattr(signal, signal_name):
            handled_signals.append(getattr(signal, signal_name))

    previous_handlers: dict[signal.Signals, signal.Handlers] = {}
    restored = False

    def restore_handlers() -> None:
        nonlocal restored
        if restored:
            return

        restored = True
        for handled_signal, previous_handler in previous_handlers.items():
            try:
                signal.signal(handled_signal, previous_handler)
            except (OSError, ValueError):
                pass

    def _handle_signal(_signum, _frame) -> None:
        if not window_exists(root):
            restore_handlers()
            return

        try:
            root.after(0, shutdown_callback)
        except TclError:
            restore_handlers()

    for handled_signal in handled_signals:
        try:
            previous_handlers[handled_signal] = signal.getsignal(handled_signal)
            signal.signal(handled_signal, _handle_signal)
        except (OSError, ValueError):
            continue

    def _restore_on_destroy(event=None) -> None:
        if event is not None and getattr(event, "widget", None) is not root:
            return
        restore_handlers()

    try:
        root.bind("<Destroy>", _restore_on_destroy, add="+")
    except (AttributeError, TclError):
        pass

    return restore_handlers
