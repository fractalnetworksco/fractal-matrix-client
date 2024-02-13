import os
from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fractal.matrix import MatrixClient, get_homeserver_for_matrix_id
from fractal.matrix.async_client import FractalAsyncClient
from fractal.matrix.exceptions import (
    GetLatestSyncTokenError,
    UnknownDiscoveryInfoException,
    WellKnownNotFoundException,
)
from nio import (
    AsyncClient,
    DiscoveryInfoError,
    DiscoveryInfoResponse,
    RegisterResponse,
    RoomMessagesError,
    RoomMessagesResponse,
)
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


async def test_decorator_async_decorator_no_home_server_and_no_matrix_id_raises_error():
    environment = deepcopy(os.environ)
    environment.pop("MATRIX_HOMESERVER_URL", None)
    environment.pop("MATRIX_ID", None)
    with patch.dict(os.environ, environment, clear=True):
        with pytest.raises(KeyError) as e:
            async with MatrixClient() as client:
                assert client.homeserver == None


async def test_context_manager_no_home_server():
    environment = deepcopy(os.environ)
    environment.pop("MATRIX_HOMESERVER_URL", None)
    matrix_id = "@user:homeserver.org"
    with patch.dict(os.environ, environment, clear=True):
        with patch(
            "fractal.matrix.async_client.get_homeserver_for_matrix_id",
            new=AsyncMock(return_value=("https://homeserver.org", False)),
        ) as mock_get_homeserver:
            async with MatrixClient(matrix_id=matrix_id) as client:
                assert client.homeserver == "https://homeserver.org"


async def test_context_manager_no_access_token():
    environment = deepcopy(os.environ)
    environment.pop("MATRIX_HOMESERVER_URL", None)
    environment.pop("MATRIX_ACCESS_TOKEN")
    matrix_id = "@user:homeserver.org"
    with patch.dict(os.environ, environment, clear=True):
        with patch(
            "fractal.matrix.async_client.get_homeserver_for_matrix_id",
            new=AsyncMock(return_value=("https://homeserver.org", False)),
        ) as mock_get_homeserver:
            async with MatrixClient(matrix_id=matrix_id) as client:
                assert client.access_token == None
                assert client.user == matrix_id


async def test_context_manager_testing_access_token():
    environment = deepcopy(os.environ)
    environment.pop("MATRIX_HOMESERVER_URL", None)
    environment.pop("MATRIX_ACCESS_TOKEN")
    matrix_id = "@user:homeserver.org"
    with patch.dict(os.environ, environment, clear=True):
        with patch(
            "fractal.matrix.async_client.get_homeserver_for_matrix_id",
            new=AsyncMock(return_value=("https://homeserver.org", False)),
        ) as mock_get_homeserver:
            async with MatrixClient(matrix_id=matrix_id, access_token="test_token") as client:
                assert client.user == ""


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


async def test_get_latest_sync_token_no_room_id():
    client = FractalAsyncClient()
    assert client.room_id == None
    with pytest.raises(GetLatestSyncTokenError) as e:
        await client.get_latest_sync_token()
    assert "No room id provided" in str(e.value)


async def test_get_latest_sync_token_successful_message():
    sample_room_id = "sample_id"
    client = FractalAsyncClient(room_id=sample_room_id)
    mock_response = RoomMessagesResponse(
        room_id=sample_room_id, chunk=[], start="mock_sync_token"
    )
    client.room_messages = AsyncMock(return_value=mock_response)
    sync_token = await client.get_latest_sync_token()
    assert sync_token == "mock_sync_token"


async def test_get_latest_sync_token_message_error():
    sample_room_id = "sample_id"
    client = FractalAsyncClient(room_id=sample_room_id)
    mock_response = RoomMessagesError("Room Message Error")
    client.room_messages = AsyncMock(return_value=mock_response)
    with pytest.raises(GetLatestSyncTokenError) as e:
        await client.get_latest_sync_token()
    assert "Room Message Error" in str(e.value)


async def test_invite_if_not_admin():
    sample_user_id = "sample_user"
    sample_room_id = "sample_id"
    client = FractalAsyncClient()
    with pytest.raises(Exception) as e:
        await client.invite(user_id=sample_user_id, room_id=sample_room_id, admin=False)
    assert "FIXME: Only admin invites are supported for now." in str(e.value)


async def test_invite_all_lower_case_failed():
    sample_user_id = "SaMplE_uSer"
    sample_room_id = "sample_id"
    client = FractalAsyncClient()
    with pytest.raises(Exception) as e:
        await client.invite(user_id=sample_user_id, room_id=sample_room_id, admin=True)
    assert "Matrix ids must be lowercase." in str(e.value)


async def test_invite_send_invite():
    sample_user_id = "sample_user"
    sample_room_id = "sample_id"
    client = FractalAsyncClient()
    # with patch(
    # "fractal.matrix.async_client.FractalAsyncClient.invite", new=AsyncMock()
    # ) as mock_invite:
    with patch("fractal.matrix.async_client.logger", new=AsyncMock()) as mock_logger:
        await client.invite(user_id=sample_user_id, room_id=sample_room_id, admin=True)
    mock_logger.error.assert_called_once()
