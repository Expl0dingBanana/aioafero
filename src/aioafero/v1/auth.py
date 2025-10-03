"""Handle authentication to Afero API."""

__all__ = ["AferoAuth", "TokenData", "passthrough"]

import asyncio
import base64
from contextlib import contextmanager
import datetime
import hashlib
import logging
import os
import re
from typing import Final, NamedTuple
from urllib.parse import parse_qs, urlparse

import aiohttp
from aiohttp import ClientResponseError, ContentTypeError
from bs4 import BeautifulSoup
from securelogging import LogRedactorMessage, add_secret, remove_secret

from aioafero.errors import InvalidAuth, InvalidOTP, InvalidResponse, OTPRequired

from . import v1_const

logger = logging.getLogger(__name__)

TOKEN_TIMEOUT: Final[int] = 118
STATUS_CODE: Final[str] = "Status Code: %s"


class AuthChallenge(NamedTuple):
    """Data used to perform the initial authentication."""

    challenge: str
    verifier: str


class TokenData(NamedTuple):
    """Data related to the current token."""

    token: str
    access_token: str
    refresh_token: str
    expiration: float


class AuthSessionData(NamedTuple):
    """Data related to current attempt to login."""

    session_code: str
    execution: str
    tab_id: str


@contextmanager
def passthrough():
    """Do nothing."""
    yield


class AferoAuth:
    """Authentication against the Afero IoT API.

    This class follows the Afero IoT authentication workflow and utilizes
    refresh tokens.
    """

    def __init__(
        self,
        bridge,
        username,
        password,
        hide_secrets: bool = True,
        refresh_token: str | None = None,
        afero_client: str | None = "hubspace",
    ):
        """Create a class to handle authentication with Afero IoT API."""
        self.logger = logging.getLogger(f"{__package__}[{username}]")
        if hide_secrets:
            self.secret_logger = LogRedactorMessage
        else:
            self.secret_logger = passthrough
        self._hide_secrets: bool = hide_secrets
        self._async_lock: asyncio.Lock = asyncio.Lock()
        self._username: str = username
        self._password: str = password
        self._token_data: TokenData | None = None
        self._bridge = bridge
        if refresh_token:
            add_secret(refresh_token)
            self._token_data = TokenData(
                None, None, refresh_token, datetime.datetime.now().timestamp()
            )
        self._afero_client: str = afero_client
        self._token_headers: dict[str, str] = {
            "Content-Type": "application/x-www-form-urlencoded",
            "accept-encoding": "gzip",
            "host": v1_const.AFERO_CLIENTS[self._afero_client]["AUTH_OPENID_HOST"],
        }
        self._otp_data: dict = {}

    @property
    async def is_expired(self) -> bool:
        """Determine if the token is expired."""
        if not self._token_data:
            return True
        return datetime.datetime.now().timestamp() >= self._token_data.expiration

    @property
    def refresh_token(self) -> str | None:
        """Get the current refresh token."""
        if not self._token_data:
            return None
        return self._token_data.refresh_token

    def generate_auth_url(self, endpoint: str) -> str:
        """Generate an auth URL for the Afero API."""
        endpoint = endpoint.removeprefix("/")
        return f"https://{v1_const.AFERO_CLIENTS[self._afero_client]['AUTH_OPENID_HOST']}/auth/realms/{v1_const.AFERO_CLIENTS[self._afero_client]['AUTH_REALM']}/{endpoint}"

    def set_token_data(self, data: TokenData) -> None:
        """Set the current taken data."""
        self._token_data = data

    async def webapp_login(self, challenge: AuthChallenge) -> str:
        """Perform login to the webapp for a code.

        Login to the webapp and generate a code used for generating tokens.

        :param challenge: Challenge data for connection and approving

        :return: Code used for generating a refresh token
        """
        code_params: dict[str, str] = {
            "response_type": "code",
            "client_id": v1_const.AFERO_CLIENTS[self._afero_client][
                "AUTH_DEFAULT_CLIENT_ID"
            ],
            "redirect_uri": v1_const.AFERO_CLIENTS[self._afero_client][
                "AUTH_DEFAULT_REDIRECT_URI"
            ],
            "code_challenge": challenge.challenge,
            "code_challenge_method": "S256",
            "scope": "openid offline_access",
        }
        url = self.generate_auth_url(v1_const.AFERO_GENERICS["AUTH_OPENID_ENDPOINT"])
        self.logger.debug(
            "URL: %s\n\tparams: %s",
            url,
            code_params,
        )
        try:
            response = await self._bridge.request(
                "GET",
                url,
                include_token=False,
                params=code_params,
                allow_redirects=False,
            )
        except aiohttp.web_exceptions.HTTPError as err:
            raise InvalidResponse("Unable to query login page") from err
        if response.status == 200:
            contents = await response.text()
            login_data = await extract_login_data(contents, "kc-form-login")
            self.logger.debug(
                ("WebApp Login:\n\tSession Code: %s\n\tExecution: %s\n\tTab ID:%s"),
                login_data.session_code,
                login_data.execution,
                login_data.tab_id,
            )
            return await self.generate_code(login_data, challenge)
        if response.status == 302:
            self.logger.debug("Hubspace returned an active session")
            return await AferoAuth.parse_code(response)
        try:
            response.raise_for_status()
        except ClientResponseError as err:
            raise InvalidResponse("Unable to query login page") from err

    @staticmethod
    async def generate_challenge_data() -> AuthChallenge:
        """Generate data to send to Afero API when logging into the system."""
        code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode("utf-8")
        code_verifier = re.sub("[^a-zA-Z0-9]+", "", code_verifier)
        code_challenge = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge).decode("utf-8")
        code_challenge = code_challenge.replace("=", "")
        chal = AuthChallenge(code_challenge, code_verifier)
        logger.debug("Challenge information: %s", chal)
        return chal

    async def generate_code(
        self, data: AuthSessionData, challenge: AuthChallenge
    ) -> str:
        """Finalize login to Afero IoT page.

        :param session_code: Session code during form interaction
        :param execution: Session code during form interaction
        :param tab_id: Session code during form interaction
        :return: code for generating tokens
        """
        self.logger.debug("Generating code")
        params = extract_login_codes(data, self._afero_client)
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "x-requested-with": "io.afero.partner.hubspace",
        }
        auth_data = {
            "username": self._username,
            "password": self._password,
            "credentialId": "",
        }
        url = self.generate_auth_url(v1_const.AFERO_GENERICS["AUTH_CODE_ENDPOINT"])
        self.logger.debug(
            "URL: %s\n\tparams: %s\n\theaders: %s",
            url,
            params,
            headers,
        )
        response = await self._bridge.request(
            "POST",
            url,
            include_token=False,
            params=params,
            data=auth_data,
            headers=headers,
            allow_redirects=False,
        )
        self.logger.debug(STATUS_CODE, response.status)
        # If OTP is required, a 200 will be returned. If a 302 is returned, then there
        # is no OTP required.
        content = await response.text()
        if await AferoAuth.requires_otp(content):
            login_data = await extract_login_data(content, "kc-otp-login-form")
            otp_params = extract_login_codes(login_data, self._afero_client)
            self._otp_data = {
                "params": otp_params,
                "headers": headers,
                "challenge": challenge,
            }
            raise OTPRequired
        if response.status != 302:
            raise InvalidAuth(
                "Unable to authenticate with the supplied username / password"
            )
        return await AferoAuth.parse_code(response)

    @staticmethod
    async def requires_otp(content: str) -> bool:
        """Determine if the user requires otp."""
        return "kc-otp-login-form" in content

    @staticmethod
    async def parse_code(response: aiohttp.ClientResponse) -> str:
        """Parse the code for generating tokens."""
        try:
            parsed_url = urlparse(response.headers["location"])
            code = parse_qs(parsed_url.query)["code"][0]
            logger.debug("Location: %s", response.headers.get("location"))
            logger.debug("Code: %s", code)
        except KeyError as err:
            raise InvalidResponse(
                f"Unable to process the result from {response.url}: {response.status}"
            ) from err
        return code

    async def generate_refresh_token(
        self,
        challenge: AuthChallenge | None = None,
        code: str | None = None,
    ) -> TokenData:
        """Generate a refresh token.

        If a challenge is provided, it will send the correct data. If no challenge is required,
        it will use the existing token

        :param client: async client for making request
        :param code: Code used for generating refresh token
        :param challenge: Challenge data for connection and approving

        :return: Refresh token to generate a new token
        """
        self.logger.debug("Generating refresh token")
        if challenge:
            data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": v1_const.AFERO_CLIENTS[self._afero_client][
                    "AUTH_DEFAULT_REDIRECT_URI"
                ],
                "code_verifier": challenge.verifier,
                "client_id": v1_const.AFERO_CLIENTS[self._afero_client][
                    "AUTH_DEFAULT_CLIENT_ID"
                ],
            }
        else:
            data = {
                "grant_type": "refresh_token",
                "refresh_token": self._token_data.refresh_token,
                "scope": "openid email offline_access profile",
                "client_id": v1_const.AFERO_CLIENTS[self._afero_client][
                    "AUTH_DEFAULT_CLIENT_ID"
                ],
            }
        url = self.generate_auth_url(v1_const.AFERO_GENERICS["AUTH_TOKEN_ENDPOINT"])
        with self.secret_logger():
            self.logger.debug(
                "URL: %s\n\tdata: %s\n\theaders: %s",
                url,
                data,
                self._token_headers,
            )
        response = await self._bridge.request(
            "POST",
            url,
            headers=self._token_headers,
            include_token=False,
            data=data,
        )
        self.logger.debug(STATUS_CODE, response.status)
        try:
            resp_json = await response.json()
        except (ValueError, ContentTypeError) as err:
            raise InvalidResponse(
                "Unexpected data returned during token refresh"
            ) from err
        if response.status != 200:
            if resp_json and resp_json.get("error") == "invalid_grant":
                raise InvalidAuth
            try:
                response.raise_for_status()
            except ClientResponseError as err:
                raise InvalidResponse(
                    "Unexpected data returned during token refresh"
                ) from err
        try:
            refresh_token = resp_json["refresh_token"]
            access_token = resp_json["access_token"]
            id_token = resp_json["id_token"]
        except KeyError as err:
            raise InvalidResponse("Unable to extract refresh token") from err
        add_secret(refresh_token)
        add_secret(access_token)
        add_secret(id_token)
        with self.secret_logger():
            self.logger.debug("JSON response: %s", resp_json)
        return TokenData(
            id_token,
            access_token,
            refresh_token,
            datetime.datetime.now().timestamp() + TOKEN_TIMEOUT,
        )

    async def perform_initial_login(self) -> TokenData:
        """Login to generate a refresh token.

        :return: Refresh token for the auth
        """
        challenge = await AferoAuth.generate_challenge_data()
        code: str = await self.webapp_login(challenge)
        self.logger.debug("Successfully generated an auth code")
        refresh_token = await self.generate_refresh_token(
            code=code, challenge=challenge
        )
        self.logger.debug("Successfully generated a refresh token")
        return refresh_token

    async def perform_otp_login(self, otp_code: str) -> TokenData:
        """Perform otp login to generate a refresh token.

        :return: Refresh token for the auth
        """
        if self._otp_data == {}:
            raise OTPRequired("No OTP data available to perform login")
        self.logger.debug("Performing otp login")
        code: str = await self.submit_otp(otp_code)
        refresh_token = await self.generate_refresh_token(
            code=code, challenge=self._otp_data["challenge"]
        )
        self.logger.debug("Successfully generated a refresh token")
        self._token_data = refresh_token
        self._otp_data = {}
        return refresh_token

    async def submit_otp(self, otp_code: str) -> None:
        """Submit OTP code to continue the login process.

        :param otp_code: OTP code provided by the user

        :return: Code used for generating a refresh token
        """
        otp_data = {
            "action": "submit",
            "flowName": "doLogIn",
            "emailCode": otp_code,
        }
        url = self.generate_auth_url(v1_const.AFERO_GENERICS["AUTH_CODE_ENDPOINT"])
        response = await self._bridge.request(
            "POST",
            url,
            include_token=False,
            params=self._otp_data["params"],
            data=otp_data,
            headers=self._otp_data["headers"],
            allow_redirects=False,
        )
        if response.status != 302:
            self.logger.warning("OTP code was invalid. Re-enter the OTP code.")
            content = await response.text()
            kc_error = get_kc_error(content)
            login_data = await extract_login_data(content, "kc-otp-login-form")
            otp_params = extract_login_codes(login_data, self._afero_client)
            self._otp_data["params"] = otp_params
            raise InvalidOTP(kc_error)
        return await AferoAuth.parse_code(response)

    async def token(self, retry: bool = True) -> str:
        """Generate the token required to make Afero API calls."""
        invalidate_refresh_token = False
        async with self._async_lock:
            if not self._token_data:
                self.logger.debug(
                    "Refresh token not present. Generating a new refresh token"
                )
                self._token_data = await self.perform_initial_login()
            if await self.is_expired:
                self.logger.debug("Token has not been generated or is expired")
                try:
                    new_data = await self.generate_refresh_token()
                    remove_secret(self._token_data.token)
                    remove_secret(self._token_data.access_token)
                    remove_secret(self._token_data.refresh_token)
                    self._token_data = new_data
                except InvalidAuth:
                    self.logger.debug("Provided refresh token is no longer valid.")
                    if not retry:
                        raise
                    invalidate_refresh_token = True
                else:
                    self.logger.debug("Token has been successfully generated")
        if invalidate_refresh_token:
            return await self.token(retry=False)
        return self._token_data.token


async def extract_login_data(page: str, form_login_element: str) -> AuthSessionData:
    """Extract the required login data from the auth page.

    :param page: the response from performing a GET against
    v1_const.AFERO_CLIENTS[self._afero_client]['OPENID_URL']
    """
    auth_page = BeautifulSoup(page, features="html.parser")
    login_form = auth_page.find("form", id=form_login_element)
    if login_form is None:
        raise InvalidResponse("Unable to parse login page")
    try:
        login_url: str = login_form.attrs["action"]
    except KeyError as err:
        raise InvalidResponse("Unable to extract login url") from err
    parsed_url = urlparse(login_url)
    login_data = parse_qs(parsed_url.query)
    try:
        return AuthSessionData(
            login_data["session_code"][0],
            login_data["execution"][0],
            login_data["tab_id"][0],
        )
    except (KeyError, IndexError) as err:
        raise InvalidResponse("Unable to parse login url") from err


def extract_login_codes(data: AuthSessionData, client: str) -> dict:
    return {
        "session_code": data.session_code,
        "execution": data.execution,
        "client_id": v1_const.AFERO_CLIENTS[client]["AUTH_DEFAULT_CLIENT_ID"],
        "tab_id": data.tab_id,
    }


def get_kc_error(page: str) -> str:
    """Extract the error message from the otp page."""
    auth_page = BeautifulSoup(page, features="html.parser")
    error_div = auth_page.find("span", class_="kc-feedback-text")
    if error_div is None:
        return "Unknown error"
    return error_div.text.strip()
