from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fractal.matrix.async_client import FractalAsyncClient
from fractal.matrix.exceptions import GetLatestSyncTokenError
from nio import RoomMessagesError, RoomMessagesResponse


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
