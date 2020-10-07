import pytest
from iflag import data
from decimal import Decimal


def test_index_from_bytes():
    input = b"\x14.\x00\x00\x80\x1d,\x04"
    assert data.Index.from_bytes(input).value == Decimal("11796.7")


def test_index9_from_bytes():
    input = b"\x14.\x00\x00\x00\x80\x1d,\x04"
    assert data.Index9.from_bytes(input).value == Decimal("11796.7")
