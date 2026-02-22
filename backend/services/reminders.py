"""Email reminder scheduler — weekday/weekend schedule aware.

Schedule:
- Weekday mornings: morning check-in reminder
- Weekday evenings: evening check-in reminder
- Saturday/Sunday mornings: weekend check-in reminder
- Sunday evening: weekly review reminder
"""

import logging
from datetime import date, datetime

import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.core.config import APP_URL
from backend.core.database import get_db, dict_from_row

log = logging.getLogger(__name__)


def _get_reminder_config() -> dict | None:
    with get_db() as db:
        row = db.execute("SELECT * FROM reminder_config WHERE id = 1").fetchone()
        return dict_from_row(row)


class ReminderService:
    """Sends scheduled email reminders with deep links to check-in forms."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()

    async def send_reminder(self, reminder_type: str) -> bool:
        """Send a single reminder email.

        reminder_type: 'morning', 'evening', 'weekend', 'weekly'
        """
        config = _get_reminder_config()
        if not config or not config.get("enabled") or not config.get("email"):
            log.info(f"Skipping {reminder_type} reminder — not configured")
            return False

        today = date.today()
        is_weekend = today.weekday() >= 5

        # Don't send morning/evening reminders on weekends (use weekend type instead)
        if reminder_type in ("morning", "evening") and is_weekend:
            return False
        # Don't send weekend reminders on weekdays
        if reminder_type == "weekend" and not is_weekend:
            return False

        # Check if already checked in today for this type
        with get_db() as db:
            existing = db.execute(
                "SELECT id FROM checkins WHERE date = ? AND type = ? AND completed = 1",
                (today.isoformat(), reminder_type),
            ).fetchone()
            if existing:
                log.info(f"Skipping {reminder_type} reminder — already completed")
                return False

        subject = {
            "morning": "Good morning — time for your morning check-in",
            "evening": "Evening check-in — how did today go?",
            "weekend": "Weekend check-in — log your session",
            "weekly": "Weekly review — reflect on the week",
        }.get(reminder_type, "Check-in reminder")

        checkin_url = f"{APP_URL}/checkin/{reminder_type}"
        body = f"""
        <h2>{subject}</h2>
        <p>
            <a href="{checkin_url}" style="
                display: inline-block;
                padding: 12px 24px;
                background: #58a6ff;
                color: white;
                text-decoration: none;
                border-radius: 8px;
                font-weight: bold;
            ">Open Check-in</a>
        </p>
        """

        return await self._send_email(config, subject, body)

    async def _send_email(self, config: dict, subject: str, html_body: str) -> bool:
        """Send an email using the configured SMTP settings."""
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = config.get("from_email") or config.get("smtp_user") or config["email"]
            msg["To"] = config["email"]
            msg.attach(MIMEText(html_body, "html"))

            await aiosmtplib.send(
                msg,
                hostname=config.get("smtp_host", "smtp.gmail.com"),
                port=config.get("smtp_port", 587),
                username=config.get("smtp_user"),
                password=config.get("smtp_password"),
                start_tls=True,
            )
            log.info(f"Sent reminder to {config['email']}: {subject}")
            return True
        except Exception as e:
            log.error(f"Failed to send email: {e}")
            return False

    def schedule_all(self):
        """Set up all reminder schedules based on config."""
        config = _get_reminder_config()
        if not config or not config.get("enabled"):
            log.info("Reminders not enabled")
            return

        morning_time = config.get("weekday_morning_time", "06:30").split(":")
        evening_time = config.get("weekday_evening_time", "21:00").split(":")
        weekend_time = config.get("weekend_morning_time", "09:30").split(":")
        weekly_time = config.get("weekly_review_time", "19:00").split(":")

        # Weekday morning (Mon-Fri)
        self.scheduler.add_job(
            self.send_reminder,
            CronTrigger(day_of_week="mon-fri", hour=int(morning_time[0]), minute=int(morning_time[1])),
            args=["morning"],
            id="morning_reminder",
            replace_existing=True,
        )

        # Weekday evening (Mon-Fri)
        self.scheduler.add_job(
            self.send_reminder,
            CronTrigger(day_of_week="mon-fri", hour=int(evening_time[0]), minute=int(evening_time[1])),
            args=["evening"],
            id="evening_reminder",
            replace_existing=True,
        )

        # Weekend morning (Sat-Sun)
        self.scheduler.add_job(
            self.send_reminder,
            CronTrigger(day_of_week="sat,sun", hour=int(weekend_time[0]), minute=int(weekend_time[1])),
            args=["weekend"],
            id="weekend_reminder",
            replace_existing=True,
        )

        # Weekly review (Sunday)
        self.scheduler.add_job(
            self.send_reminder,
            CronTrigger(day_of_week="sun", hour=int(weekly_time[0]), minute=int(weekly_time[1])),
            args=["weekly"],
            id="weekly_reminder",
            replace_existing=True,
        )

        self.scheduler.start()
        log.info("Reminder scheduler started")

    def stop(self):
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
