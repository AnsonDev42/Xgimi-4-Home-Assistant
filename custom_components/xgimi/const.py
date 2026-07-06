"""Constants for Xgimi Integration."""

import re

# Base component constants
NAME = "Xgimi Projector Integration"
DOMAIN = "xgimi"
DOMAIN_DATA = f"{DOMAIN}_data"
VERSION = "0.0.9"

COMMAND_PORT = 16735
ADVANCE_PORT = 16750
ALIVE_PORT = 554

BLE_COMPANY_ID = 0x0046
BLE_SERVICE_UUID = "1812"
BLE_ADVERTISEMENT_TIMEOUT = 1
BLE_POWER_ON_REPEATS = 3
BLE_POWER_ON_REPEAT_DELAY = 0.25

_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")


def normalize_manufacturer_data(value: str) -> str:
    """Return normalized BLE manufacturer data or raise ValueError."""
    token = "".join(str(value).replace(":", "").split())
    if not token or len(token) % 2 or not _HEX_RE.fullmatch(token):
        raise ValueError("BLE token must be an even-length hex string")
    return token.lower()
