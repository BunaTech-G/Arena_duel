from __future__ import annotations

import signal
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
                _cancel_pending_after_callbacks(root)

                try:
                    root.destroy()
                except TclError:
                    pass

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
