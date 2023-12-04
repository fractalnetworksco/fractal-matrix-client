import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fractal.matrix import (
    MatrixClient,
    UnknownDiscoveryInfoException,
    WellKnownNotFoundException,
    get_homeserver_for_matrix_id,
)
from nio import AsyncClient, DiscoveryInfoResponse
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


@patch("fractal.async_client.AsyncClientConfig")
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
    AsyncClientConfigMock.assert_called_with(max_timeouts=max_timeouts)


async def test_decorator_async_decorator():
    """
    Ensure the decorator passes an instance of AsyncClient as the last argument
    """

    @MatrixClient()
    async def test(foo, bar, client):
        assert isinstance(client, AsyncClient)

    await test("foo", "bar")  # type: ignore


@patch("fractal.FractalAsyncClient")
async def test_get_matrix_homeserver_url_for_matrix_id(AsyncClientMock):
    client_instance = AsyncClientMock.return_value
    client_instance.close = AsyncMock()
    client_instance.discovery_info = AsyncMock(spec=DiscoveryInfoResponse)

    homeserver_url = await get_homeserver_for_matrix_id("@user:localhost")
    assert homeserver_url == "http://localhost:8008"

    homeserver_url = "https://matrix-client.matrix.org"
    response = DiscoveryInfoResponse(homeserver_url=homeserver_url)
    response.transport_response = MagicMock(spec=TransportResponse)
    response.transport_response.ok = False
    response.transport_response.reason = "Not Found"
    client_instance.discovery_info.return_value = response

    with pytest.raises(WellKnownNotFoundException) as e:
        await get_homeserver_for_matrix_id("@user:matrix.org")
    assert ".well-known" in str(e.value)
    client_instance.discovery_info.assert_awaited()

    response.transport_response.reason = "Another reason"
    with pytest.raises(UnknownDiscoveryInfoException) as e:
        await get_homeserver_for_matrix_id("@user:matrix.org")
    assert "Another reason" in str(e.value)

    response.transport_response.ok = True
    assert homeserver_url == await get_homeserver_for_matrix_id("@user:matrix.org")
