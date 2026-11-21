"""510 MiB media transport/storage regression.

This test exercises real bytes, interrupted 4 MiB chunk upload and ffprobe.
It uses a valid synthetic MP4 with a large ISO BMFF 'free' atom, so it is
NOT proof of decoding a high-bitrate 510 MiB real iPhone or PUBG recording.
"""
import struct
from pathlib import Path
from clipra.media import ffprobe, sha256_file
from .conftest import upload_file


def test_510_mib_resumable_upload_and_source_integrity(client,source,tmp_path):
    size=510 * 1024 * 1024
    target=tmp_path/"large_510_mib_source.mp4"
    sample=source.read_bytes()
    padding=size-len(sample)
    assert padding>8 and padding<2**32
    with target.open("wb") as f:
        f.write(sample)
        f.write(struct.pack(">I4s",padding,b"free"))
        f.truncate(size)
    assert target.stat().st_size==size
    assert ffprobe(target)["duration"]>=59
    imported=upload_file(client,target,chunk=4*1024*1024,interrupt=True)
    assert imported["size"]==size
    assert imported["sha256"]==sha256_file(target)
    assert imported["duration"]>=59
    assert target.exists() and target.stat().st_size==size
