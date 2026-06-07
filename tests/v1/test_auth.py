import datetime
import json
import logging
import pathlib
import time
from urllib.parse import urlencode

import aiohttp
import pytest

from aioafero.v1 import auth, v1_const

current_path = pathlib.Path(__file__).parent.resolve()


@pytest.fixture
def hs_auth(aio_sess):
    return auth.AferoAuth(aio_sess, "username", "mock-refresh-token")


@pytest.fixture
def hs_auth_login(aio_sess):
    return auth.AferoAuth.for_login(aio_sess, "username", "password")


async def build_url(base_url: str, qs: dict[str, str]) -> str:
    return f"{base_url}?{urlencode(qs)}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("time_offset", "is_expired"),
    [
        # No token
        (None, True),
        # Expired token
        (-5, True),
        # Non-Expired token
        (5, False),
    ],
)
async def test_is_expired(time_offset, is_expired, hs_auth):
    if time_offset is None:
        hs_auth._token_data = None
    else:
        hs_auth._token_data = auth.TokenData(
            "token", None, None, time.time() + time_offset
        )
    assert await hs_auth.is_expired == is_expired


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("page_filename", "form_id", "err_msg", "expected"),
    [
        # Valid
        (
            "auth_webapp_login.html",
            "kc-form-login",
            None,
            auth.AuthSessionData("url_sess_code", "url_exec_code", "url_tab_id"),
        ),
        # page is missing expected id
        (
            "auth_webapp_login_missing.html",
            "kc-form-login",
            "Unable to parse login page",
            None,
        ),
        # form field is missing expected attribute
        (
            "auth_webapp_login_bad_format.html",
            "kc-form-login",
            "Unable to extract login url",
            None,
        ),
        # URL missing expected elements
        (
            "auth_webapp_login_bad_qs.html",
            "kc-form-login",
            "Unable to parse login url",
            None,
        ),
    ],
)
async def test_extract_login_data(page_filename, form_id, err_msg, expected):
    page_data = (current_path / "data" / page_filename).read_text()
    if expected:
        assert await auth.extract_login_data(page_data, form_id) == expected
    else:
        with pytest.raises(auth.InvalidResponse, match=err_msg):
            await auth.extract_login_data(page_data, form_id)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("page_filename", "gc_exp", "redirect", "response", "expected_err"),
    [
        # Invalid status code
        (None, None, False, {"status": 403}, auth.InvalidResponse),
        # Valid auth passed to generate_code
        (
            "auth_webapp_login.html",
            auth.AuthSessionData("url_sess_code", "url_exec_code", "url_tab_id"),
            False,
            {"status": 200},
            None,
        ),
        # Random error
        (
            "auth_webapp_login.html",
            auth.AuthSessionData("url_sess_code", "url_exec_code", "url_tab_id"),
            False,
            {"status": 400},
            auth.InvalidResponse,
        ),
        # Active session returned
        (
            "auth_webapp_login.html",
            None,
            True,
            {
                "status": 302,
                "headers": {
                    "location": (
                        "hubspace-app://loginredirect"
                        "?session_state=sess-state"
                        "&iss=https%3A%2F%2Faccounts.hubspaceconnect.com"
                        "%2Fauth%2Frealms%2Fthd&code=code"
                    )
                },
            },
            None,
        ),
    ],
)
async def test_webapp_login(
    page_filename,
    gc_exp,
    redirect,
    response,
    expected_err,
    hs_auth,
    mock_aioresponse,
    aio_sess,
    mocker,
):
    if page_filename:
        response["body"] = (current_path / "data" / page_filename).read_text()
    challenge = await hs_auth.generate_challenge_data()
    generate_code = mocker.patch.object(hs_auth, "generate_code")
    parse_code = mocker.patch.object(auth.AferoAuth, "parse_code")
    params: dict[str, str] = {
        "response_type": "code",
        "client_id": v1_const.AFERO_CLIENTS["hubspace"]["AUTH_DEFAULT_CLIENT_ID"],
        "redirect_uri": "hubspace-app%3A%2F%2Floginredirect",
        "code_challenge": challenge.challenge,
        "code_challenge_method": "S256",
        "scope": "openid offline_access",
    }
    url = hs_auth.generate_auth_url(v1_const.AFERO_GENERICS["AUTH_OPENID_ENDPOINT"])
    url = await build_url(url, params)
    mock_aioresponse.get(url, **response)
    if not expected_err:
        await hs_auth.webapp_login(challenge)
        if redirect:
            generate_code.asset_not_called()
            parse_code.assert_called_once()
        else:
            generate_code.assert_called_once_with(gc_exp, challenge)
            parse_code.assert_not_called()
    else:
        with pytest.raises(expected_err):
            await hs_auth.webapp_login(challenge)
        generate_code.assert_not_called()


@pytest.mark.asyncio
async def test_generate_challenge_data(caplog):
    caplog.set_level(logging.DEBUG)
    challenge = await auth.AferoAuth.generate_challenge_data()
    assert challenge.challenge
    assert challenge.verifier
    assert "Challenge information:" in caplog.text
    assert challenge.verifier not in caplog.text


def test_token_expiration_from_api():
    now = 1_000_000.0
    assert auth._token_expiration({"expires_in": 120}, now=now) == now + 118


def test_token_expiration_fallback():
    now = 1_000_000.0
    assert auth._token_expiration({}, now=now) == now + auth.DEFAULT_TOKEN_TIMEOUT


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("auth_data", "response", "expected_err", "expected"),
    [
        # Invalid response
        (
            auth.AuthSessionData("sess_code", "execution", "tab_id"),
            {"status": 200},
            auth.InvalidAuth,
            None,
        ),
        # Invalid Location
        (
            auth.AuthSessionData("sess_code", "execution", "tab_id"),
            {"status": 302, "headers": {"location": "nope"}},
            auth.InvalidResponse,
            None,
        ),
        # Valid location
        (
            auth.AuthSessionData("sess_code", "execution", "tab_id"),
            {"status": 302, "headers": {"location": "https://cool.beans?code=beans"}},
            None,
            "beans",
        ),
        # OTP login required
        (
            auth.AuthSessionData("sess_code", "execution", "tab_id"),
            {
                "status": 200,
                "headers": {"location": "https://cool.beans?code=beans"},
                "body": '<form id="kc-otp-login-form" class="form-horizontal" action="https://accounts.hubspaceconnect.com/auth/realms/thd/login-actions/authenticate?session_code=session_code&amp;execution=execution&amp;client_id=hubspace_android&amp;tab_id=tab_id" method="post" onsubmit="return submitForm()">',
            },
            auth.OTPRequired,
            None,
        ),
    ],
)
async def test_generate_code(
    auth_data,
    response,
    expected_err,
    expected,
    hs_auth_login,
    aioresponses,
    aio_sess,
):
    hs_auth = hs_auth_login
    params = {
        "session_code": auth_data.session_code,
        "execution": auth_data.execution,
        "client_id": v1_const.AFERO_CLIENTS["hubspace"]["AUTH_DEFAULT_CLIENT_ID"],
        "tab_id": auth_data.tab_id,
    }
    url = hs_auth.generate_auth_url(v1_const.AFERO_GENERICS["AUTH_CODE_ENDPOINT"])
    url = await build_url(url, params)
    aioresponses.post(url, **response)
    if not expected_err:
        assert await hs_auth.generate_code(auth_data, None) == expected
    else:
        with pytest.raises(expected_err):
            await hs_auth.generate_code(auth_data, None)
    assert hs_auth._password is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("secure_mode", "code", "response", "expected", "expected_messages", "err"),
    [
        # Invalid refresh token
        (
            True,
            "code",
            {"status": 403},
            None,
            None,
            aiohttp.web_exceptions.HTTPForbidden,
        ),
        # Incorrect format
        (
            True,
            "code",
            {"status": 200, "body": json.dumps({"refresh_token2": "cool_beans"})},
            None,
            None,
            auth.InvalidResponse,
        ),
        # Weird stuff returned
        (
            True,
            "code",
            {"status": 400, "body": "{"},
            None,
            None,
            auth.InvalidResponse,
        ),
        # Valid refresh token
        (
            True,
            "those-are-some-cool-beans",
            {
                "status": 200,
                "body": json.dumps(
                    {
                        "id_token": "cool_beans",
                        "refresh_token": "refresh_beans",
                        "access_token": "access_token_beans",
                        "expires_in": 120,
                    }
                ),
            },
            "refresh_beans",
            [
                "data: {'grant_type': 'authorization_code', 'code': 'th***ns'",
                (
                    "JSON response: {'id_token': 'co***ns', 'refresh_token': "
                    "'re***ns', 'access_token': 'ac***ns', 'expires_in': 120}"
                ),
            ],
            None,
        ),
        # Valid refresh token - inseucre
        (
            False,
            "those-are-some-cool-beans",
            {
                "status": 200,
                "body": json.dumps(
                    {
                        "id_token": "cool_beans",
                        "refresh_token": "refresh_beans",
                        "access_token": "access_token_beans",
                    }
                ),
            },
            "refresh_beans",
            [
                (
                    "JSON response: {'id_token': 'cool_beans', 'refresh_token': "
                    "'refresh_beans', 'access_token': 'access_token_beans'}"
                ),
            ],
            None,
        ),
    ],
)
async def test_generate_refresh_token(
    secure_mode,
    code,
    response,
    expected,
    expected_messages,
    err,
    hs_auth,
    aioresponses,
    caplog,
):
    caplog.set_level(logging.DEBUG)
    auth.add_secret("those-are-some-cool-beans")
    if not secure_mode:
        hs_auth.secret_logger = auth.passthrough
    hs_auth._token_data = None
    challenge = await hs_auth.generate_challenge_data()
    url = hs_auth.generate_auth_url(v1_const.AFERO_GENERICS["AUTH_TOKEN_ENDPOINT"])
    aioresponses.post(url, **response)
    if expected:
        assert (
            expected
            == (
                await hs_auth.generate_refresh_token(code=code, challenge=challenge)
            ).refresh_token
        )
    else:
        with pytest.raises(err):
            await hs_auth.generate_refresh_token(code=code, challenge=challenge)
    aioresponses.assert_called_once()
    call_args = list(aioresponses.requests.values())[0][0]
    # Add in the user-agent that is generated from the bridge
    hs_auth._token_headers["user-agent"] = v1_const.AFERO_GENERICS[
        "DEFAULT_USERAGENT"
    ].safe_substitute(client_name="aioafero")
    assert call_args.kwargs["headers"] == hs_auth._token_headers
    assert call_args.kwargs["data"] == {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": v1_const.AFERO_CLIENTS["hubspace"]["AUTH_DEFAULT_REDIRECT_URI"],
        "code_verifier": challenge.verifier,
        "client_id": v1_const.AFERO_CLIENTS["hubspace"]["AUTH_DEFAULT_CLIENT_ID"],
    }
    if expected_messages:
        for expected_message in expected_messages:
            assert expected_message in caplog.text


@pytest.mark.asyncio
async def test_generate_refresh_token_clears_login_secrets_on_failure(
    hs_auth, aioresponses, mocker
):
    challenge = await hs_auth.generate_challenge_data()
    code = "auth-code"
    auth.add_secret(code)
    remove_secret = mocker.patch("aioafero.v1.auth.remove_secret")
    url = hs_auth.generate_auth_url(v1_const.AFERO_GENERICS["AUTH_TOKEN_ENDPOINT"])
    aioresponses.post(url, status=400)
    with pytest.raises(auth.InvalidResponse):
        await hs_auth.generate_refresh_token(code=code, challenge=challenge)
    remove_secret.assert_any_call(code)
    remove_secret.assert_any_call(challenge.verifier)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("secure_mode", "refresh_token", "response", "expected", "expected_message", "err"),
    [
        # Refresh token invalidated due to password change
        (
            True,
            "code",
            {"status": 400, "body": json.dumps({"error": "invalid_grant"})},
            None,
            None,
            auth.InvalidAuth,
        ),
        # Invalid status
        (
            True,
            "code",
            {"status": 403},
            None,
            None,
            aiohttp.web_exceptions.HTTPForbidden,
        ),
        # Unexpected code returned
        (True, "code", {"status": 400}, None, None, auth.InvalidResponse),
        # bad response
        (
            True,
            "code",
            {"status": 200, "body": json.dumps({"id_token2": "cool_beans"})},
            None,
            None,
            auth.InvalidResponse,
        ),
        # valid response
        (
            True,
            "code",
            {
                "status": 200,
                "body": json.dumps(
                    {
                        "id_token": "cool_beans",
                        "refresh_token": "refresh_beans",
                        "access_token": "access_token_beans",
                    }
                ),
            },
            "refresh_beans",
            (
                "JSON response: {'id_token': 'co***ns', "
                "'refresh_token': 're***ns', 'access_token': 'ac***ns'}"
            ),
            None,
        ),
        # valid response insecure
        (
            False,
            "code",
            {
                "status": 200,
                "body": json.dumps(
                    {
                        "id_token": "cool_beans",
                        "refresh_token": "refresh_beans",
                        "access_token": "access_token_beans",
                    }
                ),
            },
            "refresh_beans",
            (
                "JSON response: {'id_token': 'cool_beans', 'refresh_token': "
                "'refresh_beans', 'access_token': 'access_token_beans'}"
            ),
            None,
        ),
    ],
)
async def test_generate_refresh_token_from_refresh(
    secure_mode,
    refresh_token,
    response,
    expected,
    expected_message,
    err,
    hs_auth,
    aioresponses,
    aio_sess,
    caplog,
):
    caplog.set_level(logging.DEBUG)
    if not secure_mode:
        hs_auth.secret_logger = auth.passthrough
    hs_auth._token_data = auth.TokenData(
        None, None, refresh_token, datetime.datetime.now()
    )
    url = hs_auth.generate_auth_url(v1_const.AFERO_GENERICS["AUTH_TOKEN_ENDPOINT"])
    aioresponses.post(url, **response)
    if expected:
        assert expected == (await hs_auth.generate_refresh_token()).refresh_token
    else:
        with pytest.raises(err):
            await hs_auth.generate_refresh_token()
    aioresponses.assert_called_once()
    call_args = list(aioresponses.requests.values())[0][0]
    # Add in the user-agent that is generated from the bridge
    hs_auth._token_headers["user-agent"] = v1_const.AFERO_GENERICS[
        "DEFAULT_USERAGENT"
    ].safe_substitute(client_name="aioafero")
    assert call_args.kwargs["headers"] == hs_auth._token_headers
    assert call_args.kwargs["data"] == {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": "openid email offline_access profile",
        "client_id": v1_const.AFERO_CLIENTS["hubspace"]["AUTH_DEFAULT_CLIENT_ID"],
    }
    if expected_message:
        assert expected_message in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("webapp_login_return", "generate_refresh_token_return"),
    [
        ("cool", "beans"),
    ],
)
async def test_perform_initial_login(
    webapp_login_return, generate_refresh_token_return, hs_auth_login, aio_sess, mocker
):
    hs_auth = hs_auth_login
    mocker.patch.object(hs_auth, "webapp_login", return_value=webapp_login_return)
    mocker.patch.object(
        hs_auth, "generate_refresh_token", return_value=generate_refresh_token_return
    )
    assert await hs_auth.perform_initial_login() == generate_refresh_token_return


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("hide_secrets", "token"),
    [
        (True, None),
        (False, "yes"),
    ],
)
async def test_AferoAuth_init(hide_secrets, token, mocker, aio_sess):
    test_auth = auth.AferoAuth(
        aio_sess,
        "username",
        "refresh_token",
        token=token,
        hide_secrets=hide_secrets,
    )
    if hide_secrets:
        assert test_auth.secret_logger == auth.LogRedactorMessage
    else:
        assert test_auth.secret_logger == auth.passthrough
    if token:
        assert test_auth._token_data.token == token
        assert test_auth._token_data.refresh_token == "refresh_token"
        assert await test_auth.is_expired is True
    else:
        assert test_auth._token_data == auth.TokenData(
            None, None, "refresh_token", mocker.ANY
        )


@pytest.mark.asyncio
async def test_AferoAuth_for_login(aio_sess):
    test_auth = auth.AferoAuth.for_login(aio_sess, "username", "password")
    assert test_auth._password == "password"
    assert test_auth._token_data is None


@pytest.mark.asyncio
async def test_for_login_requires_session():
    with pytest.raises(ValueError, match="session is required"):
        auth.AferoAuth.for_login(None, "username", "password")


@pytest.mark.asyncio
async def test_refresh_token_requires_session():
    with pytest.raises(ValueError, match="session is required"):
        auth.AferoAuth(None, "username", "refresh_token")


@pytest.mark.asyncio
async def test_token_expiration_honored(aio_sess):
    expires = time.time() + 3600
    test_auth = auth.AferoAuth(
        aio_sess,
        "username",
        "refresh_token",
        token="bearer",
        token_expiration=expires,
    )
    assert test_auth._token_data.expiration == expires
    assert await test_auth.is_expired is False


@pytest.mark.asyncio
async def test_login_clears_password_on_failure(aio_sess, mocker):
    test_auth = auth.AferoAuth.for_login(aio_sess, "username", "password")
    remove_secret = mocker.patch("aioafero.v1.auth.remove_secret")
    mocker.patch.object(
        auth.AferoAuth,
        "generate_challenge_data",
        return_value=auth.AuthChallenge("challenge", "verifier"),
    )
    mocker.patch.object(
        test_auth,
        "webapp_login",
        side_effect=auth.InvalidResponse("fail"),
    )
    with pytest.raises(auth.InvalidResponse):
        await test_auth.login()
    assert test_auth._password is None
    remove_secret.assert_has_calls(
        [mocker.call("password"), mocker.call("verifier")],
        any_order=True,
    )


def test_remove_secrets_not_in_skips_shared_values(mocker):
    remove_secret = mocker.patch("aioafero.v1.auth.remove_secret")
    old = auth.TokenData("old-bearer", "old-access", "shared-refresh", 0)
    new = auth.TokenData("new-bearer", "new-access", "shared-refresh", 100)
    auth._remove_secrets_not_in(old, new)
    remove_secret.assert_has_calls(
        [mocker.call("old-bearer"), mocker.call("old-access")],
        any_order=True,
    )


@pytest.mark.asyncio
async def test_for_login_does_not_register_empty_refresh_secret(mocker, aio_sess):
    add_secret = mocker.patch("aioafero.v1.auth.add_secret")
    auth.AferoAuth.for_login(aio_sess, "username", "password")
    assert "" not in [call.args[0] for call in add_secret.call_args_list]


def bad_refresh_token(*args, **kwargs):
    yield auth.InvalidAuth()
    yield auth.TokenData(
        "token",
        "access_token",
        "refresh_token",
        datetime.datetime.now().timestamp() + 120,
    )


def bad_refresh_token_invalid(*args, **kwargs):
    yield auth.InvalidAuth()
    yield auth.InvalidAuth()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("token_data", "results_generate_refresh_token", "expected", "messages"),
    [
        # No token data available
        (
            None,
            None,
            None,
            [],
        ),
        # Previously logged in but expired
        (
            auth.TokenData(
                "token",
                "access_token",
                "refresh_token",
                datetime.datetime.now().timestamp() - 120,
            ),
            auth.TokenData(
                "token",
                "access_token",
                "refresh_token",
                datetime.datetime.now().timestamp() + 120,
            ),
            "token",
            [
                "Token has not been generated or is expired",
            ],
        ),
        # Refresh-only token data (no bearer yet)
        (
            auth.TokenData(
                None,
                None,
                "refresh_token",
                datetime.datetime.now().timestamp() - 120,
            ),
            auth.TokenData(
                "token",
                "access_token",
                "refresh_token",
                datetime.datetime.now().timestamp() + 120,
            ),
            "token",
            [
                "Token has not been generated or is expired",
            ],
        ),
        # Invalid refresh token retried once then succeeds
        (
            auth.TokenData(
                "token",
                "access_token",
                "refresh_token",
                datetime.datetime.now().timestamp() - 120,
            ),
            bad_refresh_token,
            "token",
            [
                "Token has not been generated or is expired",
                "Provided refresh token is no longer valid.",
            ],
        ),
        # Invalid refresh token on both attempts
        (
            auth.TokenData(
                "token",
                "access_token",
                "refresh_token",
                datetime.datetime.now().timestamp() - 120,
            ),
            bad_refresh_token_invalid,
            None,
            [
                "Token has not been generated or is expired",
                "Provided refresh token is no longer valid.",
            ],
        ),
    ],
)
async def test_token(
    token_data,
    results_generate_refresh_token,
    expected,
    messages,
    caplog,
    mocker,
    aio_sess,
):
    caplog.set_level(logging.DEBUG)
    test_auth = auth.AferoAuth(aio_sess, "username", "refresh_token")
    test_auth._token_data = token_data
    if isinstance(results_generate_refresh_token, auth.TokenData):
        mocker.patch.object(
            test_auth,
            "generate_refresh_token",
            mocker.AsyncMock(return_value=results_generate_refresh_token),
        )
    elif results_generate_refresh_token:
        mocker.patch.object(
            test_auth,
            "generate_refresh_token",
            side_effect=results_generate_refresh_token(),
        )
    if isinstance(expected, str):
        assert await test_auth.token() == expected
        assert test_auth.refresh_token == "refresh_token"
    else:
        with pytest.raises(auth.InvalidAuth):
            await test_auth.token()
    for message in messages:
        assert message in caplog.text


def test_set_token_data(hs_auth):
    data = auth.TokenData(
        "token",
        "access_token",
        "refresh_token",
        datetime.datetime.now().timestamp() + 120,
    )
    hs_auth.set_token_data(data)
    assert hs_auth._token_data == data


def test_property_refresh_token(aio_sess):
    _auth = auth.AferoAuth.for_login(aio_sess, "username", "password")
    assert _auth.refresh_token is None
    _auth._token_data = auth.TokenData(
        "token",
        "access_token",
        "refresh_token",
        datetime.datetime.now().timestamp() + 120,
    )
    assert _auth.refresh_token == "refresh_token"


@pytest.mark.parametrize(
    ("page_filename", "expected"),
    [
        # Valid OTP error
        ("auth_webapp_login_otp_failed.html", "Invalid access code."),
        # Can't find OTP error
        ("auth_webapp_login.html", "Unknown error"),
    ],
)
def test_get_kc_error(page_filename, expected):
    page_data = (current_path / "data" / page_filename).read_text()
    assert auth.get_kc_error(page_data) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "page_filename",
        "response",
        "expected_token_data",
        "expected_error",
        "expected_error_match",
    ),
    [
        # Valid OTP submission
        (
            None,
            {
                "status": 302,
                "headers": {
                    "location": (
                        "hubspace-app://loginredirect"
                        "?session_state=sess-state"
                        "&iss=https%3A%2F%2Faccounts.hubspaceconnect.com"
                        "%2Fauth%2Frealms%2Fthd&code=code"
                    )
                },
            },
            auth.TokenData(
                token="id_token",
                access_token="access_token",
                refresh_token="refresh_token",
                expiration=0,
            ),
            None,
            None,
        ),
        # Invalid OTP provided
        (
            "auth_webapp_login_otp_failed.html",
            {
                "status": 200,
            },
            None,
            auth.InvalidOTP,
            "Invalid access code.",
        ),
    ],
)
async def test_submit_otp(
    page_filename,
    response,
    expected_token_data,
    expected_error,
    expected_error_match,
    mock_aioresponse,
    aio_sess,
    hs_auth_login,
    mocker,
):
    challenge = await hs_auth_login.generate_challenge_data()
    auth_sess_data = auth.AuthSessionData(
        "url_sess_code", "url_exec_code", "url_tab_id"
    )
    url_params = auth.extract_login_codes(auth_sess_data, hs_auth_login._afero_client)
    hs_auth_login._otp_data = {
        "params": url_params,
        "headers": {},
        "challenge": challenge,
    }
    if page_filename:
        response["body"] = (current_path / "data" / page_filename).read_text()
    url = hs_auth_login.generate_auth_url(v1_const.AFERO_GENERICS["AUTH_CODE_ENDPOINT"])
    url = await build_url(url, url_params)
    mock_aioresponse.post(url, **response)
    if expected_token_data:
        token_url = hs_auth_login.generate_auth_url(
            v1_const.AFERO_GENERICS["AUTH_TOKEN_ENDPOINT"]
        )
        mock_aioresponse.post(
            token_url,
            status=200,
            body=json.dumps(
                {
                    "refresh_token": "refresh_token",
                    "access_token": "access_token",
                    "id_token": "id_token",
                }
            ),
        )
        assert await hs_auth_login.submit_otp("123456") == auth.TokenData(
            token=expected_token_data.token,
            access_token=expected_token_data.access_token,
            refresh_token=expected_token_data.refresh_token,
            expiration=mocker.ANY,
        )
    else:
        with pytest.raises(expected_error, match=expected_error_match):
            await hs_auth_login.submit_otp("123456")


@pytest.mark.asyncio
async def test_perform_otp_login(mock_aioresponse, aio_sess, hs_auth_login, mocker):
    challenge = await hs_auth_login.generate_challenge_data()
    auth_sess_data = auth.AuthSessionData(
        "url_sess_code", "url_exec_code", "url_tab_id"
    )
    url_params = auth.extract_login_codes(auth_sess_data, hs_auth_login._afero_client)
    hs_auth_login._otp_data = {
        "params": url_params,
        "headers": {},
        "challenge": challenge,
    }
    url = hs_auth_login.generate_auth_url(v1_const.AFERO_GENERICS["AUTH_CODE_ENDPOINT"])
    url = await build_url(url, url_params)
    # Successful OTP POST
    otp_post_response = {
        "status": 302,
        "headers": {
            "location": (
                "hubspace-app://loginredirect"
                "?session_state=sess-state"
                "&iss=https%3A%2F%2Faccounts.hubspaceconnect.com"
                "%2Fauth%2Frealms%2Fthd&code=code"
            )
        },
    }
    mock_aioresponse.post(url, **otp_post_response)
    # Successful authorization_code generation
    url = hs_auth_login.generate_auth_url(
        v1_const.AFERO_GENERICS["AUTH_TOKEN_ENDPOINT"]
    )
    resp_data = {
        "refresh_token": "refresh_token",
        "access_token": "access_token",
        "id_token": "id_token",
    }
    mock_aioresponse.post(url, status=200, body=json.dumps(resp_data))
    assert await hs_auth_login.perform_otp_login("123456") == auth.TokenData(
        token="id_token",
        access_token="access_token",
        refresh_token="refresh_token",
        expiration=mocker.ANY,
    )


@pytest.mark.asyncio
async def test_perform_otp_login_not_ready(hs_auth_login):
    hs_auth_login._otp_data = {}
    with pytest.raises(auth.OTPRequired):
        await hs_auth_login.perform_otp_login("123456")
