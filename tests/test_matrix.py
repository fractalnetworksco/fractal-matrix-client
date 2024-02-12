import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fractal.matrix import MatrixClient, get_homeserver_for_matrix_id
from fractal.matrix.async_client import FractalAsyncClient
from fractal.matrix.exceptions import (
    UnknownDiscoveryInfoException,
    WellKnownNotFoundException,
)
from nio import AsyncClient, DiscoveryInfoError, DiscoveryInfoResponse, RegisterResponse
from nio.http import TransportResponse


async def test_decorator_async_context_manager_raises():
    """
    Ensure
    """
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(KeyError) as e:
            async with MatrixClient() as client:
                pass
        assert "MATRIX_HOMESERVER_URL" in str(e.value)


@patch("fractal.matrix.async_client.AsyncClientConfig")
async def test_decorator_async_context_manager(AsyncClientConfigMock):
    homeserver_url = "http://homeserver"
    access_token = "access_token"
    max_timeouts = 5

    mock_config_instance = AsyncClientConfigMock.return_value

    async with MatrixClient(homeserver_url, access_token, max_timeouts=max_timeouts) as client:
        # make sure our code sets the access token on the instance of AsyncClient
        assert client.access_token == access_token
        client.close = AsyncMock()

    client.close.assert_awaited()

    # make sure max_timeouts was passed properly to AsyncClientConfig
    AsyncClientConfigMock.assert_called_with(max_timeouts=max_timeouts, request_timeout=5)


async def test_decorator_async_decorator():
    """
    Ensure the decorator passes an instance of AsyncClient as the last argument
    """

    @MatrixClient()
    async def test(foo, bar, client):
        assert isinstance(client, AsyncClient)

    await test("foo", "bar")  # type: ignore


@patch("fractal.matrix.async_client.FractalAsyncClient")
async def test_get_matrix_homeserver_url_for_matrix_id(AsyncClientMock):
    client_instance = AsyncClientMock.return_value
    client_instance.close = AsyncMock()
    response = DiscoveryInfoResponse(homeserver_url="http://localhost:8008")
    client_instance.discovery_info = AsyncMock(return_value=response)

    homeserver_url, apex_changed = await get_homeserver_for_matrix_id("@user:localhost")
    assert homeserver_url == "http://localhost:8008"


@patch("fractal.matrix.async_client.FractalAsyncClient")
async def test_get_matrix_homeserver_url_for_matrix_id_not_found(AsyncClientMock):
    client_instance = AsyncClientMock.return_value
    client_instance.close = AsyncMock()
    homeserver_url = "https://matrix-client.matrix.org"
    discovery_info_response = DiscoveryInfoError(message="Test")
    discovery_info_response.transport_response = MagicMock(spec=TransportResponse)
    discovery_info_response.transport_response.ok = False
    discovery_info_response.transport_response.reason = "Not Found"
    response = AsyncMock(return_value=discovery_info_response)
    client_instance.discovery_info = response

    with pytest.raises(WellKnownNotFoundException) as e:
        await get_homeserver_for_matrix_id("@user:matrix.org")
    assert ".well-known" in str(e.value)
    client_instance.discovery_info.assert_awaited()


@patch("fractal.matrix.async_client.FractalAsyncClient")
async def test_get_matrix_homeserver_url_for_matrix_id_unknown_error(AsyncClientMock):
    client_instance = AsyncClientMock.return_value
    client_instance.close = AsyncMock()
    homeserver_url = "https://matrix-client.matrix.org"
    discovery_info_response = DiscoveryInfoError(message="Test")
    discovery_info_response.transport_response = MagicMock(spec=TransportResponse)
    discovery_info_response.transport_response.ok = False
    discovery_info_response.transport_response.reason = "Error"
    response = AsyncMock(return_value=discovery_info_response)
    client_instance.discovery_info = response

    with pytest.raises(UnknownDiscoveryInfoException) as e:
        await get_homeserver_for_matrix_id("@user:matrix.org")
    assert "Error" in str(e.value)
    client_instance.discovery_info.assert_awaited()


@patch("fractal.matrix.async_client.FractalAsyncClient")
async def test_get_matrix_homeserver_url_for_matrix_id_url_apex_changed(AsyncClientMock):
    client_instance = AsyncClientMock.return_value
    client_instance.close = AsyncMock()
    homeserver_url = "https://matrix-client.test.com"
    discovery_info_response = DiscoveryInfoResponse(homeserver_url)
    discovery_info_response.transport_response = MagicMock(spec=TransportResponse)
    discovery_info_response.transport_response.ok = False
    discovery_info_response.transport_response.reason = "Error"
    response = AsyncMock(return_value=discovery_info_response)
    client_instance.discovery_info = response
    server, apexchanged = await get_homeserver_for_matrix_id("@user:matrix.org")
    assert server == homeserver_url
    assert apexchanged == True
    client_instance.discovery_info.assert_awaited()


async def test_register_with_token_works():
    homeserver_url = "http://localhost:8008"
    access_token = "test_token"
    client = FractalAsyncClient(homeserver_url, access_token)
    matrix_id = "@user:localhost"
    password = "pass"
    registration_token = "test_reg"
    register_with_token_response = RegisterResponse(matrix_id, "devid", access_token)
    client.register_with_token = AsyncMock(return_value=register_with_token_response)
    token = await client.register_with_token(matrix_id, password, registration_token)
