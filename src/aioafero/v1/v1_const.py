from typing import Final

HUBSPACE_DEFAULT_USERAGENT: Final[str] = "Dart/2.15 (dart:io)"
HUBSPACE_ACCOUNT_ID_URL: Final[str] = "https://api2.afero.net/v1/users/me"
HUBSPACE_DEFAULT_ENCODING: Final[str] = "gzip"

HUBSPACE_DATA_URL: Final[str] = "https://api2.afero.net/v1/accounts/{}/metadevices"

HUBSPACE_DEVICE_STATE: Final[str] = (
    "https://api2.afero.net/v1/accounts/{}/metadevices/{}/state"
)
HUBSPACE_DATA_HOST: Final[str] = "semantics2.afero.net"

DEFAULT_HEADERS: Final[dict[str, str]] = {
    "user-agent": HUBSPACE_DEFAULT_USERAGENT,
    "accept-encoding": HUBSPACE_DEFAULT_ENCODING,
}

MAX_RETRIES: Final[int] = 3
