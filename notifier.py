"""Desktop notification sender — cross-platform."""

import platform
import subprocess
import logging

logger = logging.getLogger("sbb-not")


def send_notification(title: str, message: str, urgency: str = "normal") -> None:
    """Send a desktop notification. Works on Linux and macOS."""
    system = platform.system()

    try:
        if system == "Linux":
            urgency_map = {"low": "low", "normal": "normal", "critical": "critical"}
            subprocess.run(
                [
                    "notify-send",
                    "--urgency", urgency_map.get(urgency, "normal"),
                    "--app-name", "SBB-Not",
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
