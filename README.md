# Fractal Matrix Client

This project is a thin wrapper around `matrix-nio`. It provides convenience helpers for working with synapse admin and the Matrix API
for Matrix powered projects.

## Example Usage

Context manager example:
```python
from fractal_matrix_client import MatrixClient

# Fractal Matrix Client can automatically discover the Matrix server associated with the given matrix_id if the homesrver is configured properly
async with MatrixClient(matrix_id='@user:matrix.org') as client:
    res = await client.login('password')
    print(res.access_token)

syt_bW8... #access_token
```
