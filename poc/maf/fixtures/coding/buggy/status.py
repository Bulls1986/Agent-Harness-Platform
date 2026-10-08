"""Defective baseline; verification must fail and trigger a legitimate replan."""
def normalize_status(value: str) -> str:
    return value.strip().lower()
