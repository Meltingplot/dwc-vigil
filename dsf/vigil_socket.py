"""
Vigil Socket — Robust JSON-object framing for DSF UNIX-socket connections.

dsf-python's ``BaseConnection.connect`` reads the server init message with a
single fixed-size ``self.socket.recv(50)``. DSF 3.6 sends a greeting longer
than 50 bytes, so the message is truncated mid-string and ``json.loads`` raises
``JSONDecodeError: Unterminated string``. This module provides a length-agnostic
reader that accumulates bytes until a complete JSON object has arrived, mirroring
the framing logic dsf-python already uses for every other message.
"""

import time


def json_object_end_index(json_string: str) -> int:
    """Return the end index (exclusive) of the first complete JSON object.

    Counts curly braces to find where the first balanced ``{...}`` object ends.
    Returns -1 when no complete object is present yet. Matches the behaviour of
    dsf-python's ``BaseConnection.get_json_object_end_index``: input that does
    not start with ``{`` yields 1, which callers reject via an ``end > 1`` check.
    """
    count = 0
    for index, token in enumerate(json_string):
        if token == "{":
            count += 1
        elif token == "}":
            count -= 1

        if count < 0:  # Unbalanced closing brace — malformed input
            return -1
        if count == 0:  # Balanced: end of the first object (or no object at all)
            return index + 1

    return -1


def read_json_object(recv, timeout: float = 3, buff_size: int = 4096):
    """Read from ``recv`` until a complete JSON object has been buffered.

    ``recv`` is a callable like ``socket.recv`` returning ``bytes`` (or ``str``).
    Returns a tuple of ``(json_string, leftover)`` where ``json_string`` is the
    first complete JSON object and ``leftover`` is any extra buffered data that
    should be prepended to subsequent reads.

    Raises ``TimeoutError`` if no complete object arrives within ``timeout``
    seconds, or ``ConnectionError`` if the peer closes the connection first.
    """
    buffer = ""
    start = time.monotonic()
    while True:
        end = json_object_end_index(buffer)
        if end > 1:
            return buffer[:end], buffer[end:]

        if timeout and (time.monotonic() - start > timeout):
            raise TimeoutError("Timeout while waiting for JSON object")

        chunk = recv(buff_size)
        if not chunk:
            raise ConnectionError(
                "Connection closed before a complete JSON object was received"
            )
        buffer += chunk.decode("utf8") if isinstance(chunk, (bytes, bytearray)) else chunk
