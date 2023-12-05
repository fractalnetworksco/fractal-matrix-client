import logging
import os
from typing import Any, Dict, List, Optional, Union

from nio import (
    AsyncClient,
    AsyncClientConfig,
    JoinError,
    MessageDirection,
    RoomGetStateEventError,
    RoomInviteError,
    RoomMessagesError,
    RoomPutStateError,
    RoomSendResponse,
)

from .exceptions import GetLatestSyncTokenError

logger = logging.getLogger(__name__)


class FractalAsyncClient(AsyncClient):
    def __init__(
        self,
        homeserver_url: str = os.environ.get("MATRIX_HOMESERVER_URL", ""),
        access_token: str = os.environ.get("MATRIX_ACCESS_TOKEN", ""),
        room_id: Optional[str] = None,
        max_timeouts: int = 2,
        *args,
        **kwargs,
    ):
        super().__init__(homeserver_url, *args, **kwargs)
        self.config = AsyncClientConfig(max_timeouts=max_timeouts)
        self.access_token = access_token
        self.room_id: Optional[str] = room_id

    async def send_message(
        self,
        room: str,
        message: Union[bytes, str, List[Any], Dict[Any, Any]],
        msgtype: str = "taskiq.task",
        **kwargs,
    ) -> None:
        """
        Send a message to a room.

        Note: Encrypted rooms are not supported for now.

        Args:
            room (str): The room id to send the message to.
            message (bytes | str): The message to send.
            msgtype (str): The message type to send. Defaults to "m.taskiq.task".
        """
        if isinstance(message, bytes):
            message = message.decode("utf-8")

        # msg_body: Dict[str, Any] = {"task": message, **kwargs}
        msg_content = {"msgtype": msgtype, "body": message}
        logger.debug("Sending message: %s to room %s", msg_content, room)
        try:
            response = await self.room_send(room, msgtype, msg_content)
            if not isinstance(response, RoomSendResponse):
                logger.error("Error sending message: %s", response)
            logger.debug("Response from room_send: %s", response)
        except Exception as err:
            logger.error("Error sending message: %s", err)

    async def get_latest_sync_token(self, room_id: Optional[str] = None) -> str:
        """
        Returns the latest sync token for a room in constant time,
        using /sync with an empty filter takes longer as the room grows.

        Args:
            room_id (Optional[str]): The room id to get the sync token for.
                                     If not provided, defaults to the client's room.

        Returns:
            str: The latest sync token for the room.
        """
        room_id = room_id or self.room_id

        if not room_id:
            raise GetLatestSyncTokenError("No room id provided")

        res = await self.room_messages(
            room_id, start="", limit=1, direction=MessageDirection.back
        )
        if not isinstance(res, RoomMessagesError):
            return res.start
        raise GetLatestSyncTokenError(self.room_id)

    async def invite(self, user_id: str, room_id: str) -> None:
        """
        Invites a user to a room and sets their power level to 100.
        FIXME: setting power level to 100 is required for Fractal Database.

        Args:
            user_id (str): The user id to invite to the room.
            room_id (str): The room id to invite the user to.
        """
        logger.info(f"Sending invite to {room_id} to user ({user_id})")
        res = await self.room_invite(room_id, user_id)
        if isinstance(res, RoomInviteError):
            raise Exception(res.message)

        # get power levels
        res = await self.room_get_state_event(room_id, "m.room.power_levels")
        if isinstance(res, RoomGetStateEventError):
            raise Exception(res.message)

        # set user as admin
        power_levels = res.content
        power_levels["users"][user_id] = 100
        res = await self.room_put_state(room_id, "m.room.power_levels", power_levels)
        if isinstance(res, RoomPutStateError):
            raise Exception(res.message)

        return None

    async def join_room(self, room_id: str) -> None:
        """
        Joins a room.

        Args:
            room_id (str): The room id to join.
        """
        logger.info(f"Joining room: {room_id}")
        res = await self.join(room_id)
        if isinstance(res, JoinError):
            raise Exception(res.message)
        return None
