"""QuBot Scheduler Module.

This module provides utilities for scheduled tasks with APScheduler integration.
It contains dataclasses and helper functions to create and manage cron-style
scheduled tasks within the Discord bot ecosystem.

The module simplifies the creation of APScheduler CronTrigger objects by providing
a more intuitive interface for defining scheduled times with validation.

Example:
    Create a scheduled task for daily notifications:

        from utils.scheduler import ScheduledTime

        # Daily at 9:00 AM
        daily_time = ScheduledTime(hour=9, minute=0)
        trigger = daily_time.to_cron_trigger()

        # Weekly on Monday at 10:30 AM
        weekly_time = ScheduledTime(day=0, hour=10, minute=30)
        trigger = weekly_time.to_cron_trigger()

Note:
    - All scheduled times use the bot's default timezone (Europe/Rome)
    - Day numbering follows Python's convention (0=Monday, 6=Sunday)
    - Validation is performed automatically during object creation
"""

from dataclasses import dataclass
from typing import Optional
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger

from utils.constants import ZONE_INFO

# =============================================================================
# SCHEDULED TIME DATACLASS
# =============================================================================


@dataclass
class ScheduledTime:
    """Dataclass for defining scheduled times with APScheduler integration.

    This class provides a convenient way to define scheduled times with automatic
    validation and conversion to APScheduler CronTrigger objects. It supports
    both daily and weekly scheduling patterns.

    Attributes:
        day (Optional[int]): Day of the week (0=Monday, 6=Sunday). None for daily.
        hour (int): Hour of the day (0-23). Defaults to 0 (midnight).
        minute (int): Minute of the hour (0-59). Defaults to 0.
        timezone (ZoneInfo): Timezone for the scheduled time. Defaults to ZONE_INFO.

    Example:
        Create different types of scheduled times:

            # Daily at 9:15 AM
            daily = ScheduledTime(hour=9, minute=15)

            # Every Friday at 6:00 PM
            weekly = ScheduledTime(day=4, hour=18, minute=0)

            # Midnight daily (default values)
            midnight = ScheduledTime()
    """

    day: Optional[int] = None
    hour: int = 0
    minute: int = 0
    timezone: ZoneInfo = ZONE_INFO

    def __post_init__(self) -> None:
        """Validate time parameters during initialization.

        Performs validation of all time parameters to ensure they are within valid ranges.
        This prevents runtime errors when creating APScheduler triggers.

        Raises:
            ValueError: If day is not between 0-6 or None.
            ValueError: If hour is not between 0-23.
            ValueError: If minute is not between 0-59.

        Note:
            - Day validation: 0=Monday through 6=Sunday (Python standard)
            - Hour validation: 24-hour format (0=midnight, 23=11 PM)
            - Minute validation: Standard 60-minute hour
        """
        if self.day is not None and not 0 <= self.day <= 6:
            raise ValueError("day must be between 0-6 or None.")
        if not 0 <= self.hour <= 23:
            raise ValueError("hour must be between 0-23.")
        if not 0 <= self.minute <= 59:
            raise ValueError("minute must be between 0-59.")

    def to_cron_trigger(self) -> CronTrigger:
        """Convert the ScheduledTime to an APScheduler CronTrigger object.

        Creates a CronTrigger instance that can be used directly with APScheduler
        to schedule recurring tasks. The trigger respects the configured timezone
        and handles both daily and weekly scheduling patterns.

        Returns:
            CronTrigger: An APScheduler CronTrigger configured with this object's parameters.

        Example:
            Use with APScheduler to schedule a task:

                from apscheduler.schedulers.asyncio import AsyncIOScheduler

                scheduler = AsyncIOScheduler()
                scheduled_time = ScheduledTime(hour=9, minute=30)
                trigger = scheduled_time.to_cron_trigger()

                scheduler.add_job(
                    my_task_function,
                    trigger=trigger,
                    id="daily_task"
                )

        Note:
            - If day is None, creates a daily trigger
            - If day is specified, creates a weekly trigger for that day
            - Timezone is automatically applied to the trigger
        """
        return CronTrigger(
            day_of_week=self.day,
            hour=self.hour,
            minute=self.minute,
            timezone=self.timezone,
        )
