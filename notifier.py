"""Desktop notification sender — cross-platform."""

import platform
import subprocess
import logging

logger = logging.getLogger("gleis")


def _send_windows_toast(title: str, message: str) -> None:
    """Send a Windows toast notification via PowerShell."""
    ps_script = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$textNodes = $template.GetElementsByTagName('text')
$textNodes.Item(0).AppendChild($template.CreateTextNode('{title.replace("'", "''")}')) > $null
$textNodes.Item(1).AppendChild($template.CreateTextNode('{message.replace("'", "''")}')) > $null
$toast = [Windows.UI.Notifications.ToastNotification]::new($template)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Gleis').Show($toast)
"""
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script],
        check=True,
        capture_output=True,
    )


def send_notification(title: str, message: str, urgency: str = "normal") -> None:
    """Send a desktop notification. Works on Windows, Linux, and macOS."""
    system = platform.system()

    try:
        if system == "Windows":
            _send_windows_toast(title, message)
        elif system == "Linux":
            urgency_map = {"low": "low", "normal": "normal", "critical": "critical"}
            subprocess.run(
                [
                    "notify-send",
                    "--urgency", urgency_map.get(urgency, "normal"),
                    "--app-name", "Gleis",
                    title,
                    message,
                ],
                check=True,
                capture_output=True,
            )
        elif system == "Darwin":
            # macOS — use osascript
            escaped_title = title.replace('"', '\\"')
            escaped_msg = message.replace('"', '\\"')
            script = f'display notification "{escaped_msg}" with title "{escaped_title}" sound name "default"'
            subprocess.run(
                ["osascript", "-e", script],
                check=True,
                capture_output=True,
            )
        else:
            # Fallback: just print
            logger.warning(f"[NOTIFICATION] {title}: {message}")

    except FileNotFoundError:
        logger.warning(f"Notification tool not found. {title}: {message}")
    except subprocess.CalledProcessError as e:
        logger.warning(f"Notification failed: {e}. {title}: {message}")
