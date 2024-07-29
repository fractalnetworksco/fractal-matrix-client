import logging
import os
from typing import Optional

from fractal.matrix.admin_client import MatrixAdminClient
from fractal.matrix.async_client import (
    FractalAsyncClient,
    MatrixClient,
    get_homeserver_for_matrix_id,
)

logger = logging.getLogger(__file__)
