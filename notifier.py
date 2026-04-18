"""Desktop notification sender — cross-platform."""

import platform
import subprocess
import logging
import webbrowser

logger = logging.getLogger("gleis")


def _send_windows_toast(title: str, message: str, url: str | None = None) -> None:
    """Send a Windows toast notification via PowerShell.

    If *url* is provided, clicking the notification opens the URL in the
    default browser (uses the toast ``launch`` attribute).
    """
    safe_title = title.replace("'", "''").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    safe_message = message.replace("'", "''").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    launch_attr = f' launch="{url.replace(chr(34), "&quot;")}"' if url else ""

    ps_script = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$xml = @'
<toast{launch_attr} activationType="protocol">
  <visual>
    <binding template="ToastText02">
      <text id="1">{safe_title}</text>
      <text id="2">{safe_message}</text>
    </binding>
  </visual>
</toast>
'@
$doc = [Windows.Data.Xml.Dom.XmlDocument]::new()
$doc.LoadXml($xml)
$toast = [Windows.UI.Notifications.ToastNotification]::new($doc)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Gleis').Show($toast)
"""
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script],
        check=True,
        capture_output=True,
    )


def send_notification(title: str, message: str, urgency: str = "normal", url: str | None = None) -> None:
    """Send a desktop notification. Works on Windows, Linux, and macOS.

    On Windows, clicking the notification opens *url* (if provided).
    On other platforms the URL is appended to the message as a fallback.
    """
    system = platform.system()

    try:
        if system == "Windows":
            _send_windows_toast(title, message, url=url)
        elif system == "Linux":
            urgency_map = {"low": "low", "normal": "normal", "critical": "critical"}
            body = f"{message}\n{url}" if url else message
            subprocess.run(
                [
                    "notify-send",
                    "--urgency", urgency_map.get(urgency, "normal"),
                    "--app-name", "Gleis",
                    title,
                    body,
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
            # macOS doesn't support click-to-open natively; open in browser directly
            if url:
                webbrowser.open(url)
        else:
            # Fallback: just print
            logger.warning(f"[NOTIFICATION] {title}: {message}")

    except FileNotFoundError:
        logger.warning(f"Notification tool not found. {title}: {message}")
    except subprocess.CalledProcessError as e:
        logger.warning(f"Notification failed: {e}. {title}: {message}")
