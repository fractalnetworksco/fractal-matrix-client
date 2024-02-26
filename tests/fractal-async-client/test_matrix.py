import asyncio
import os
from builtins import super
from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from aioresponses import aioresponses
from fractal.matrix import MatrixClient, get_homeserver_for_matrix_id
from fractal.matrix.async_client import FractalAsyncClient, parse_matrix_id
from fractal.matrix.exceptions import (
    UnknownDiscoveryInfoException,
    WellKnownNotFoundException,
)
from nio import (
    AsyncClient,
    DeviceList,
    DeviceOneTimeKeyCount,
    DiscoveryInfoError,
    DiscoveryInfoResponse,
    InviteInfo,
    JoinError,
    PresenceEvent,
    RegisterResponse,
    RoomInfo,
    Rooms,
    SyncError,
    SyncResponse,
    Timeline,
    TransferMonitor,
    UploadError,
    UploadResponse,
)
from nio.http import TransportResponse
from nio.responses import RegisterErrorResponse


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


async def test_get_room_invites_return_inviteinfo():
    client = FractalAsyncClient()
    sample_next_batch = "sample_batch_value"
    rooms = Rooms(
        invite={"invite_room_id": InviteInfo(invite_state=[])},
        join={
            "join_room_id": RoomInfo(
                timeline=Timeline(events=[], limited=True, prev_batch=""),
                state=[],
                ephemeral=[],
                account_data=[],
            )
        },
        leave={
            "leave_room_id": RoomInfo(
                timeline=Timeline(events=[], limited=True, prev_batch=""),
                state=[],
                ephemeral=[],
                account_data=[],
            )
        },
    )
    devicelist = DeviceList(changed=[], left=[])
    devicecount = DeviceOneTimeKeyCount(curve25519=None, signed_curve25519=None)
    client.sync = AsyncMock(
        return_value=SyncResponse(
            next_batch=sample_next_batch,
            rooms=rooms,
            device_key_count=devicecount,
            device_list=devicelist,
            to_device_events=[],
            presence_events=[],
        )
    )
    result = await client.get_room_invites()
    expected_invite_info = {"invite_room_id": InviteInfo(invite_state=[])}
    assert result == expected_invite_info


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


async def test_disable_ratelimiting_post_mock_correct(mock_aiohttp_client):
    client = FractalAsyncClient()
    matrix_id = "sample_matrix_id"
    request_url = f"{client.homeserver}/_synapse/admin/v1/users/{matrix_id}/override_ratelimit"
    mock_aiohttp_client.post(request_url, status=200)
    await client.disable_ratelimiting(matrix_id=matrix_id)
    mock_aiohttp_client.assert_called_with(
        request_url,
        method="POST",
        headers={"Authorization": f"Bearer {client.access_token}"},
        json={},
    )


async def test_disable_ratelimiting_override_error(mock_aiohttp_client):
    client = FractalAsyncClient()
    matrix_id = "sample_matrix_id"
    request_url = f"{client.homeserver}/_synapse/admin/v1/users/{matrix_id}/override_ratelimit"
    status = 500
    mock_aiohttp_client.post(request_url, status=status)
    with pytest.raises(Exception) as e:
        await client.disable_ratelimiting(matrix_id=matrix_id)
    assert f"Failed to override rate limit. Error Response status {status}: " in str(e.value)


async def test_disable_ratelimiting_logger(mock_aiohttp_client):
    client = FractalAsyncClient()
    matrix_id = "sample_matrix_id"
    request_url = f"{client.homeserver}/_synapse/admin/v1/users/{matrix_id}/override_ratelimit"
    mock_aiohttp_client.post(request_url, status=200)
    with patch("fractal.matrix.async_client.logger", new=MagicMock()) as mock_logger:
        await client.disable_ratelimiting(matrix_id=matrix_id)
        mock_logger.info.assert_called_with("Rate limit override successful.")
    mock_aiohttp_client.assert_called_with(
        request_url,
        method="POST",
        headers={"Authorization": f"Bearer {client.access_token}"},
        json={},
    )


async def test_generate_registration_token_post_mock(mock_aiohttp_client):
    client = FractalAsyncClient()
    request_url = f"{client.homeserver}/_synapse/admin/v1/registration_tokens/new"
    token_value = "sample_token"
    expected_payload = {"token": token_value}
    mock_aiohttp_client.post(request_url, status=200, payload=expected_payload)
    token = await client.generate_registration_token()
    assert isinstance(token, str)
    mock_aiohttp_client.assert_called_once_with(
        request_url,
        method="POST",
        headers={"Authorization": f"Bearer {client.access_token}"},
        json={},
    )


async def test_generate_registration_token_override_error(mock_aiohttp_client):
    client = FractalAsyncClient()
    request_url = f"{client.homeserver}/_synapse/admin/v1/registration_tokens/new"
    status = 500
    mock_aiohttp_client.post(request_url, status=status)
    with patch("fractal.matrix.async_client.logger", new=MagicMock()) as mock_logger:
        with pytest.raises(Exception):
            await client.generate_registration_token()
        mock_logger.error.assert_called_with(
            f"Failed to override rate limit. Error Response status {status}: "
        )


async def test_register_with_token_username_created_and_parent_register_with_token_called():
    client = FractalAsyncClient()
    matrix_id = "sample_matrix_id"
    password = "sample_password"
    registration_token = "sample_registration_token"
    with patch(
        "fractal.matrix.async_client.parse_matrix_id",
        new=MagicMock(return_value=["sample_username"]),
    ) as mock_parse:
        with patch(
            "fractal.matrix.async_client.AsyncClient.register_with_token", new=AsyncMock()
        ) as mock_register_with_token:
            client.disable_ratelimiting = AsyncMock()
            await client.register_with_token(
                matrix_id=matrix_id,
                password=password,
                registration_token=registration_token,
            )
            mock_register_with_token.assert_called_once_with(
                "sample_username", password, registration_token, device_name=""
            )


async def test_register_with_token_registererrorresponse():
    client = FractalAsyncClient()
    matrix_id = "sample_matrix_id"
    password = "sample_password"
    registration_token = "sample_registration_token"
    with patch("fractal.matrix.async_client.parse_matrix_id", new=MagicMock()) as mock_parse:
        with patch(
            "fractal.matrix.async_client.AsyncClient.register_with_token",
            new=AsyncMock(return_value=RegisterErrorResponse("Error with response")),
        ) as mock_register_with_token:
            with pytest.raises(Exception) as e:
                await client.register_with_token(
                    matrix_id=matrix_id,
                    password=password,
                    registration_token=registration_token,
                    disable_ratelimiting=True,
                )
            assert "Error with response" in str(e)


async def test_register_with_token_disable_ratelimiting_for_user():
    client = FractalAsyncClient()
    matrix_id = "sample_matrix_id"
    password = "sample_password"
    registration_token = "sample_registration_token"
    with patch("fractal.matrix.async_client.parse_matrix_id", new=MagicMock()) as mock_parse:
        with patch(
            "fractal.matrix.async_client.AsyncClient.register_with_token", new=AsyncMock()
        ) as mock_register_with_token:
            client.disable_ratelimiting = AsyncMock()
            await client.register_with_token(
                matrix_id=matrix_id,
                password=password,
                registration_token=registration_token,
            )
            client.disable_ratelimiting.assert_called_once_with(matrix_id)


async def test_register_with_token_successful_registration_access_token():
    client = FractalAsyncClient()
    matrix_id = "sample_matrix_id"
    password = "sample_password"
    registration_token = "sample_registration_token"
    expected_access_token = "expected_token"
    with patch("fractal.matrix.async_client.parse_matrix_id", new=MagicMock()) as mock_parse:
        with patch(
            "fractal.matrix.async_client.AsyncClient.register_with_token", new=AsyncMock()
        ) as mock_register_with_token:
            mock_register_with_token.return_value = RegisterResponse(
                user_id="sample_user",
                device_id="sample_device",
                access_token=expected_access_token,
            )
            client.disable_ratelimiting = AsyncMock()
            access_token = await client.register_with_token(
                matrix_id=matrix_id,
                password=password,
                registration_token=registration_token,
            )
            assert access_token == expected_access_token


async def test_upload_file_success_no_monitor(mock_async_context_manager):
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
                assert "monitor" not in client.upload.call_args.kwargs


async def test_upload_file_uploaderror(mock_async_context_manager):
    client = FractalAsyncClient()
    failure = (UploadError("Failed to upload file."), {})
    client.upload = AsyncMock(return_value=failure)
    file_path = "sample/file/path"
    # create mock to use fake file path for
    with patch("fractal.matrix.async_client.aiofiles_os.stat", new=AsyncMock()) as mock_file_stat:
        with patch(
            "fractal.matrix.async_client.aiofiles_open",
            new=MagicMock(spec=mock_async_context_manager),
        ) as mock_file_open:
            with patch("fractal.matrix.async_client.logger", new=MagicMock()) as mock_logger:
                with pytest.raises(Exception) as e:
                    await client.upload_file(file_path=file_path)
                assert "Failed to upload file." in str(e.value)


async def test_upload_file_monitor_success(mock_async_context_manager):
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
                trans_monitor = TransferMonitor(total_size=10)
                content_uri = await client.upload_file(file_path=file_path, monitor=trans_monitor)
                assert content_uri == "http://Someurl"
                mock_logger.info.assert_called_once_with(f"Uploading file: {file_path}")
                assert "http://Someurl" in content_uri
                client.upload.assert_called()
                assert client.upload.call_args.kwargs["monitor"].total_size == 10
