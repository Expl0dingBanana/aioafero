"""Constants for accessing Afero API."""

from typing import Final

AFERO_CLIENTS: Final[dict[str, dict[str, str]]] = {
    "hubspace": {
        "API_DATA_HOST": "semantics2.afero.net",
        "API_HOST": "api2.afero.net",
        "AUTH_DEFAULT_CLIENT_ID": "hubspace_android",
        "AUTH_DEFAULT_REDIRECT_URI": "hubspace-app://loginredirect",
        "AUTH_OPENID_HOST": "accounts.hubspaceconnect.com",
        "AUTH_REALM": "thd",
    },
    "myko": {
        "API_DATA_HOST": "semantics2.sxz2xlhh.afero.net",
        "API_HOST": "api2.sxz2xlhh.afero.net",
        "AUTH_DEFAULT_CLIENT_ID": "kfi_android",
        "AUTH_DEFAULT_REDIRECT_URI": "kfi-app://loginredirect",
        "AUTH_OPENID_HOST": "accounts.mykoapp.com",
        "AUTH_REALM": "kfi",
    },
}


AFERO_GENERICS: Final[dict[str, str]] = {
    # Generics
    "DEFAULT_USERAGENT": "Dart/3.1 (dart:io)",
    # API Endpoints
    "API_DEVICE_ENDPOINT": "/v1/accounts/{}/metadevices",
    "API_DEVICE_STATE_ENDPOINT": "/v1/accounts/{}/metadevices/{}/state",
    "API_DEVICE_VERSIONS_ENDPOINT": "/v1/accounts/{}/devices/{}/versions",
    # Auth endpoints
    "AUTH_OPENID_ENDPOINT": "/protocol/openid-connect/auth",
    "AUTH_CODE_ENDPOINT": "/login-actions/authenticate",
    "AUTH_TOKEN_ENDPOINT": "/protocol/openid-connect/token",
    "ACCOUNT_ID_ENDPOINT": "/v1/users/me",
}

MAX_RETRIES: Final[int] = 3

# Version polling interval in seconds (6 hours)
VERSION_POLL_INTERVAL_SECONDS = 6 * 3600
