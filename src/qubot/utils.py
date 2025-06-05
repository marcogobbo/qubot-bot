from datetime import datetime, timedelta
import pytz

def seconds_until_target(day_of_week, hour, minute):
    now = datetime.now(pytz.timezone("Europe/Rome"))
    today = now.weekday()
    days_ahead = (day_of_week - today + 7) % 7
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if days_ahead == 0 and now > target:
        days_ahead = 7

    target += timedelta(days=days_ahead)
    return (target - now).total_seconds()
