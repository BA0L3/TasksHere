import argparse
import ctypes
import logging
import os
import sys

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication, QMessageBox

from Background import (
    BackgroundRuntime,
    _auto_start_command,
    _auto_start_of,
    _auto_start_on,
)
from Database import DataBase
from Settings import Settings
from config import METADATA, TASKS_FILE, WEIGHTS, setup_logging
from gui import MainWindow
from Updater import start_update_if_available


logger = logging.getLogger(__name__)


def _should_start_hidden(settings: Settings, tray_available: bool) -> bool:
    return bool(getattr(settings, "Just Show Only TrayIon")) and tray_available


class _WindowSignals(QObject):
    show_requested = Signal()
    hide_requested = Signal()
    task_requested = Signal(str)
    tasks_changed = Signal()


def main(update_status: str | None = None) -> int:
    setup_logging()
    logger.info("%s %s GUI starting", METADATA["name"], METADATA["version"])
    startup_warning: str | None = None
    if update_status is None:
        update_started, startup_warning = start_update_if_available(
            0,
            "main_gui.exe",
        )
        if update_started:
            return 0
    elif update_status == "updated":
        logger.info("TasksHere was updated successfully.")
    else:
        logger.error("Update failed: %s", update_status)
        startup_warning = f"Không thể áp dụng bản cập nhật:\n{update_status}"

    application = QApplication([sys.argv[0]])
    application.setApplicationName(METADATA["name"])
    application.setStyle("Fusion")

    myappid = f'{METADATA["developer"]}.{METADATA["version"]}.gui.{METADATA["version"]}' 
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    runtime: BackgroundRuntime | None = None
    try:
        settings = Settings()
        if settings.recovery_message:
            logger.warning("%s", settings.recovery_message)
        if os.name == "nt":
            try:
                if settings.auto_start:
                    _auto_start_on(_auto_start_command("main_gui.py"))
                else:
                    _auto_start_of()
            except OSError as exc:
                logger.exception("Could not synchronize Windows auto-start")
                startup_warning = (
                    "Không thể đồng bộ tùy chọn khởi động cùng Windows:\n"
                    f"{exc}"
                )
        database = DataBase(TASKS_FILE)
        window = MainWindow(database, WEIGHTS, settings)
        signals = _WindowSignals()

        def show_window() -> None:
            window.showNormal()
            window.raise_()
            window.activateWindow()

        signals.show_requested.connect(show_window)
        signals.hide_requested.connect(window.hide)
        signals.task_requested.connect(window.show_task)
        signals.tasks_changed.connect(window._refresh_tasks)
        if os.name == "nt":
            runtime = BackgroundRuntime(
                database,
                settings,
                show_callback=signals.show_requested.emit,
                hide_callback=signals.hide_requested.emit,
                open_task_callback=signals.task_requested.emit,
                tasks_changed_callback=signals.tasks_changed.emit,
            )
            runtime.start()
            monitor = QTimer(application)
            monitor.setInterval(250)
            monitor.timeout.connect(
                lambda: application.quit()
                if runtime is not None and runtime.stop_event.is_set()
                else None
            )
            monitor.start()
        tray_available = os.name != "nt" or (
            runtime is not None and runtime.tray is not None
        )
        if not _should_start_hidden(settings, tray_available):
            window.show()
        if settings.recovery_message:
            QMessageBox.warning(
                window,
                "Cài đặt được khôi phục",
                settings.recovery_message,
            )
        if startup_warning:
            QMessageBox.warning(window, "Cảnh báo", startup_warning)
        return application.exec()
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        logger.exception("GUI terminated due to an unexpected error")
        QMessageBox.critical(
            None,
            "Không thể khởi chạy TasksHere",
            f"{type(exc).__name__}: {exc}\n\n"
            "Kiểm tra logs/taskshere.log để biết thêm chi tiết.",
        )
        return 1
    finally:
        if runtime is not None:
            runtime.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--update-status")
    args = parser.parse_args()
    raise SystemExit(main(args.update_status))
