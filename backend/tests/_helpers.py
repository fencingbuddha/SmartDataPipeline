def unwrap(j):
    """Return API data payload regardless of envelope/legacy shape."""
    if isinstance(j, dict) and "ok" in j and "data" in j:
        return j["data"]
    return j

def is_enveloped(j) -> bool:
    return isinstance(j, dict) and "ok" in j and "data" in j
