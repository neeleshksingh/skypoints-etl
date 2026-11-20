SOURCE_TO_ISO_ALPHA3 = {
    "USA": "USA",
    "IND": "IND",
    "CAN": "CAN",
    "PHIL": "PHL",
    "AU": "AUS",
}


def normalize_country(source_code: str) -> str:
    """Map a source-system country code to ISO alpha-3; reject codes we don't know."""
    if source_code not in SOURCE_TO_ISO_ALPHA3:
        raise ValueError(f"Unknown country code: {source_code!r}")
    return SOURCE_TO_ISO_ALPHA3[source_code]