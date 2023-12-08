import re
from getpass import getpass
from typing import Tuple

from fractal.matrix.exceptions import InvalidMatrixIdException


def prompt_matrix_password(matrix_id: str) -> str:
    """
    Prompts for Matrix password.

    Args:
        matrix_id: Matrix ID to prompt for

    TODO: This should instead direct to a homeserver login page.
    """
    print(f"Login with Matrix ID ({matrix_id}) to continue")
    try:
        password = getpass(f"{matrix_id}'s password: ")
        return password
    except (KeyboardInterrupt, EOFError):
        # newline after ^C
        print()
        exit(1)


def parse_matrix_id(matrix_id: str) -> Tuple[str, str]:
    """Parse local part and homeserver from MatrixID"""
    pattern = re.compile(r"^@([^:]+):([^:]+)$")
    match = pattern.match(matrix_id)
    if not match:
        raise InvalidMatrixIdException(f"{matrix_id} is not a valid Matrix ID.")
    user_localpart = match.group(1)
    homeserver = match.group(2)
    return (user_localpart, homeserver)
