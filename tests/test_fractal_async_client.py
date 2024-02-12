from unittest.mock import AsyncMock, MagicMock, patch

from fractal.matrix.async_client import FractalAsyncClient, RoomSendResponse
from nio import RoomSendError


async def test_send_message_contains_bytes():
    test_fractal_client = FractalAsyncClient()
    with patch(
        "fractal.matrix.async_client.FractalAsyncClient.room_send", new=AsyncMock()
    ) as mock_room_send:
        mock_room_send.return_value = MagicMock(spec=RoomSendResponse)
        room = "test_room"
        test_bytes = b"test_message"
        await test_fractal_client.send_message(room=room, message=test_bytes)
    expected_argument = {"msgtype": "taskiq.task", "body": "test_message"}
    mock_room_send.assert_called_with(room, "taskiq.task", expected_argument)


async def test_send_message_contains_string():
    test_fractal_client = FractalAsyncClient()
    with patch(
        "fractal.matrix.async_client.FractalAsyncClient.room_send", new=AsyncMock()
    ) as mock_room_send:
        mock_room_send.return_value = MagicMock(spec=RoomSendResponse)
        room = "test_room"
        test_string = "test_string"
        await test_fractal_client.send_message(room=room, message=test_string)
    expected_argument = {"msgtype": "taskiq.task", "body": "test_string"}
    mock_room_send.assert_called_with(room, "taskiq.task", expected_argument)


async def test_send_message_contains_list():
    test_fractal_client = FractalAsyncClient()
    with patch(
        "fractal.matrix.async_client.FractalAsyncClient.room_send", new=AsyncMock()
    ) as mock_room_send:
        mock_room_send.return_value = MagicMock(spec=RoomSendResponse)
        room = "test_room"
        test_list = ["testlist"]
        await test_fractal_client.send_message(room=room, message=test_list)
    expected_argument = {"msgtype": "taskiq.task", "body": test_list}
    mock_room_send.assert_called_with(room, "taskiq.task", expected_argument)


async def test_send_message_contains_dictionary():
    test_fractal_client = FractalAsyncClient()
    with patch(
        "fractal.matrix.async_client.FractalAsyncClient.room_send", new=AsyncMock()
    ) as mock_room_send:
        mock_room_send.return_value = MagicMock(spec=RoomSendResponse)
        room = "test_room"
        test_dic = {"val": "1"}
        await test_fractal_client.send_message(room=room, message=test_dic)
    expected_argument = {"msgtype": "taskiq.task", "body": test_dic}
    mock_room_send.assert_called_with(room, "taskiq.task", expected_argument)


async def test_send_message_returns_error():
    test_fractal_client = FractalAsyncClient()
    with patch(
        "fractal.matrix.async_client.FractalAsyncClient.room_send", new=AsyncMock()
    ) as mock_room_send:
        mock_room_send.return_value = RoomSendError(message="Test Error Message")
        with patch("fractal.matrix.async_client.logger") as mock_logger:
            room = "test_room"
            test_dic = {"val": "1"}
            await test_fractal_client.send_message(room=room, message=test_dic)
    mock_logger.error.assert_called_once()


async def test_send_message_raises_exception():
    test_fractal_client = FractalAsyncClient()
    with patch(
        "fractal.matrix.async_client.FractalAsyncClient.room_send", new=AsyncMock()
    ) as mock_room_send:
        mock_room_send.side_effect = Exception()
        with patch("fractal.matrix.async_client.logger") as mock_logger:
            room = "test_room"
            test_dic = {"val": "1"}
            await test_fractal_client.send_message(room=room, message=test_dic)
    mock_logger.error.assert_called_once()
