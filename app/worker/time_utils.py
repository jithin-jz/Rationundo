from datetime import date, datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def today_ist() -> date:
    return datetime.now(IST).date()


def now_ist_naive() -> datetime:
    return datetime.now(IST).replace(tzinfo=None)


def get_target_month_year(today: date | None = None) -> tuple[int, int, str]:
    """Determine the stock cycle using India time, including month boundaries."""
    current = today or today_ist()
    if current.day <= 3:
        if current.month == 1:
            return 12, current.year - 1, f"December {current.year - 1}"
        previous = date(current.year, current.month - 1, 1)
        return previous.month, previous.year, previous.strftime("%B %Y")
    return current.month, current.year, current.strftime("%B %Y")
