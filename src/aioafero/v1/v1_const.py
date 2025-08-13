"""Constants for accessing Afero API."""

from typing import Final

AFERO_CLIENTS: Final[dict[str, dict[str, str]]] = {
    "hubspace": {
        "DEFAULT_USERAGENT": "Dart/2.15 (dart:io)",
        "DOMAIN": "afero.net",
        "API_HOST": "api2.afero.net",
        "AUTH_BASE_URL": "accounts.hubspaceconnect.com/auth/realms/thd",
        "DATA_HOST": "semantics2.afero.net",
        "DEFAULT_CLIENT_ID": "hubspace_android",
        "DEFAULT_REDIRECT_URI": "hubspace-app://loginredirect",
        "OPENID_HOST": "accounts.hubspaceconnect.com",
    },
    "myko": {
        "DEFAULT_USERAGENT": "Dart/3.1 (dart:io)",
        "DOMAIN": "sxz2xlhh.afero.net",
        "API_HOST": "api2.sxz2xlhh.afero.net",
        "DATA_HOST": "semantics2.sxz2xlhh.afero.net",
        "DEFAULT_CLIENT_ID": "kfi_android",
        "DEFAULT_REDIRECT_URI": "kfi-app://loginredirect",
        "OPENID_HOST": "accounts.mykoapp.com",
    },
}


AFERO_GENERICS: Final[dict[str, str]] = {
    "AUTH_OPENID_ENDPOINT": "/protocol/openid-connect/auth",
    "AUTH_CODE_ENDPOINT": "/login-actions/authenticate",
    "AUTH_TOKEN_ENDPOINT": "/protocol/openid-connect/token",
    "ACCOUNT_ID_ENDPOINT": "/v1/users/me",
    "DATA_ENDPOINT": "/v1/accounts/{}/metadevices",
    "DEVICE_STATE_ENDPOINT": "/v1/accounts/{}/metadevices/{}/state",
}

MAX_RETRIES: Final[int] = 3
