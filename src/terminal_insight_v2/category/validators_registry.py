"""Built-in validator IDs allowed in Excel templates."""

KNOWN_VALIDATORS = frozenset(
    {
        "non_empty",
        "date_iso",
        "has_digit",
        "ip_rating",
        "mah",
        "watt",
        "storage_combo",
        "screen_token",
        "weight_g",
        "yes_no_zh",
        "watch_water",
        "watch_battery",
        "watch_size",
    }
)
