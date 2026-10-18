import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTime, Qt
from PySide6.QtWidgets import QApplication, QCheckBox, QMessageBox

from Database.Database1 import DataBase
from Settings import Settings
from config import WEIGHTS
from gui import MainWindow, SettingsDialog, TaskDialog
from i18n import colors
from TasksHere_gui import _should_start_hidden


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.database = DataBase(root / "tasks.json")
        self.settings = Settings(root / "settings.json")
        future = datetime.now() + timedelta(days=1)
        self.database.new_task(
            [3.0] * 10 + [future.strftime(DataBase.DATE_FORMAT)],
            "Active task",
            "Some notes",
        )
        past_info = [2.0] * 10 + [
            (datetime.now() - timedelta(minutes=5)).strftime(
                DataBase.DATE_FORMAT
            )
        ]
        timed_out = {
            "task_name": "Expired task",
            "info": past_info,
            "note": "Past deadline",
            "created_at": datetime.now().strftime(DataBase.DATE_FORMAT),
            "weight": 0,
        }
        self.database._write_tasks(
            [*self.database.get_tasks(), timed_out]
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_refresh_separates_active_and_timed_out_tasks(self) -> None:
        window = MainWindow(self.database, WEIGHTS, self.settings)

        self.assertEqual(window.task_table.rowCount(), 1)
        self.assertEqual(window.timeout_table.rowCount(), 1)
        expired_name = window.timeout_table.item(0, 0)
        if expired_name is None:
            self.fail("The timed-out task name was not shown")
        self.assertEqual(expired_name.text(), "Expired task")

        window.refresh_timer.stop()

        window.refresh_timer.stop()
        window.close()

    def test_clear_button_removes_all_expired_tasks_only(self) -> None:
        window = MainWindow(self.database, WEIGHTS, self.settings)
        window.refresh_timer.stop()
        with patch(
            "gui.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            window._clear_timed_out_tasks()

        self.assertIsNone(self.database.get_task("Expired task"))
        self.assertIsNotNone(self.database.get_task("Active task"))
        self.assertEqual(window.timeout_table.rowCount(), 0)
        window.close()

    def test_language_and_dark_mode_are_applied(self) -> None:
        window = MainWindow(self.database, WEIGHTS, self.settings)
        window.refresh_timer.stop()
        self.settings.set_values(mode="Dark", Language="Eng")
        window._apply_theme()
        window._apply_language()

        self.assertEqual(window.active_title.text(), "Tasks")
        self.assertEqual(window.clear_button.text(), "Clear expired deadline tasks")
        self.assertIn("#171a21", window.styleSheet())
        self.assertIn("gridline-color: #303642", window.styleSheet())
        window.close()

    def test_task_dialog_builds_weekly_schedule_values(self) -> None:
        dialog = TaskDialog(WEIGHTS, language="Eng")
        dialog.task_type_input.setCurrentIndex(
            dialog.task_type_input.findData("type_3")
        )
        dialog.weekday_input.setCurrentIndex(2)
        dialog.schedule_mode_input.setCurrentIndex(
            dialog.schedule_mode_input.findData("specific")
        )
        dialog.schedule_time_input.setTime(QTime(17, 30, 0))

        info, _, _, task_type, schedule = dialog.get_task_values()

        self.assertEqual(task_type, "type_3")
        self.assertIsNotNone(schedule)
        if schedule is None:
            self.fail("Weekly task schedule was not returned")
        self.assertEqual(schedule["weekday"], 2)
        self.assertEqual(schedule["deadline_time"], "17:30:00")
        self.assertEqual(len(info), 11)
        dialog.close()

    def test_main_window_has_two_type_filterable_task_tables(self) -> None:
        self.settings.set_values(Language="Eng")
        self.database.new_task(
            [3.0] * 10 + [datetime.now().strftime(DataBase.DATE_FORMAT)],
            "Daily task",
            "Repeats daily",
            task_type="type_2",
            schedule={},
        )
        window = MainWindow(self.database, WEIGHTS, self.settings)
        window.refresh_timer.stop()

        self.assertEqual(window.task_table.columnCount(), 4)
        self.assertEqual(window.timeout_table.columnCount(), 4)
        self.assertEqual(window.task_table.horizontalHeaderItem(1).text(), "Type")
        self.assertEqual(window.timeout_table.horizontalHeaderItem(1).text(), "Type")
        self.assertEqual(window.task_type_filter.count(), 5)
        self.assertEqual(window.task_type_filter.itemText(0), "All")
        self.assertEqual(window.task_type_filter.itemText(1), "Daily")
        self.assertEqual(window.timeout_type_filter.count(), 5)

        daily_row = next(
            row
            for row in range(window.task_table.rowCount())
            if window.task_table.item(row, 0).text() == "Daily task"
        )
        window.task_type_filter.setCurrentIndex(
            window.task_type_filter.findData("type_2")
        )
        self.assertFalse(window.task_table.isRowHidden(daily_row))
        deadline_row = next(
            row
            for row in range(window.task_table.rowCount())
            if window.task_table.item(row, 0).text() == "Active task"
        )
        self.assertTrue(window.task_table.isRowHidden(deadline_row))

        window.task_type_filter.setCurrentIndex(0)
        self.assertFalse(window.task_table.isRowHidden(deadline_row))
        self.assertIn("QScrollBar:vertical", window.styleSheet())
        self.assertIn("gridline-color: #eef0f5", window.styleSheet())
        self.assertIn("border-bottom: 1px solid #eef0f5", window.styleSheet())
        window.close()

    def test_deadline_calendar_has_explicit_light_and_weekend_colors(self) -> None:
        dialog = TaskDialog(WEIGHTS, language="Eng", mode="Light")

        calendar_stylesheet = dialog.deadline_input.calendarWidget().styleSheet()
        self.assertIn("#ffffff", calendar_stylesheet)
        self.assertIn("background-color: #ffffff", calendar_stylesheet)
        self.assertEqual(
            dialog.deadline_input.calendarWidget().weekdayTextFormat(
                Qt.DayOfWeek.Saturday
            ).foreground().color().name(),
            "#d64545",
        )

    def test_dropdowns_use_palette_colors(self) -> None:
        window = MainWindow(self.database, WEIGHTS, self.settings)
        window.refresh_timer.stop()

        self.assertIn("QComboBox::drop-down", window.styleSheet())
        self.assertIn("QComboBox QAbstractItemView", window.styleSheet())
        self.assertIn(
            "QComboBox QAbstractItemView::item:selected",
            window.styleSheet(),
        )
        self.assertIn("border: 1px solid #e0e5ef", window.styleSheet())
        self.assertIn(
            "background: #f4f6fb;\n                border: 1px solid #e0e5ef",
            window.styleSheet(),
        )
        combo = window.task_type_filter
        view = combo.view()
        self.assertEqual(view.frameShape().name, "NoFrame")

        for mode in ("Light", "Dark"):
            self.settings.set_values(mode=mode)
            window._apply_theme()
            popup = view.window()
            combo.showPopup()
            self.application.processEvents()
            image = popup.grab().toImage()
            self.assertEqual(popup.width(), combo.width())
            palette = colors(mode)
            allowed_popup_colors = {
                palette["surface"],
                palette["border"],
            }
            for point in (
                (0, image.height() // 2),
                (image.width() - 1, image.height() // 2),
                (image.width() // 2, image.height() - 1),
            ):
                self.assertIn(
                    image.pixelColor(*point).name(),
                    allowed_popup_colors,
                )
            combo.hidePopup()
        window.close()

    def test_show_only_tray_setting_is_available_in_settings_dialog(self) -> None:
        dialog = SettingsDialog(self.settings)
        control = dialog.controls["Just Show Only TrayIon"]
        self.assertIsInstance(control, QCheckBox)
        if not isinstance(control, QCheckBox):
            self.fail("The show-only-tray setting is not a checkbox")
        control.setChecked(True)
        dialog._save()
        self.assertTrue(getattr(self.settings, "Just Show Only TrayIon"))

    def test_startup_hides_window_only_when_tray_is_available(self) -> None:
        self.settings.set_values(**{"Just Show Only TrayIon": True})

        self.assertTrue(_should_start_hidden(self.settings, tray_available=True))
        self.assertFalse(_should_start_hidden(self.settings, tray_available=False))


if __name__ == "__main__":
    unittest.main()
