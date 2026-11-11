"""Stage 2.1 테스트 추가 T1 — 2.0 mutant #2 (fc58c0e src/collectors/dart.py:56 is_valid_zip, and → or)
명세: is_valid_zip docstring "실제로 열리고 손상이 없는지 확인한다".
"""
import io
import zipfile

from src.collectors.dart import is_valid_zip
from tests.test_dart_collector import make_zip  # 기존 헬퍼 재사용


def test_corrupted_zip_member_is_not_valid():
    data = bytearray(make_zip())
    name = zipfile.ZipFile(io.BytesIO(bytes(data))).namelist()[0]
    data[30 + len(name)] ^= 0xFF  # 첫 항목 데이터의 첫 바이트를 바꾼다 (헤더 'PK'와 목록은 그대로, CRC가 맞지 않게 됨)
    assert data.startswith(b"PK")
    assert not is_valid_zip(bytes(data))


def test_empty_zip_is_not_valid():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w"):
        pass
    assert not is_valid_zip(buf.getvalue())
