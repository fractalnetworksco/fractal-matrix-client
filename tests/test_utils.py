from getpass import getpass
from io import StringIO
from unittest.mock import patch

import pytest
from fractal.matrix import utils
from fractal.matrix.exceptions import InvalidMatrixIdException


@pytest.mark.skip()
async def test_prompt_matrix_password():
    matrix_id = "test_matrix_id"
    expected_password = "test_password"
    utils.prompt_matrix_password = AsyncMock(return_value=expected_password)


async def test_prompt_matrix_password_keyboard_interrupt():
    matrix_id = "test_matrix_id"
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        with patch("builtins.getpass", side_effect=KeyboardInterrupt):
            utils.prompt_matrix_password(matrix_id)
    assert pytest_wrapped_e.type == SystemExit
