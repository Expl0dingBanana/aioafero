import datetime
import json
import logging
import os
import pathlib
import time
from urllib.parse import urlencode

import aiohttp
import pytest
import pytest_asyncio

from aioafero.v1 import auth, v1_const

current_path = pathlib.Path(__file__).parent.resolve()


@pytest.fixture(scope="function")
def hs_auth():
    return auth.AferoAuth("username", "password")


@pytest_asyncio.fixture(scope="function")
async def aio_sess() -> aiohttp.ClientSession:
    yield aiohttp.ClientSession()


async def build_url(base_url: str, qs: dict[str, str]) -> str:
    return f"{base_url}?{urlencode(qs)}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "time_offset,is_expired",
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
    if time_offset:
        hs_auth._token_data = auth.token_data(
            "token", None, None, time.time() + time_offset
        )
    assert await hs_auth.is_expired == is_expired


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "page_filename,err_msg,expected",
    [
        # Valid
        (
            "auth_webapp_login.html",
            None,
            auth.auth_sess_data("url_sess_code", "url_exec_code", "url_tab_id"),
        ),
        # page is missing expected id
        (
            "auth_webapp_login_missing.html",
            "Unable to parse login page",
            None,
        ),
        # form field is missing expected attribute
        (
            "auth_webapp_login_bad_format.html",
            "Unable to extract login url",
            None,
        ),
        # URL missing expected elements
        (
            "auth_webapp_login_bad_qs.html",
            "Unable to parse login url",
            None,
        ),
    ],
)
async def test_extract_login_data(page_filename, err_msg, expected):
    with open(os.path.join(current_path, "data", page_filename), "r") as f:
        page_data = f.read()
    if expected:
        assert await auth.extract_login_data(page_data) == expected
    else:
        with pytest.raises(auth.InvalidResponse, match=err_msg):
            await auth.extract_login_data(page_data)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "page_filename, gc_exp, redirect, response, expected_err",
    [
        # Invalid status code
        (None, None, False, {"status": 403}, auth.InvalidResponse),
        # Valid auth passed to generate_code
        (
            "auth_webapp_login.html",
            ("url_sess_code", "url_exec_code", "url_tab_id"),
            False,
            {"status": 200},
            None,
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
        with open(os.path.join(current_path, "data", page_filename), "r") as f:
            response["body"] = f.read()
    challenge = await hs_auth.generate_challenge_data()
    generate_code = mocker.patch.object(hs_auth, "generate_code")
    parse_code = mocker.patch.object(auth.AferoAuth, "parse_code")
    params: dict[str, str] = {
        "response_type": "code",
        "client_id": v1_const.AFERO_CLIENTS["hubspace"]["DEFAULT_CLIENT_ID"],
        "redirect_uri": "hubspace-app%3A%2F%2Floginredirect",
        "code_challenge": challenge.challenge,
        "code_challenge_method": "S256",
        "scope": "openid offline_access",
    }
    url = await build_url(v1_const.AFERO_CLIENTS["hubspace"]["OPENID_URL"], params)
    mock_aioresponse.get(url, **response)
    if not expected_err:
        await hs_auth.webapp_login(challenge, aio_sess)
        if redirect:
            generate_code.asset_not_called()
            parse_code.assert_called_once()
        else:
            exp = list(gc_exp)
            exp.append(aio_sess)
            generate_code.assert_called_once_with(*exp)
            parse_code.assert_not_called()
    else:
        with pytest.raises(expected_err):
            await hs_auth.webapp_login(challenge, aio_sess)
        generate_code.assert_not_called()


@pytest.mark.asyncio
async def test_generate_challenge_data():
    pass


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "session_code, execution, tab_id, response, expected_err, expected",
    [
        # Invalid response
        (
            "sess_code",
            "execution",
            "tab_id",
            {"status": 200},
            auth.InvalidAuth,
            None,
        ),
        # Invalid Location
        (
            "sess_code",
            "execution",
            "tab_id",
            {"status": 302, "headers": {"location": "nope"}},
            auth.InvalidResponse,
            None,
        ),
        # Valid location
        (
            "sess_code",
            "execution",
            "tab_id",
            {"status": 302, "headers": {"location": "https://cool.beans?code=beans"}},
            None,
            "beans",
        ),
    ],
)
async def test_generate_code(
    session_code,
    execution,
    tab_id,
    response,
    expected_err,
    expected,
    hs_auth,
    aioresponses,
    aio_sess,
):
    params = {
        "session_code": session_code,
        "execution": execution,
        "client_id": v1_const.AFERO_CLIENTS["hubspace"]["DEFAULT_CLIENT_ID"],
        "tab_id": tab_id,
    }
    url = await build_url(v1_const.AFERO_CLIENTS["hubspace"]["CODE_URL"], params)
    aioresponses.post(url, **response)
    if not expected_err:
        assert (
            await hs_auth.generate_code(session_code, execution, tab_id, aio_sess)
            == expected
        )
    else:
        with pytest.raises(expected_err):
            await hs_auth.generate_code(session_code, execution, tab_id, aio_sess)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "secure_mode,code,response,expected,expected_messages, err",
    [
        # Invalid refresh token
        (True, "code", {"status": 403}, None, None, aiohttp.ClientError),
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
                    }
                ),
            },
            "refresh_beans",
            [
                "data: {'grant_type': 'authorization_code', 'code': 'th***ns'",
                (
                    "JSON response: {'id_token': 'co***ns', 'refresh_token': "
                    "'re***ns', 'access_token': 'ac***ns'}"
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
    aio_sess,
    caplog,
):
    caplog.set_level(logging.DEBUG)
    auth.add_secret("those-are-some-cool-beans")
    if not secure_mode:
        hs_auth.secret_logger = auth.passthrough
    hs_auth._token_data = None
    challenge = await hs_auth.generate_challenge_data()
    aioresponses.post(v1_const.AFERO_CLIENTS["hubspace"]["TOKEN_URL"], **response)
    if expected:
        assert (
            expected
            == (
                await hs_auth.generate_refresh_token(
                    aio_sess, code=code, challenge=challenge
                )
            ).refresh_token
        )
    else:
        with pytest.raises(err):
            await hs_auth.generate_refresh_token(
                aio_sess, code=code, challenge=challenge
            )
    aioresponses.assert_called_once()
    call_args = list(aioresponses.requests.values())[0][0]
    assert call_args.kwargs["headers"] == hs_auth._token_headers
    assert call_args.kwargs["data"] == {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": v1_const.AFERO_CLIENTS["hubspace"]["DEFAULT_REDIRECT_URI"],
        "code_verifier": challenge.verifier,
        "client_id": v1_const.AFERO_CLIENTS["hubspace"]["DEFAULT_CLIENT_ID"],
    }
    if expected_messages:
        for expected_message in expected_messages:
            assert expected_message in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "secure_mode,refresh_token,response,expected,expected_message,err",
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
        (True, "code", {"status": 403}, None, None, aiohttp.ClientError),
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
    hs_auth._token_data = auth.token_data(
        None, None, refresh_token, datetime.datetime.now()
    )
    aioresponses.post(v1_const.AFERO_CLIENTS["hubspace"]["TOKEN_URL"], **response)
    if expected:
        assert (
            expected == (await hs_auth.generate_refresh_token(aio_sess)).refresh_token
        )
    else:
        with pytest.raises(err):
            await hs_auth.generate_refresh_token(aio_sess)
    aioresponses.assert_called_once()
    call_args = list(aioresponses.requests.values())[0][0]
    assert call_args.kwargs["headers"] == hs_auth._token_headers
    assert call_args.kwargs["data"] == {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": "openid email offline_access profile",
        "client_id": "hubspace_android",
    }
    if expected_message:
        assert expected_message in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "webapp_login_return, generate_refresh_token_return",
    [
        ("cool", "beans"),
    ],
)
async def test_perform_initial_login(
    webapp_login_return, generate_refresh_token_return, hs_auth, aio_sess, mocker
):
    mocker.patch.object(hs_auth, "webapp_login", return_value=webapp_login_return)
    mocker.patch.object(
        hs_auth, "generate_refresh_token", return_value=generate_refresh_token_return
    )
    assert (
        await hs_auth.perform_initial_login(aio_sess) == generate_refresh_token_return
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "hide_secrets, refresh_token",
    [
        (True, None),
        (False, "yes"),
    ],
)
async def test_AferoAuth_init(hide_secrets, refresh_token, mocker):
    test_auth = auth.AferoAuth(
        "username", "password", hide_secrets=hide_secrets, refresh_token=refresh_token
    )
    if hide_secrets:
        assert test_auth.secret_logger == auth.LogRedactorMessage
    else:
        assert test_auth.secret_logger == auth.passthrough
    if refresh_token:
        assert test_auth._token_data == auth.token_data(
            None, None, refresh_token, mocker.ANY
        )
    else:
        assert test_auth._token_data is None


def bad_refresh_token(*args, **kwargs):
    yield auth.InvalidAuth()
    yield auth.token_data(
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
    "token_data, results_perform_initial_login, results_generate_refresh_token,expected,messages",
    [
        # Perform full login
        (
            None,
            auth.token_data(
                "token",
                "access_token",
                "refresh_token",
                datetime.datetime.now().timestamp() + 120,
            ),
            None,
            "token",
            ["Refresh token not present. Generating a new refresh token"],
        ),
        # Previously logged in but expired
        (
            None,
            auth.token_data(
                "token",
                "access_token",
                "refresh_token",
                datetime.datetime.now().timestamp() - 120,
            ),
            auth.token_data(
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
        # Invalid refresh token
        (
            None,
            auth.token_data(
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
                "Refresh token not present. Generating a new refresh token",
            ],
        ),
        # Invalid refresh token and bad login
        (
            None,
            auth.token_data(
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
                "Refresh token not present. Generating a new refresh token",
            ],
        ),
    ],
)
async def test_token(
    token_data,
    results_perform_initial_login,
    results_generate_refresh_token,
    expected,
    messages,
    caplog,
    mocker,
):
    caplog.set_level(logging.DEBUG)
    test_auth = auth.AferoAuth("username", "password")
    test_auth._token_data = token_data
    sess = mocker.Mock()
    mocker.patch.object(
        test_auth,
        "perform_initial_login",
        mocker.AsyncMock(return_value=results_perform_initial_login),
    )
    if isinstance(results_generate_refresh_token, auth.token_data):
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
        assert await test_auth.token(sess) == expected
        assert test_auth.refresh_token == "refresh_token"
    else:
        with pytest.raises(auth.InvalidAuth):
            await test_auth.token(sess)
    for message in messages:
        assert message in caplog.text


def test_set_token_data(hs_auth):
    data = auth.token_data(
        "token",
        "access_token",
        "refresh_token",
        datetime.datetime.now().timestamp() + 120,
    )
    hs_auth.set_token_data(data)
    assert hs_auth._token_data == data
