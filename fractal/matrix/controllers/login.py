import os
from sys import exit
from typing import Optional, Tuple

from asgiref.sync import async_to_sync
from fractal.cli import cli_method
from fractal.matrix import MatrixClient, get_homeserver_for_matrix_id  # move to utils?
from fractal.matrix.utils import prompt_matrix_password, read_user_data, write_user_data
from nio import LoginError


class MatrixLoginError(Exception):
    pass


class LoginController:
    PLUGIN_NAME = "login"

    @cli_method
    def login(self, matrix_id: str):
        """
        Login to a Matrix homeserver.
        ---
        Args:
            matrix_id: Matrix ID of user to login as
        """

        homeserver_url, access_token = async_to_sync(self._login_with_password)(matrix_id)

        # save access token to token file
        write_user_data(
            {"access_token": access_token, "homeserver_url": homeserver_url}, "matrix"
        )

        print(f"Successfully logged in as {matrix_id}")

    login.clicz_aliases = ["login"]

    @cli_method
    def logout(self):
        """
        Logout of Matrix
        ---
        Args:
        """
        try:
            data, path = read_user_data("matrix")
            access_token = data["access_token"]
            homeserver_url = data["homeserver_url"]
        except KeyError:
            raise

        async def _logout():
            async with MatrixClient(homeserver_url, access_token) as client:
                await client.logout()

        os.remove(path)
        print("Successfully logged out. Have a nice day.")

    logout.clicz_aliases = ["logout"]

    async def _login_with_password(
        self, matrix_id: str, password: Optional[str] = None
    ) -> Tuple[str, str]:
        homeserver_url = await get_homeserver_for_matrix_id(matrix_id)
        if not password:
            password = prompt_matrix_password(matrix_id)
        async with MatrixClient(homeserver_url) as client:
            client.user = matrix_id
            res = await client.login(password)
            if isinstance(res, LoginError):
                raise MatrixLoginError(res.message)
        return homeserver_url, res.access_token


Controller = LoginController
