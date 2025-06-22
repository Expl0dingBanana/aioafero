__all__ = ["AferoAuth", "passthrough", "token_data"]

import asyncio
import base64
import datetime
import hashlib
import logging
import os
import re
from collections import namedtuple
from contextlib import contextmanager
from typing import Final, Optional
from urllib.parse import parse_qs, urlparse

import aiohttp
from aiohttp import ClientSession, ContentTypeError
from bs4 import BeautifulSoup
from securelogging import LogRedactorMessage, add_secret, remove_secret

from ..errors import InvalidAuth, InvalidResponse
from . import v1_const

logger = logging.getLogger(__name__)

TOKEN_TIMEOUT: Final[int] = 118
STATUS_CODE: Final[str] = "Status Code: %s"

auth_challenge = namedtuple("AuthChallenge", ["challenge", "verifier"])
token_data = namedtuple(
    "TokenData", ["token", "access_token", "refresh_token", "expiration"]
)
auth_sess_data = namedtuple("AuthSessionData", ["session_code", "execution", "tab_id"])


@contextmanager
def passthrough():
    yield


class AferoAuth:
    """Authentication against the Afero IoT API

    This class follows the Afero IoT authentication workflow and utilizes
    refresh tokens.
    """

    def __init__(
        self,
        username,
        password,
        hide_secrets: bool = True,
        refresh_token: Optional[str] = None,
        afero_client: Optional[str] = "hubspace",
    ):
        self.logger = logging.getLogger(f"{__package__}[{username}]")
        if hide_secrets:
            self.secret_logger = LogRedactorMessage
        else:
            self.secret_logger = passthrough
        self._hide_secrets: bool = hide_secrets
        self._async_lock: asyncio.Lock = asyncio.Lock()
        self._username: str = username
        self._password: str = password
        self._token_data: Optional[token_data] = None
        if refresh_token:
            add_secret(refresh_token)
            self._token_data = token_data(
                None, None, refresh_token, datetime.datetime.now().timestamp()
            )
        self._afero_client: str = afero_client
        self._token_headers: dict[str, str] = {
            "Content-Type": "application/x-www-form-urlencoded",
            "user-agent": v1_const.AFERO_CLIENTS[self._afero_client][
                "DEFAULT_USERAGENT"
            ],
            "host": v1_const.AFERO_CLIENTS[self._afero_client]["OPENID_HOST"],
        }

    @property
    async def is_expired(self) -> bool:
        """Determine if the token is expired"""
        if not self._token_data:
            return True
        return datetime.datetime.now().timestamp() >= self._token_data.expiration

    @property
    def refresh_token(self) -> str | None:
        return self._token_data.refresh_token

    def set_token_data(self, data: token_data) -> None:
        self._token_data = data

    async def webapp_login(
        self, challenge: auth_challenge, client: ClientSession
    ) -> str:
        """Perform login to the webapp for a code

        Login to the webapp and generate a code used for generating tokens.

        :param challenge: Challenge data for connection and approving
        :param client: async client for making requests

        :return: Code used for generating a refresh token
        """
        code_params: dict[str, str] = {
            "response_type": "code",
            "client_id": v1_const.AFERO_CLIENTS[self._afero_client][
                "DEFAULT_CLIENT_ID"
            ],
            "redirect_uri": v1_const.AFERO_CLIENTS[self._afero_client][
                "DEFAULT_REDIRECT_URI"
            ],
            "code_challenge": challenge.challenge,
            "code_challenge_method": "S256",
            "scope": "openid offline_access",
        }
        self.logger.debug(
            "URL: %s\n\tparams: %s",
            v1_const.AFERO_CLIENTS[self._afero_client]["OPENID_URL"],
            code_params,
        )
        async with client.get(
            v1_const.AFERO_CLIENTS[self._afero_client]["OPENID_URL"],
            params=code_params,
            allow_redirects=False,
        ) as response:
            if response.status == 200:
                contents = await response.text()
                login_data = await extract_login_data(contents)
                self.logger.debug(
                    (
                        "WebApp Login:"
                        "\n\tSession Code: %s"
                        "\n\tExecution: %s"
                        "\n\tTab ID:%s"
                    ),
                    login_data.session_code,
                    login_data.execution,
                    login_data.tab_id,
                )
                return await self.generate_code(
                    login_data.session_code,
                    login_data.execution,
                    login_data.tab_id,
                    client,
                )
            elif response.status == 302:
                self.logger.debug("Hubspace returned an active session")
                return await AferoAuth.parse_code(response)
            else:
                raise InvalidResponse("Unable to query login page")

    @staticmethod
    async def generate_challenge_data() -> auth_challenge:
        code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode("utf-8")
        code_verifier = re.sub("[^a-zA-Z0-9]+", "", code_verifier)
        code_challenge = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge).decode("utf-8")
        code_challenge = code_challenge.replace("=", "")
        chal = auth_challenge(code_challenge, code_verifier)
        logger.debug("Challenge information: %s", chal)
        return chal

    async def generate_code(
        self, session_code: str, execution: str, tab_id: str, client: ClientSession
    ) -> str:
        """Finalize login to Afero IoT page

        :param session_code: Session code during form interaction
        :param execution: Session code during form interaction
        :param tab_id: Session code during form interaction
        :param client: async client for making request

        :return: code for generating tokens
        """
        self.logger.debug("Generating code")
        params = {
            "session_code": session_code,
            "execution": execution,
            "client_id": v1_const.AFERO_CLIENTS[self._afero_client][
                "DEFAULT_CLIENT_ID"
            ],
            "tab_id": tab_id,
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "user-agent": v1_const.AFERO_CLIENTS[self._afero_client][
                "DEFAULT_USERAGENT"
            ],
        }
        auth_data = {
            "username": self._username,
            "password": self._password,
            "credentialId": "",
        }
        self.logger.debug(
            "URL: %s\n\tparams: %s\n\theaders: %s",
            v1_const.AFERO_CLIENTS[self._afero_client]["CODE_URL"],
            params,
            headers,
        )
        async with client.post(
            v1_const.AFERO_CLIENTS[self._afero_client]["CODE_URL"],
            params=params,
            data=auth_data,
            headers=headers,
            allow_redirects=False,
        ) as response:
            self.logger.debug(STATUS_CODE, response.status)
            if response.status != 302:
                raise InvalidAuth(
                    "Unable to authenticate with the supplied username / password"
                )
            return await AferoAuth.parse_code(response)

    @staticmethod
    async def parse_code(response: aiohttp.ClientResponse) -> str:
        """Parses the code for generating tokens"""
        try:
            parsed_url = urlparse(response.headers["location"])
            code = parse_qs(parsed_url.query)["code"][0]
            logger.debug("Location: %s", response.headers.get("location"))
            logger.debug("Code: %s", code)
        except KeyError:
            raise InvalidResponse(
                f"Unable to process the result from {response.url}: {response.status}"
            )
        return code

    async def generate_refresh_token(
        self,
        client: ClientSession,
        challenge: auth_challenge | None = None,
        code: str | None = None,
    ) -> token_data:
        """Generate a refresh token

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
                    "DEFAULT_REDIRECT_URI"
                ],
                "code_verifier": challenge.verifier,
                "client_id": v1_const.AFERO_CLIENTS[self._afero_client][
                    "DEFAULT_CLIENT_ID"
                ],
            }
        else:
            data = {
                "grant_type": "refresh_token",
                "refresh_token": self._token_data.refresh_token,
                "scope": "openid email offline_access profile",
                "client_id": v1_const.AFERO_CLIENTS[self._afero_client][
                    "DEFAULT_CLIENT_ID"
                ],
            }
        with self.secret_logger():
            self.logger.debug(
                "URL: %s\n\tdata: %s\n\theaders: %s",
                v1_const.AFERO_CLIENTS[self._afero_client]["TOKEN_URL"],
                data,
                self._token_headers,
            )
        async with client.post(
            v1_const.AFERO_CLIENTS[self._afero_client]["TOKEN_URL"],
            headers=self._token_headers,
            data=data,
        ) as response:
            self.logger.debug(STATUS_CODE, response.status)
            try:
                resp_json = await response.json()
            except (ValueError, ContentTypeError):
                raise InvalidResponse("Unexpected data returned during token refresh")
            if response.status != 200:
                if resp_json and resp_json.get("error") == "invalid_grant":
                    raise InvalidAuth()
                response.raise_for_status()
            try:
                refresh_token = resp_json["refresh_token"]
                access_token = resp_json["access_token"]
                id_token = resp_json["id_token"]
            except KeyError:
                raise InvalidResponse("Unable to extract refresh token")
            add_secret(refresh_token)
            add_secret(access_token)
            add_secret(id_token)
            with self.secret_logger():
                self.logger.debug("JSON response: %s", resp_json)
            return token_data(
                id_token,
                access_token,
                refresh_token,
                datetime.datetime.now().timestamp() + TOKEN_TIMEOUT,
            )

    async def perform_initial_login(self, client: ClientSession) -> token_data:
        """Login to generate a refresh token

        :param client: async client for making request

        :return: Refresh token for the auth
        """
        challenge = await AferoAuth.generate_challenge_data()
        code: str = await self.webapp_login(challenge, client)
        self.logger.debug("Successfully generated an auth code")
        refresh_token = await self.generate_refresh_token(
            client, code=code, challenge=challenge
        )
        self.logger.debug("Successfully generated a refresh token")
        return refresh_token

    async def token(self, client: ClientSession, retry: bool = True) -> str:
        invalidate_refresh_token = False
        async with self._async_lock:
            if not self._token_data:
                self.logger.debug(
                    "Refresh token not present. Generating a new refresh token"
                )
                self._token_data = await self.perform_initial_login(client)
            if await self.is_expired:
                self.logger.debug("Token has not been generated or is expired")
                try:
                    new_data = await self.generate_refresh_token(client)
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
            return await self.token(client, retry=False)
        return self._token_data.token


async def extract_login_data(page: str) -> auth_sess_data:
    """Extract the required login data from the auth page

    :param page: the response from performing a GET against
    v1_const.AFERO_CLIENTS[self._afero_client]['OPENID_URL']
    """
    auth_page = BeautifulSoup(page, features="html.parser")
    login_form = auth_page.find("form", id="kc-form-login")
    if login_form is None:
        raise InvalidResponse("Unable to parse login page")
    try:
        login_url: str = login_form.attrs["action"]
    except KeyError:
        raise InvalidResponse("Unable to extract login url")
    parsed_url = urlparse(login_url)
    login_data = parse_qs(parsed_url.query)
    try:
        return auth_sess_data(
            login_data["session_code"][0],
            login_data["execution"][0],
            login_data["tab_id"][0],
        )
    except (KeyError, IndexError) as err:
        raise InvalidResponse("Unable to parse login url") from err
