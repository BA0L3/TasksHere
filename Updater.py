import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

import requests

from config import BASE_DIR, METADATA


logger = logging.getLogger(__name__)

LATEST_VERSION = 0
ASSET_NOT_FOUND = 1
FETCH_FAILED = 2
DOWNLOAD_FAILED = 3

_UPDATE_ERRORS = {
    ASSET_NOT_FOUND: "No ZIP update package was found for this interface.",
    FETCH_FAILED: "The latest release could not be fetched.",
    DOWNLOAD_FAILED: "The update package could not be downloaded.",
}


def _version_tuple(version: str) -> tuple[int, ...] | None:
    normalized = version.strip().lstrip("vV")
    parts = normalized.split(".")
    if not parts or any(not part.isdecimal() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def is_compiled() -> bool:
    return bool(getattr(sys, "frozen", False) or "__compiled__" in globals())


def check_for_updates(ui: int) -> int | str:
    if ui not in (0, 1):
        raise ValueError("ui must be 0 for GUI or 1 for CLI")

    interface = ("GUI", "CLI")[ui]
    release_url = (
        f"https://api.github.com/repos/{METADATA['developer']}/"
        f"{METADATA['name']}/releases/latest"
    )
    headers = {"User-Agent": f"{METADATA['name']}_{METADATA['version']}"}

    try:
        response = requests.get(release_url, headers=headers, timeout=15)
        try:
            if response.status_code != 200:
                logger.warning(
                    "Could not fetch the latest release: HTTP %s",
                    response.status_code,
                )
                return FETCH_FAILED
            release_data = response.json()
        finally:
            response.close()

        latest_version = _version_tuple(str(release_data["tag_name"]))
        current_version = _version_tuple(str(METADATA["version"]))
        if latest_version is None or current_version is None:
            logger.error("Release or application version is not numeric semver.")
            return FETCH_FAILED
        width = max(len(latest_version), len(current_version))
        latest_version += (0,) * (width - len(latest_version))
        current_version += (0,) * (width - len(current_version))
        if latest_version <= current_version:
            logger.info("No newer TasksHere release is available.")
            return LATEST_VERSION

        prefix = f"{METADATA['name']}-{interface}-".casefold()
        assets = release_data.get("assets", [])
        matching_assets = [
            asset
            for asset in assets
            if str(asset.get("name", "")).casefold().startswith(prefix)
            and Path(str(asset.get("name", ""))).suffix.casefold() == ".zip"
        ]
        if len(matching_assets) != 1:
            logger.error(
                "Expected one ZIP package for %s, found %s.",
                interface,
                len(matching_assets),
            )
            return ASSET_NOT_FOUND

        asset = matching_assets[0]
        download_url = str(asset["browser_download_url"])
        if not download_url.startswith("https://"):
            logger.error("Refusing non-HTTPS update URL: %s", download_url)
            return DOWNLOAD_FAILED
        return download_file(download_url, str(asset["name"]), headers)
    except (
        KeyError,
        OSError,
        requests.RequestException,
        TypeError,
        ValueError,
    ):
        logger.exception("Could not check or download the latest release.")
        return DOWNLOAD_FAILED


def download_file(url: str, file_name: str, headers: dict[str, str]) -> str:
    safe_name = Path(file_name).name
    if (
        not safe_name
        or safe_name != file_name
        or Path(safe_name).suffix.casefold() != ".zip"
    ):
        raise ValueError("The release asset must be a ZIP with a plain filename")

    destination = BASE_DIR / safe_name
    partial_path = destination.with_name(destination.name + ".part")
    response = None
    try:
        response = requests.get(
            url,
            headers=headers,
            stream=True,
            timeout=(10, 60),
        )
        if response.status_code != 200:
            raise requests.HTTPError(
                f"Update download failed with HTTP {response.status_code}"
            )
        with partial_path.open("wb") as archive:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if chunk:
                    archive.write(chunk)
        if partial_path.stat().st_size == 0:
            raise ValueError("The downloaded update package is empty")
        os.replace(partial_path, destination)
    except (OSError, requests.RequestException, ValueError):
        partial_path.unlink(missing_ok=True)
        raise
    finally:
        if response is not None:
            response.close()

    logger.info("Downloaded update package to %s", destination)
    return str(destination)


def start_update_if_available(ui: int, launcher_name: str) -> tuple[bool, str | None]:
    if not is_compiled():
        logger.debug("Automatic updates are disabled for source runs.")
        return False, None

    result = check_for_updates(ui)
    if result == LATEST_VERSION:
        return False, None
    if not isinstance(result, str):
        message = _UPDATE_ERRORS.get(
            result,
            "An unexpected error occurred while checking for updates.",
        )
        logger.warning("%s", message)
        return False, message

    try:
        start_update(result, launcher_name)
    except OSError as exc:
        logger.exception("Could not start the update helper.")
        return False, f"Could not start the update helper: {exc}"
    return True, None


def start_update(archive_path: str, launcher_name: str) -> None:
    app_dir = BASE_DIR.resolve()
    archive = Path(archive_path).resolve()
    helper = app_dir / "Unziper.exe"
    launcher = app_dir / launcher_name
    if not archive.is_file():
        raise FileNotFoundError(f"Update package not found: {archive}")
    if not helper.is_file():
        raise FileNotFoundError(f"Update helper not found: {helper}")
    if not launcher.is_file():
        raise FileNotFoundError(f"Application launcher not found: {launcher}")

    helper_copy = Path(tempfile.gettempdir()) / (
        f"TasksHere-update-{os.getpid()}-{uuid.uuid4().hex}.exe"
    )
    try:
        shutil.copy2(helper, helper_copy)
        subprocess.Popen(
            [
                str(helper_copy),
                "--pid",
                str(os.getpid()),
                "--zip",
                str(archive),
                "--launcher",
                str(launcher),
                "--app-dir",
                str(app_dir),
            ],
            cwd=str(app_dir),
        )
    except OSError:
        try:
            helper_copy.unlink(missing_ok=True)
        except OSError:
            logger.exception("Could not clean up the temporary update helper.")
        raise
