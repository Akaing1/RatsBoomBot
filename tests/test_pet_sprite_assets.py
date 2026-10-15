import struct
import zlib
from pathlib import Path


def test_witch_cat_is_a_complete_four_frame_png():
    data = (Path(__file__).resolve().parents[1] / "assets/Witch's Cat.png").read_bytes()
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    offset = 8
    compressed = bytearray()
    chunks = []
    while offset < len(data):
        length = struct.unpack('>I', data[offset:offset + 4])[0]
        kind = data[offset + 4:offset + 8]
        payload = data[offset + 8:offset + 8 + length]
        checksum = struct.unpack('>I', data[offset + 8 + length:offset + 12 + length])[0]
        assert zlib.crc32(kind + payload) & 0xffffffff == checksum
        chunks.append(kind)
        if kind == b'IHDR':
            assert struct.unpack('>IIBBBBB', payload) == (448, 149, 8, 6, 0, 0, 0)
        if kind == b'IDAT':
            compressed.extend(payload)
        offset += length + 12
    assert chunks[0] == b'IHDR' and chunks[-1] == b'IEND'
    assert len(zlib.decompress(compressed)) == 149 * (1 + 448 * 4)
