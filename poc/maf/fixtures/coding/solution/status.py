"""Reference result, held by the POC acceptance suite rather than the Agent."""
def normalize_status(value: str) -> str:
    return value.strip().upper()
