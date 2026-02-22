"""Email reminder scheduler — weekday/weekend schedule aware."""


class ReminderService:
    """Sends scheduled email reminders with deep links to check-in forms."""

    async def send_reminder(self, reminder_type: str) -> bool:
        raise NotImplementedError

    def schedule_all(self):
        raise NotImplementedError
