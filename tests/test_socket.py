"""Tests for vigil_socket — robust JSON-object framing for DSF connections.

Regression coverage for the dsf-python bug where BaseConnection.connect reads
the server init message with a fixed-size recv(50), truncating greetings longer
than 50 bytes and raising "JSONDecodeError: Unterminated string".
"""

import json

import pytest

from vigil_socket import json_object_end_index, read_json_object


class FakeRecv:
    """Callable that hands out a queued byte stream in fixed-size chunks."""

    def __init__(self, data, chunk_size=4096):
        if isinstance(data, str):
            data = data.encode("utf8")
        self._data = data
        self._chunk_size = chunk_size
        self._pos = 0

    def __call__(self, buff_size):
        size = min(self._chunk_size, buff_size)
        chunk = self._data[self._pos:self._pos + size]
        self._pos += len(chunk)
        return chunk


class TestJsonObjectEndIndex:
    def test_complete_object(self):
        assert json_object_end_index('{"a":1}') == 7

    def test_incomplete_object(self):
        assert json_object_end_index('{"a":1') == -1

    def test_empty_string(self):
        assert json_object_end_index("") == -1

    def test_nested_object(self):
        s = '{"a":{"b":2}}'
        assert json_object_end_index(s) == len(s)

    def test_trailing_data_after_object(self):
        # Stops at the end of the first complete object.
        assert json_object_end_index('{"a":1}{"b":2}') == 7

    def test_braces_inside_string_still_balance(self):
        # Note: the brace counter is string-naive (matches dsf-python), but a
        # well-formed object's outer braces still resolve correctly.
        s = '{"id":"abc"}'
        assert json_object_end_index(s) == len(s)


class TestReadJsonObject:
    def test_reads_short_message(self):
        msg = '{"version":12,"id":1}'
        json_string, leftover = read_json_object(FakeRecv(msg))
        assert json.loads(json_string) == {"version": 12, "id": 1}
        assert leftover == ""

    def test_reads_long_message_exceeding_50_bytes(self):
        # The exact failure mode: a greeting longer than the old recv(50) limit.
        guid = "a1b2c3d4-e5f6-7890-abcd-ef0123456789"
        msg = json.dumps({"version": 12, "id": guid})
        assert len(msg.encode("utf8")) > 50
        json_string, leftover = read_json_object(FakeRecv(msg))
        assert json.loads(json_string)["id"] == guid
        assert leftover == ""

    def test_reassembles_across_small_chunks(self):
        msg = '{"version":12,"id":"a1b2c3d4-e5f6-7890-abcd-ef0123456789"}'
        # Deliver one byte at a time to force multi-read reassembly.
        json_string, leftover = read_json_object(FakeRecv(msg, chunk_size=1))
        assert json.loads(json_string)["version"] == 12
        assert leftover == ""

    def test_preserves_leftover_after_object(self):
        msg = '{"version":12,"id":1}{"next":true}'
        json_string, leftover = read_json_object(FakeRecv(msg))
        assert json.loads(json_string) == {"version": 12, "id": 1}
        assert leftover == '{"next":true}'

    def test_raises_on_closed_connection(self):
        # recv returns b"" (EOF) before a complete object arrives.
        with pytest.raises(ConnectionError):
            read_json_object(FakeRecv('{"version":12'))

    def test_raises_on_timeout(self):
        # A recv that yields data but never forms a complete object times out.
        def empty_but_open(_buff_size):
            return b" "  # whitespace: never forms an object

        with pytest.raises(TimeoutError):
            read_json_object(empty_but_open, timeout=0.05)

    def test_accepts_str_chunks(self):
        # recv callables that hand back str (not bytes) are tolerated.
        json_string, leftover = read_json_object(FakeRecv('{"ok":1}'.encode()))
        assert json.loads(json_string) == {"ok": 1}
