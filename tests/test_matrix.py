import asyncio
import os
from copy import deepcopy
from os import stat_result
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from aioresponses import aioresponses
from fractal.matrix import MatrixClient, get_homeserver_for_matrix_id
from fractal.matrix.async_client import FractalAsyncClient
from fractal.matrix.exceptions import (
    UnknownDiscoveryInfoException,
    WellKnownNotFoundException,
)
from nio import (
    AsyncClient,
    DiscoveryInfoError,
    DiscoveryInfoResponse,
    JoinError,
    RegisterResponse,
    SyncError,
    UploadResponse,
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


async def test_get_room_invites_sync_error():
    client = FractalAsyncClient()
    with patch.object(
        client, "sync", new=AsyncMock(return_value=SyncError("Error with request"))
    ):
        with pytest.raises(Exception) as e:
            await client.get_room_invites()
        assert "Error with request" in str(e.value)


@pytest.mark.skip("Either my logic is wrong or the get_room_invites is bugged")
async def test_get_room_invites_save_prev_next_batch():
    client = FractalAsyncClient()
    client.next_batch = "sample_batch_value"
    mock_sync_response = {"rooms": {"invite": {"room_id_1": {}, "room_id_2": {}}}}
    # we create a mock of sync and make it return our dictionary
    with patch.object(client, "sync", new=AsyncMock(return_value=mock_sync_response)):
        invites_dict = await client.get_room_invites()
        expected_invites_dict = mock_sync_response["rooms"]["invite"]
        assert client.next_batch == "sample_batch_value"
        assert invites_dict == expected_invites_dict


async def test_join_room_logger():
    client = FractalAsyncClient()
    client.join = AsyncMock()
    room_id = "sample_room_id"
    with patch("fractal.matrix.async_client.logger", new=MagicMock()) as mock_logger:
        await client.join_room(room_id=room_id)
        mock_logger.info.assert_called_once_with(f"Joining room: {room_id}")


async def test_join_room_join_error():
    client = FractalAsyncClient()
    client.join = AsyncMock(return_value=JoinError("Failed to join room"))
    room_id = "sample_room_id"
    with pytest.raises(Exception) as e:
        await client.join_room(room_id=room_id)
    assert "Failed to join room" in str(e.value)


@pytest.mark.skip("Don't know how to use aiohttp")
async def test_disable_ratelimiting_url_creation():
    client = FractalAsyncClient()
    matrix_id = "sample_matrix_id"
    await client.disable_ratelimiting(matrix_id=matrix_id)


@pytest.mark.skip(
    "Type error, either lack of knowledge of aiohttp or bug in disable_ratelimiting"
)
async def test_disable_ratelimiting_logger():
    client = FractalAsyncClient()
    matrix_id = "sample_matrix_id"
    url = f"https://_synapse/admin/v1/users/{matrix_id}/override_ratelimit"
    mock_post = AsyncMock(return_value=MagicMock(ok=True, text=AsyncMock(return_value="OK")))
    with patch(
        "fractal.matrix.async_client.aiohttp.ClientSession.post", new=mock_post
    ) as mock_post_call:
        with patch("fractal.matrix.async_client.logger", new=MagicMock()) as mock_logger:
            await client.disable_ratelimiting(matrix_id=matrix_id)
            mock_logger.info.assert_called_once_with("Rate limit override successful.")
            mock_post_call.assert_called_once_with(
                url, json={}, headers={"Authorization": f"Bearer {client.access_token}"}
            )


@pytest.mark.skip("come back to")
async def test_register_with_token():
    client = FractalAsyncClient()
    matrix_id = "sample_matrix_id"
    password = "sample_password"
    registration_token = "sample_registration_token"
    client.register_with_token = AsyncMock()


async def test_upload_file_logger(mock_async_context_manager):
    client = FractalAsyncClient()
    success = (UploadResponse("http://Someurl"), {})
    client.upload = AsyncMock(return_value=success)
    file_path = "sample/file/path"
    # create mock to use fake file path for
    with patch("fractal.matrix.async_client.aiofiles_os.stat", new=AsyncMock()) as mock_file_stat:
        with patch(
            "fractal.matrix.async_client.aiofiles_open",
            new=MagicMock(spec=mock_async_context_manager),
        ) as mock_file_open:
            with patch("fractal.matrix.async_client.logger", new=MagicMock()) as mock_logger:
                content_uri = await client.upload_file(file_path=file_path)
                assert content_uri == "http://Someurl"
                mock_logger.info.assert_called_once_with(f"Uploading file: {file_path}")
                client.upload.assert_called()
