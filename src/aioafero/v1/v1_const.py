from typing import Final

AFERO_CLIENTS: Final[dict[str, dict[str, str]]] = {
    "hubspace": {
        "DEFAULT_USERAGENT": "Dart/2.15 (dart:io)",
        "DOMAIN": "afero.net",
        "API_HOST": "api2.afero.net",
        "ACCOUNT_ID_URL": "https://api2.afero.net/v1/users/me",
        "DEFAULT_ENCODING": "gzip",
        "DATA_URL": "https://api2.afero.net/v1/accounts/{}/metadevices",
        "DEVICE_STATE": "https://api2.afero.net/v1/accounts/{}/metadevices/{}/state",
        "DATA_HOST": "semantics2.afero.net",
        "APPLICATION_ID": "hubspace",
        "DEFAULT_CLIENT_ID": "hubspace_android",
        "DEFAULT_REDIRECT_URI": "hubspace-app://loginredirect",
        "OPENID_REALM": "thd",
        "OPENID_HOST": "accounts.hubspaceconnect.com",
        "OPENID_URL": (
            "https://accounts.hubspaceconnect.com/auth/realms/thd"
            "/protocol/openid-connect/auth"
        ),
        "CODE_URL": (
            "https://accounts.hubspaceconnect.com/auth/realms/thd"
            "/login-actions/authenticate"
        ),
        "TOKEN_URL": (
            "https://accounts.hubspaceconnect.com/auth/realms/thd/"
            "protocol/openid-connect/token"
        ),
    },
    "myko": {
        "DEFAULT_USERAGENT": "Dart/3.1 (dart:io)",
        "DOMAIN": "sxz2xlhh.afero.net",
        "API_HOST": "api2.sxz2xlhh.afero.net",
        "ACCOUNT_ID_URL": "https://api2.sxz2xlhh.afero.net/v1/users/me",
        "DEFAULT_ENCODING": "gzip",
        "DATA_URL": "https://api2.sxz2xlhh.afero.net/v1/accounts/{}/metadevices",
        "DEVICE_STATE": "https://api2.sxz2xlhh.afero.net/v1/accounts/{}/metadevices/{}/state",
        "DATA_HOST": "semantics2.sxz2xlhh.afero.net",
        "APPLICATION_ID": "kfi",
        "DEFAULT_CLIENT_ID": "kfi_android",
        "DEFAULT_REDIRECT_URI": "kfi-app://loginredirect",
        "OPENID_REALM": "kfi",
        "OPENID_HOST": "accounts.mykoapp.com",
        "OPENID_URL": "https://accounts.mykoapp.com/auth/realms/kfi/protocol/openid-connect/auth",
        "CODE_URL": "https://accounts.mykoapp.com/auth/realms/kfi/login-actions/authenticate",
        "TOKEN_URL": "https://accounts.mykoapp.com/auth/realms/kfi/protocol/openid-connect/token",
    },
}

MAX_RETRIES: Final[int] = 3
