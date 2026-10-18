def parse_retry_after(header: str) -> float:
    if not header or not header.strip():
        return 0.0
    return float(header.strip())
