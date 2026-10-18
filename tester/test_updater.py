import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import requests
import Updater
import Unziper


class UpdaterTests(unittest.TestCase):
    def test_v_prefixed_matching_version_is_up_to_date(self) -> None:
        response = Mock(
            status_code=200,
            json=Mock(return_value={"tag_name": "v1.1.0", "assets": []}),
        )

        with patch("Updater.requests.get", return_value=response):
            result = Updater.check_for_updates(0)

        self.assertEqual(result, Updater.LATEST_VERSION)
        response.close.assert_called_once()

    def test_does_not_downgrade_to_an_older_release(self) -> None:
        response = Mock(
            status_code=200,
            json=Mock(return_value={"tag_name": "v1.0.9", "assets": []}),
        )

        with patch("Updater.requests.get", return_value=response):
            result = Updater.check_for_updates(1)

        self.assertEqual(result, Updater.LATEST_VERSION)

    def test_downloads_zip_for_requested_interface_only(self) -> None:
        release_response = Mock(
            status_code=200,
            json=Mock(
                return_value={
                    "tag_name": "v1.2.0",
                    "assets": [
                        {
                            "name": "TasksHere-GUI-1.2.0-Portable.rar",
                            "browser_download_url": "https://example.test/gui.rar",
                        },
                        {
                            "name": "TasksHere-GUI-1.2.0-Portable.zip",
                            "browser_download_url": "https://example.test/gui.zip",
                        },
                        {
                            "name": "TasksHere-CLI-1.2.0-Portable.zip",
                            "browser_download_url": "https://example.test/cli.zip",
                        },
                    ],
                }
            ),
        )
        download_response = Mock(
            status_code=200,
            iter_content=Mock(return_value=[b"zip-content"]),
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            with (
                patch("Updater.BASE_DIR", Path(temporary_directory)),
                patch(
                    "Updater.requests.get",
                    side_effect=[release_response, download_response],
                ) as get,
            ):
                result = Updater.check_for_updates(0)

            expected_path = Path(temporary_directory) / (
                "TasksHere-GUI-1.2.0-Portable.zip"
            )
            self.assertEqual(result, str(expected_path))
            self.assertEqual(expected_path.read_bytes(), b"zip-content")
            self.assertEqual(get.call_args_list[1].args[0], "https://example.test/gui.zip")
            download_response.close.assert_called_once()

    def test_failed_download_removes_partial_file(self) -> None:
        response = Mock(
            status_code=503,
            iter_content=Mock(return_value=[]),
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            with (
                patch("Updater.BASE_DIR", Path(temporary_directory)),
                patch("Updater.requests.get", return_value=response),
            ):
                with self.assertRaisesRegex(requests.HTTPError, "HTTP 503"):
                    Updater.download_file(
                        "https://example.test/update.zip",
                        "update.zip",
                        {},
                    )

            self.assertFalse((Path(temporary_directory) / "update.zip.part").exists())
            response.close.assert_called_once()

    def test_starting_an_update_passes_the_parent_pid_and_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            app_dir = Path(temporary_directory)
            archive = app_dir / "update.zip"
            archive.touch()
            helper = app_dir / "Unziper.exe"
            helper.write_text("current helper", encoding="utf-8")
            (app_dir / "main_gui.exe").touch()

            with (
                patch("Updater.BASE_DIR", app_dir),
                patch("Updater.os.getpid", return_value=1234),
                patch("Updater.tempfile.gettempdir", return_value=str(app_dir)),
                patch("Updater.uuid.uuid4") as uuid4,
                patch("Updater.subprocess.Popen") as popen,
            ):
                uuid4.return_value.hex = "unit"
                Updater.start_update(str(archive), "main_gui.exe")

            helper_copy = app_dir / "TasksHere-update-1234-unit.exe"
            popen.assert_called_once_with(
                [
                    str(helper_copy),
                    "--pid",
                    "1234",
                    "--zip",
                    str(archive),
                    "--launcher",
                    str(app_dir / "main_gui.exe"),
                    "--app-dir",
                    str(app_dir),
                ],
                cwd=str(app_dir),
            )
            self.assertEqual(
                helper_copy.read_text(encoding="utf-8"),
                "current helper",
            )

    def test_check_starts_update_and_tells_application_to_exit(self) -> None:
        with (
            patch("Updater.is_compiled", return_value=True),
            patch("Updater.check_for_updates", return_value="C:\\app\\update.zip"),
            patch("Updater.start_update") as start_update,
        ):
            started, warning = Updater.start_update_if_available(0, "main_gui.exe")

        self.assertTrue(started)
        self.assertIsNone(warning)
        start_update.assert_called_once_with(
            "C:\\app\\update.zip",
            "main_gui.exe",
        )


class UpdateExtractionTests(unittest.TestCase):
    def make_update_zip(self, path: Path, members: dict[str, str]) -> None:
        with zipfile.ZipFile(path, "w") as archive:
            for name, value in members.items():
                archive.writestr(name, value)

    def test_extracts_update_and_preserves_user_data_and_refreshes_helper(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            archive_path = root / "update.zip"
            app_dir = root / "app"
            app_dir.mkdir()
            (app_dir / "Datas").mkdir()
            (app_dir / "Datas" / "Tasks.json").write_text("keep tasks", encoding="utf-8")
            (app_dir / "Unziper.exe").write_text("running helper", encoding="utf-8")
            self.make_update_zip(
                archive_path,
                {
                    "main_gui.exe": "new launcher",
                    "Unziper.exe": "new helper",
                    "Datas/Tasks.json": "replace tasks",
                    "Datas/assets/TaskHere.ico": "new icon",
                },
            )

            Unziper._extract_update(
                archive_path,
                app_dir,
                app_dir / "main_gui.exe",
            )

            self.assertEqual(
                (app_dir / "main_gui.exe").read_text(encoding="utf-8"),
                "new launcher",
            )
            self.assertEqual(
                (app_dir / "Datas" / "Tasks.json").read_text(encoding="utf-8"),
                "keep tasks",
            )
            self.assertEqual(
                (app_dir / "Unziper.exe").read_text(encoding="utf-8"),
                "new helper",
            )
            self.assertEqual(
                (app_dir / "Datas" / "assets" / "TaskHere.ico").read_text(
                    encoding="utf-8"
                ),
                "new icon",
            )

    def test_rejects_path_traversal_before_extracting_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            archive_path = root / "update.zip"
            app_dir = root / "app"
            app_dir.mkdir()
            self.make_update_zip(
                archive_path,
                {
                    "main_gui.exe": "new launcher",
                    "../outside.txt": "outside",
                },
            )

            with self.assertRaisesRegex(ValueError, "Unsafe path"):
                Unziper._extract_update(
                    archive_path,
                    app_dir,
                    app_dir / "main_gui.exe",
                )

            self.assertFalse((root / "outside.txt").exists())
            self.assertFalse((app_dir / "main_gui.exe").exists())

    def test_rejects_zip_without_root_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            archive_path = root / "update.zip"
            app_dir = root / "app"
            app_dir.mkdir()
            self.make_update_zip(archive_path, {"folder/main_gui.exe": "nested"})

            with self.assertRaisesRegex(ValueError, "does not contain"):
                Unziper._extract_update(
                    archive_path,
                    app_dir,
                    app_dir / "main_gui.exe",
                )

            self.assertFalse((app_dir / "folder").exists())

    def test_helper_waits_for_parent_then_restarts_with_update_status(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            archive_path = root / "update.zip"
            app_dir = root / "app"
            app_dir.mkdir()
            launcher = app_dir / "main.exe"
            launcher.touch()
            self.make_update_zip(archive_path, {"main.exe": "updated launcher"})

            with (
                patch("Unziper._wait_for_process") as wait_for_process,
                patch("Unziper._launch_application") as launch_application,
                patch("Unziper._configure_logging"),
            ):
                result = Unziper.main(
                    [
                        "--pid",
                        "987",
                        "--zip",
                        str(archive_path),
                        "--launcher",
                        str(launcher),
                        "--app-dir",
                        str(app_dir),
                    ]
                )

            self.assertEqual(result, 0)
            wait_for_process.assert_called_once_with(987)
            launch_application.assert_called_once_with(launcher, app_dir, "updated")
            self.assertEqual(launcher.read_text(encoding="utf-8"), "updated launcher")
            self.assertFalse(archive_path.exists())

    def test_helper_reports_wait_failure_and_restarts_old_application(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            archive_path = root / "update.zip"
            app_dir = root / "app"
            app_dir.mkdir()
            launcher = app_dir / "main.exe"
            launcher.touch()

            with self.assertLogs("Unziper", level="ERROR"):
                with (
                    patch(
                        "Unziper._wait_for_process",
                        side_effect=OSError("process wait failed"),
                    ),
                    patch("Unziper._launch_application") as launch_application,
                    patch("Unziper._configure_logging"),
                ):
                    result = Unziper.main(
                        [
                            "--pid",
                            "987",
                            "--zip",
                            str(archive_path),
                            "--launcher",
                            str(launcher),
                            "--app-dir",
                            str(app_dir),
                        ]
                    )

            self.assertEqual(result, 1)
            launch_application.assert_called_once()
            self.assertIn("failed:", launch_application.call_args.args[2])


if __name__ == "__main__":
    unittest.main()
