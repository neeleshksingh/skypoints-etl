MANDATORY_FIELDS = ("member_name", "member_id", "enrollment_date")
NULL_SENTINELS = {"", "NULL"}


def is_blank(value: str) -> bool:
    """Treat empty, whitespace-only and the literal text 'NULL' as missing."""
    return value.strip() in NULL_SENTINELS


def find_missing_mandatory_fields(record: dict) -> list:
    """List every mandatory field that is blank, in layout order."""
    return [field for field in MANDATORY_FIELDS if is_blank(record[field])]