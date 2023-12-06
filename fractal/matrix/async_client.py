import logging
import os
from typing import Any, Dict, List, Optional, Union

import aiohttp
from fractal.matrix import parse_matrix_id
from nio import (
    AsyncClient,
    AsyncClientConfig,
    JoinError,
    MessageDirection,
    RegisterResponse,
    RoomGetStateEventError,
    RoomInviteError,
    RoomMessagesError,
    RoomPutStateError,
    RoomSendResponse,
)
from nio.responses import RegisterErrorResponse

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
        self.config = AsyncClientConfig(max_timeouts=max_timeouts, request_timeout=5)
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

    async def invite(self, user_id: str, room_id: str, admin: bool = False) -> None:
        """
        Invites a user to a room and sets their power level to 100.
        FIXME: setting power level to 100 is required for Fractal Database.

        Args:
            user_id (str): The user id to invite to the room.
            room_id (str): The room id to invite the user to.
            admin (bool): Whether or not to set the user as an admin. FIXME: Only admin invites are supported for now.
        """
        if not admin:
            raise Exception("FIXME: Only admin invites are supported for now.")

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

    async def disable_ratelimiting(self, matrix_id: str) -> None:
        """
        Disables rate limiting for a user.

        Args:
            matrix_id (str): The matrix id to disable rate limiting for.
        """
        url = f"{self.homeserver}/_synapse/admin/v1/users/{matrix_id}/override_ratelimit"
        headers = {"Authorization": f"Bearer {self.access_token}"}

        logger.info(f"Disabling rate limiting for user: {matrix_id}")
        async with aiohttp.ClientSession() as session:
            # TODO: Maybe not completely disable rate limiting?
            # what is optimial for Fractal Database?
            async with session.post(url, json={}, headers=headers) as response:
                if response.ok:
                    logger.info("Rate limit override successful.")
                    return None
                else:
                    txt = await response.text()
                    raise Exception(
                        f"Failed to override rate limit. Error Response status {response.status}: {txt}"
                    )

    async def generate_registration_token(self) -> str:
        """


        Args:
            matrix_id (str): The matrix id to disable rate limiting for.
        """
        url = f"{self.homeserver}/_synapse/admin/v1/registration_tokens/new"
        headers = {"Authorization": f"Bearer {self.access_token}"}

        async with aiohttp.ClientSession() as session:
            # TODO: Maybe not completely disable rate limiting?
            # what is optimial for Fractal Database?
            async with session.post(url, json={}, headers=headers) as response:
                if response.ok:
                    data = await response.json()
                    return data["token"]
                else:
                    txt = await response.text()
                    logger.error(
                        f"Failed to override rate limit. Error Response status {response.status}: {txt}"
                    )
                    raise Exception()

    async def register_with_token(
        self,
        matrix_id: str,
        password: str,
        registration_token: str,
        device_name: str = "",
        disable_ratelimiting: bool = True,
    ) -> str:
        """
        Registers a user with a registration token.

        Args:
            username (str): The username to register.
            password (str): The password to register.
            registration_token (str): The registration token to use.
            device_name (str): The device name to register. Defaults to "".
            disable_ratelimiting (bool): Whether or not to disable rate limiting for the user. Defaults to True.
        """
        username = parse_matrix_id(matrix_id)[0]
        access_token = self.access_token
        res = await super().register_with_token(
            username, password, registration_token, device_name=device_name
        )
        if isinstance(res, RegisterErrorResponse):
            raise Exception(res.message)

        # register will replace the access token that's on the client with the one returned
        # from a successful registration. We want to keep the original access token.
        self.access_token = access_token

        if disable_ratelimiting:
            await self.disable_ratelimiting(matrix_id)

        return res.access_token
