import logging
import os
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

import aiohttp
from aiofiles import open as aiofiles_open
from aiofiles import os as aiofiles_os
from fractal.matrix.utils import invite_filter, parse_matrix_id
from nio import (
    AsyncClient,
    AsyncClientConfig,
    DiscoveryInfoError,
    InviteInfo,
    JoinError,
    MessageDirection,
    RoomGetStateEventError,
    RoomInviteError,
    RoomMessagesError,
    RoomPutStateError,
    RoomSendResponse,
    SyncError,
    TransferMonitor,
    UploadError,
)
from nio.responses import RegisterErrorResponse

from .exceptions import (
    GetLatestSyncTokenError,
    UnknownDiscoveryInfoException,
    WellKnownNotFoundException,
)

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
        raise GetLatestSyncTokenError(res.message)

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

        # check if user_id is lowercase
        if not user_id.split("@")[1].islower():
            raise Exception("Matrix ids must be lowercase.")

        logger.info(f"Sending invite to {room_id} to user ({user_id})")
        res = await self.room_invite(room_id, user_id)
        if isinstance(res, RoomInviteError):
            raise Exception(res.message)

        # get power levels
        res = await self.room_get_state_event(room_id, "m.room.power_levels")
        if isinstance(res, RoomGetStateEventError) or "errcode" in res.content:
            if hasattr(res, "message"):
                raise Exception(res.message)
            else:
                raise Exception(res.content["error"])

        # set user as admin
        power_levels = res.content
        power_levels["users"][user_id] = 100
        res = await self.room_put_state(room_id, "m.room.power_levels", power_levels)
        if isinstance(res, RoomPutStateError):
            raise Exception(res.message)

        return None

    async def get_room_invites(self) -> Dict[str, InviteInfo]:
        """
        Returns a dictionary of room ids to invite info.

        TODO: Optionally support a custom invite filter.
        Returns:
            Dict[str, InviteInfo]: A dictionary of room ids to invite info.
        """
        # save previous next batch since sync will replace it.
        prev_next_batch = self.next_batch
        res = await self.sync(since=None, timeout=0, sync_filter=invite_filter())
        print(f"RES IS ============== {res}")
        if isinstance(res, SyncError):
            raise Exception(res.message)
        # restore previous next batch
        self.next_batch = prev_next_batch
        return res.rooms.invite

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

        Returns: Access Token for registered user
        """
        matrix_id = matrix_id.lower()
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

    async def upload_file(
        self,
        file_path: str,
        monitor: Optional[TransferMonitor] = None,
        filename: Optional[str] = None,
    ) -> str:
        """
        Uploads a file to the homeserver.

        Args:
            file_path (str): The path to the file to upload.
            monitor (Optional[TransferMonitor]): A transfer monitor to use. Defaults to None.

        Returns:
            str: The content uri of the uploaded file.
        """
        file_stat = await aiofiles_os.stat(file_path)
        logger.info(f"Uploading file: {file_path}")
        async with aiofiles_open(file_path, "r+b") as f:
            if monitor:
                res, _ = await self.upload(
                    f, filesize=file_stat.st_size, monitor=monitor, filename=filename
                )
            else:
                res, _ = await self.upload(f, filesize=file_stat.st_size, filename=filename)
        if isinstance(res, UploadError):
            raise Exception("Failed to upload file.")
        return res.content_uri


class MatrixClient:
    """
    Helper decorator and context manager for use with code
    that communicates with Matrix via matrix-nio's AsyncClient.

    Args:
        homeserver_url: homeserver URL to set on the nio AsyncClient
            defaults to MATRIX_HOMESERVER_URL environment variable
        access_token: Access token to set on the nio AsyncClient
            defaults to MATRIX_ACCESS_TOKEN environment variable
        max_timeouts: Number of retries for failed requests
            defaults to 2

    @MatrixClient()
    async def example(client: FractalAsyncClient):
        await client.discovery_info()

        or

    async with MatrixClient("http://localhost:8008") as client:
        await client.discovery_info()
    """

    def __init__(
        self,
        homeserver_url: Optional[str] = None,
        access_token: Optional[str] = None,
        matrix_id: Optional[str] = None,
        room_id: Optional[str] = None,
        max_timeouts: int = 0,
    ):
        self.homeserver_url = homeserver_url or os.environ.get("MATRIX_HOMESERVER_URL")
        self.matrix_id = matrix_id or os.environ.get("MATRIX_ID")
        self.access_token = access_token or os.environ.get("MATRIX_ACCESS_TOKEN")
        self.room_id = room_id
        self.max_timeouts = max_timeouts

        if not self.homeserver_url and not self.matrix_id:
            raise KeyError(
                "Environment variable MATRIX_HOMESERVER_URL and MATRIX_ID must be set if\
    not passed explicitly to the MatrixClient context manager decorator."
            )

    def __call__(self, func):
        async def wrapper(*args, **kwargs):
            async with self as client:
                return await func(*args, client, **kwargs)

        return wrapper

    async def __aenter__(self):
        if not self.homeserver_url:
            print(get_homeserver_for_matrix_id)
            self.homeserver_url, _ = await get_homeserver_for_matrix_id(self.matrix_id)
        self.client = FractalAsyncClient(
            self.homeserver_url,
            self.access_token,
            room_id=self.room_id,
            max_timeouts=self.max_timeouts,
        )
        if not self.access_token and self.matrix_id:
            self.client.user = self.matrix_id
        return self.client

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.client.close()


async def get_homeserver_for_matrix_id(matrix_id: str) -> Tuple[str, bool]:
    """Lookup the homeserver url associated with a Matrix ID"""
    # FIXME: just because matrix_id has localhost, doesn't necessarily mean
    # that the homeserver is running on localhost. Could be synapse:8008, etc.
    if "localhost" in matrix_id:
        homeserver_url = os.environ.get("MATRIX_HOMESERVER_URL", "http://localhost:8008")
    else:
        _, homeserver_host = parse_matrix_id(matrix_id)
        homeserver_url = f"https://{homeserver_host}"
    parsed_homeserver = urlparse(homeserver_url).netloc.split(":")[0]
    async with MatrixClient(homeserver_url) as client:
        res = await client.discovery_info()
    if isinstance(res, DiscoveryInfoError):
        if res.transport_response.reason == "Not Found":  # type: ignore
            raise WellKnownNotFoundException()
        raise UnknownDiscoveryInfoException(res.transport_response.reason)  # type: ignore
    if parsed_homeserver in urlparse(res.homeserver_url).netloc:
        return res.homeserver_url, False
    else:
        return res.homeserver_url, True
