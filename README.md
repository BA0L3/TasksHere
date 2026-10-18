# TasksHere

![app](Datas/assets/TaskHere.png)

Review:

![rv1](image/README/1792078415206.png)

TasksHere is a task manager (actually it s"Real-Life Works" Manager) for Windows 10 and Windows 11. It provides both a
command-line interface (CLI) and a graphical interface (GUI), and automatically
orders tasks by a calculated priority score.

## Features

- Create, update, list, and remove tasks.
- Score each task using ten criteria and add an optional note.
- Create one-time deadline tasks or recurring daily, weekly, monthly, and yearly
  tasks with an end-of-day or specific-time deadline.
- Keep recurring tasks in their own tab while their scheduled window is active;
  otherwise they remain in the timed-out tab and return automatically next time.
- Keep tasks sorted from highest to lowest priority.
- Use reminders, deadline alerts, and a Windows system-tray icon.
- Packaged GUI and CLI builds can check for GitHub ZIP releases and apply an
  update after the running application exits.
- Choose the interface language and appearance in the application settings. (EngLish and Tiếng Việt are supported))

| Stored type | Task kind |
| ----------- | --------- |
| `type_1` | One-time task with a future date and time |
| `type_2` | Daily recurring task |
| `type_3` | Weekly recurring task |
| `type_4` | Monthly recurring task |
| `type_5` | Yearly recurring task |

## Getting started

### Requirements

- Windows 10 or Windows 11
- Python 3.10 or later

Install the application dependencies:

```powershell
python -m pip install PySide6 prompt_toolkit pystray Pillow windows-toasts requests
```

### Start the application

Run these commands from the project directory:

```powershell
# Command-line interface
python main.py

# Graphical interface
python main_gui.py
```

### Use the CLI

At the `tasks>` prompt, enter one of these commands:

| Command              | Action                                                                   |
| -------------------- | ------------------------------------------------------------------------ |
| `add`              | Create a task by entering its name, scores, deadline, and optional note. |
| `list`             | Show tasks sorted by priority.                                           |
| `update`           | Change a task's details.                                                 |
| `remove`           | Delete a task.                                                           |
| `settings`         | View or change application settings.                                     |
| `help`             | Show the available commands.                                             |
| `exit` or `quit` | Close the CLI.                                                           |

For each task, rate the first nine criteria from 1 to 5, then provide a Regret
Score from 1 to 5. Deadline tasks require a future date and time. Recurring
tasks ask for a weekday, day of month, or month/day as appropriate. Monthly
dates beyond a month's length run on its last day; a yearly February 29 task
runs on February 28 in non-leap years. In the GUI, use the task-type selector
and schedule controls; all task types share `Datas/Tasks.json`. Completing a
recurring task from a notification keeps it in the database and suppresses it
until its next scheduled occurrence. Clearing timed-out tasks only removes
one-time deadline tasks.

## Data and settings

The application stores task data in `Datas/Tasks.json` and settings in
`Datas/settings.json`. Logs are written to `Datas/logs/taskshere.log`. Keep the
`Datas` directory alongside the application files so the image, icon, and saved
data remain available.

Created & Developed by: BA0L3 (Lê Nguyễn Gia Bảo)
