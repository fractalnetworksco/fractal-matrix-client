from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fractal.matrix.async_client import FractalAsyncClient
from fractal.matrix.exceptions import InvalidMatrixIdException
from nio import (
    RoomGetStateEventError,
    RoomGetStateEventResponse,
    RoomInviteError,
    RoomInviteResponse,
    RoomPutStateError,
    RoomPutStateResponse,
)


async def test_invite_if_not_admin():
    sample_user_id = "@sample_user:sample_domain"
    sample_room_id = "sample_id"
    client = FractalAsyncClient()
    with pytest.raises(Exception) as e:
        await client.invite(user_id=sample_user_id, room_id=sample_room_id, admin=False)
    assert "FIXME: Only admin invites are supported for now." in str(e.value)


async def test_invite_all_lower_case_failed():
    sample_user_id = "@SaMplE_uSer:sample_domain"
    sample_room_id = "sample_id"
    client = FractalAsyncClient()
    with pytest.raises(Exception) as e:
        await client.invite(user_id=sample_user_id, room_id=sample_room_id, admin=True)
    assert "Matrix ids must be lowercase." in str(e.value)


async def test_invite_send_invite():
    sample_user_id = "@sample_user:sample_domain"
    sample_room_id = "sample_id"
    sample_event_id = "event_id"
    sample_state_key = "state_key"
    client = FractalAsyncClient()
    client.room_invite = AsyncMock(return_value=RoomInviteResponse())
    content = {"users": {}}
    client.room_get_state_event = AsyncMock(
        return_value=RoomGetStateEventResponse(
            content=content,
            event_type=sample_event_id,
            state_key=sample_state_key,
            room_id=sample_room_id,
        )
    )
    client.room_put_state = AsyncMock(
        return_value=RoomPutStateResponse(event_id=sample_event_id, room_id=sample_room_id)
    )
    with patch("fractal.matrix.async_client.logger", new=MagicMock()) as mock_logger:
        await client.invite(user_id=sample_user_id, room_id=sample_room_id, admin=True)
        mock_logger.info.assert_called_once_with(
            f"Sending invite to {sample_room_id} to user ({sample_user_id})"
        )


async def test_invite_raise_exception_for_userID():
    sample_user_id = "sample_user:sample_domain"
    sample_room_id = "sample_id"
    client = FractalAsyncClient()
    with pytest.raises(InvalidMatrixIdException) as e:
        await client.invite(user_id=sample_user_id, room_id=sample_room_id, admin=True)
    assert f"{sample_user_id} is not a valid Matrix ID." in str(e.value)


async def test_invite_get_power_levels():
    sample_user_id = "@sample_user:sample_domain"
    sample_room_id = "sample_id"
    sample_event_id = "event_id"
    sample_state_key = "state_key"
    client = FractalAsyncClient()
    client.room_invite = AsyncMock(return_value=RoomInviteResponse())
    content = {"users": {}}
    client.room_get_state_event = AsyncMock(
        return_value=RoomGetStateEventResponse(
            content=content,
            event_type=sample_event_id,
            state_key=sample_state_key,
            room_id=sample_room_id,
        )
    )
    client.room_put_state = AsyncMock(
        return_value=RoomPutStateResponse(event_id=sample_event_id, room_id=sample_room_id)
    )
    await client.invite(user_id=sample_user_id, room_id=sample_room_id, admin=True)
    client.room_get_state_event.assert_called_once_with(sample_room_id, "m.room.power_levels")


async def test_invite_room_get_state_event_error_when_has_message():
    sample_user_id = "@sample_user:sample_domain"
    sample_room_id = "sample_id"
    client = FractalAsyncClient()
    client.room_invite = AsyncMock()
    client.room_get_state_event = AsyncMock(return_value=RoomGetStateEventError("Error message"))
    with pytest.raises(Exception) as e:
        await client.invite(user_id=sample_user_id, room_id=sample_room_id, admin=True)
    assert "Error message" in str(e.value)


# @pytest.mark.skip("Having trouble reaching the else condition and testing the exception")
async def test_invite_room_get_state_event_error_when_no_message():
    sample_user_id = "@sample_user:sample_domain"
    sample_room_id = "sample_id"
    sample_event_id = "event_id"
    sample_state_key = "state_key"
    client = FractalAsyncClient()
    client.room_invite = AsyncMock()
    client.room_get_state_event = AsyncMock(
        return_value=RoomGetStateEventResponse(
            content={"errcode": "sample_error"},
            event_type=sample_event_id,
            state_key=sample_state_key,
            room_id=sample_room_id,
        )
    )
    with pytest.raises(Exception) as e:
        await client.invite(user_id=sample_user_id, room_id=sample_room_id, admin=True)
    assert "error" in str(e.value)


async def test_invite_room_put_state_error():
    sample_user_id = "@sample_user:sample_domain"
    sample_room_id = "sample_id"
    sample_event_id = "event_id"
    sample_state_key = "state_key"
    client = FractalAsyncClient()
    client.room_invite = AsyncMock(return_value=RoomInviteResponse())
    content = {"users": {}}
    client.room_get_state_event = AsyncMock(
        return_value=RoomGetStateEventResponse(
            content=content,
            event_type=sample_event_id,
            state_key=sample_state_key,
            room_id=sample_room_id,
        )
    )
    client.room_put_state = AsyncMock(return_value=RoomPutStateError("Room Put State Error"))
    with pytest.raises(Exception) as e:
        await client.invite(user_id=sample_user_id, room_id=sample_room_id, admin=True)
    assert "Room Put State Error" in str(e.value)
