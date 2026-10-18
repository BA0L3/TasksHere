import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False) or "__compiled__" in globals():
        return Path(sys.argv[0]).resolve().parent
    return Path(__file__).resolve().parent


BASE_DIR = get_base_dir()


def resolve_path(path: str | Path) -> Path:
    resolved_path = Path(path)
    if resolved_path.is_absolute():
        return resolved_path
    return BASE_DIR / resolved_path


TASKS_FILE = resolve_path("Datas//Tasks.json")
LOG_DIR = resolve_path("Datas//logs")
LOG_FILE = LOG_DIR / "taskshere.log"
SETTINGS_FILE = resolve_path("Datas//settings.json")
ICON_FILE = resolve_path("Datas//assets//TaskHere.ico")
IMG_FILE = resolve_path("Datas//assets//TaskHere.png")

METADATA = {
    "name": "TasksHere",
    "version": "1.2.1",
    "credit": "BA0L3 (BA0L3-dev or Lê Nguyễn Gia Bảo)",
    "developer": "BA0L3",
    "os": ["windows10", "windows11"],
    "UI": ["CLI", "GUI"]
}

WEIGHTS = [
    "Importance",
    "Urgency",
    "Value / ROI",
    "Blocking",
    "Alignment",
    "Effort",
    "Delegation",
    "Context",
    "Fatigue",
    "Regret Score",
    "Deadline"
]


def setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    if not any(handler.get_name() == "taskshere-file" for handler in root_logger.handlers):
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=1_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        file_handler.set_name("taskshere-file")
        root_logger.addHandler(file_handler)
    if not any(handler.get_name() == "taskshere-console" for handler in root_logger.handlers):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        console_handler.setFormatter(formatter)
        console_handler.set_name("taskshere-console")
        root_logger.addHandler(console_handler)