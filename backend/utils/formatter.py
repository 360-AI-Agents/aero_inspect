from datetime import datetime


def format_datetime(dt: datetime) -> str:
    if not dt:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_percentage(value: float) -> str:
    return f"{round(value, 2)}%"


def format_status_label(status: str) -> str:
    return status.replace("_", " ").title()