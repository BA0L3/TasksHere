import argparse
import ctypes
import logging
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import zipfile
from ctypes import wintypes


logger = logging.getLogger(__name__)

_PROCESS_SYNCHRONIZE = 0x00100000
_WAIT_OBJECT_0 = 0
_WAIT_FAILED = 0xFFFFFFFF
_WAIT_INFINITE = 0xFFFFFFFF
_ERROR_INVALID_PARAMETER = 87
_MOVEFILE_DELAY_UNTIL_REBOOT = 0x00000004


def _positive_pid(value: str) -> int:
    pid = int(value)
    if pid <= 0:
        raise argparse.ArgumentTypeError("PID must be a positive integer")
    return pid


def _wait_for_process(pid: int) -> None:
    if os.name != "nt":
        raise OSError("The update helper is supported only on Windows")

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    open_process = kernel32.OpenProcess
    open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    open_process.restype = wintypes.HANDLE
    wait_for_single_object = kernel32.WaitForSingleObject
    wait_for_single_object.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    wait_for_single_object.restype = wintypes.DWORD
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL

    process_handle = open_process(_PROCESS_SYNCHRONIZE, False, pid)
    if not process_handle:
        error_code = ctypes.get_last_error()
        if error_code == _ERROR_INVALID_PARAMETER:
            return
        raise ctypes.WinError(error_code)

    try:
        result = wait_for_single_object(process_handle, _WAIT_INFINITE)
        if result == _WAIT_FAILED:
            raise ctypes.WinError(ctypes.get_last_error())
        if result != _WAIT_OBJECT_0:
            raise OSError(f"Unexpected process wait result: {result}")
    finally:
        close_handle(process_handle)


def _safe_members(
    archive: zipfile.ZipFile,
    app_dir: Path,
) -> list[tuple[zipfile.ZipInfo, Path]]:
    destination = app_dir.resolve()
    members: list[tuple[zipfile.ZipInfo, Path]] = []
    seen_targets: set[str] = set()
    for member in archive.infolist():
        normalized_name = member.filename.replace("\\", "/")
        relative_path = PurePosixPath(normalized_name)
        if (
            not normalized_name
            or "\x00" in normalized_name
            or relative_path.is_absolute()
            or any(
                part in ("", ".", "..") or ":" in part
                for part in relative_path.parts
            )
        ):
            raise ValueError(f"Unsafe path in update ZIP: {member.filename!r}")

        target = destination.joinpath(*relative_path.parts).resolve()
        if target != destination and destination not in target.parents:
            raise ValueError(f"Unsafe path in update ZIP: {member.filename!r}")
        target_key = os.path.normcase(str(target)).casefold()
        if target_key in seen_targets:
            raise ValueError(f"Duplicate path in update ZIP: {member.filename!r}")
        seen_targets.add(target_key)
        members.append((member, target))
    return members


def _preserves_user_data(target: Path, app_dir: Path) -> bool:
    try:
        relative_path = target.relative_to(app_dir)
    except ValueError:
        return False

    parts = tuple(part.casefold() for part in relative_path.parts)
    return (
        len(parts) >= 2
        and parts[0] == "datas"
        and (
            parts[1] in ("tasks.json", "settings.json")
            or parts[1] == "logs"
        )
    )


def _extract_update(
    zip_path: Path,
    app_dir: Path,
    expected_launcher: Path,
) -> None:
    destination = app_dir.resolve()
    expected_path = expected_launcher.resolve()
    if expected_path.parent != destination:
        raise ValueError("The application launcher must be in the application folder")

    with zipfile.ZipFile(zip_path, "r") as archive:
        members = _safe_members(archive, destination)
        if not any(target == expected_path for _, target in members):
            raise ValueError(
                f"Update ZIP does not contain {expected_path.name} at its root"
            )

        damaged_member = archive.testzip()
        if damaged_member is not None:
            raise zipfile.BadZipFile(f"Corrupted ZIP member: {damaged_member}")

        for member, target in members:
            if _preserves_user_data(target, destination):
                continue
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{target.name}.",
                suffix=".update",
                dir=target.parent,
            )
            os.close(descriptor)
            temporary_target = Path(temporary_name)
            try:
                with archive.open(member, "r") as source:
                    with temporary_target.open("wb") as output:
                        shutil.copyfileobj(source, output)
                os.replace(temporary_target, target)
            except Exception:
                temporary_target.unlink(missing_ok=True)
                raise


def _launch_application(launcher: Path, app_dir: Path, status: str) -> None:
    subprocess.Popen(
        [str(launcher), "--update-status", status],
        cwd=str(app_dir),
    )


def _schedule_worker_cleanup() -> None:
    if os.name != "nt":
        return
    worker_path = Path(sys.argv[0]).resolve()
    if worker_path.suffix.casefold() != ".exe":
        return

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    move_file_ex = kernel32.MoveFileExW
    move_file_ex.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
    ]
    move_file_ex.restype = wintypes.BOOL
    if not move_file_ex(
        str(worker_path),
        None,
        _MOVEFILE_DELAY_UNTIL_REBOOT,
    ):
        logger.warning(
            "Could not schedule temporary update-helper cleanup: %s",
            ctypes.get_last_error(),
        )


def _configure_logging(app_dir: Path) -> None:
    log_file = app_dir / "Datas" / "logs" / "taskshere.log"
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            encoding="utf-8",
        )
    except OSError:
        logging.basicConfig(level=logging.WARNING)
        logger.exception("Could not configure update-helper file logging")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply a TasksHere ZIP update.")
    parser.add_argument("--pid", type=_positive_pid, required=True)
    parser.add_argument("--zip", dest="zip_path", required=True)
    parser.add_argument("--launcher", required=True)
    parser.add_argument("--app-dir", required=True)
    args = parser.parse_args(argv)

    app_dir = Path(args.app_dir).resolve()
    archive_path = Path(args.zip_path).resolve()
    launcher = Path(args.launcher).resolve()
    _configure_logging(app_dir)

    status = "updated"
    result = 0
    try:
        _wait_for_process(args.pid)
        if not app_dir.is_dir():
            raise FileNotFoundError(f"Application directory not found: {app_dir}")
        if not archive_path.is_file():
            raise FileNotFoundError(f"Update ZIP not found: {archive_path}")
        if not launcher.is_file():
            raise FileNotFoundError(f"Application launcher not found: {launcher}")
        _extract_update(archive_path, app_dir, launcher)
        try:
            archive_path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not remove downloaded update package %s", archive_path)
        logger.info("Update was applied successfully.")
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
        logger.exception("Could not apply update.")
        status = f"failed: {exc}"
        result = 1

    try:
        _launch_application(launcher, app_dir, status)
    except OSError:
        logger.exception("Could not restart the application after the update.")
        _schedule_worker_cleanup()
        return 1
    _schedule_worker_cleanup()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
