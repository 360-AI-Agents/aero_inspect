import uuid
from datetime import datetime


def generate_report_title(inspection_name: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{inspection_name}_Report_{timestamp}"


def generate_uid() -> str:
    return str(uuid.uuid4())