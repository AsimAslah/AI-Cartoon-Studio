import struct

from app.services.render_verifier import verify_mp4, verify_png


def test_png_verification_checks_signature_and_dimensions(tmp_path):
    path = tmp_path / "preview.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + struct.pack(">II", 640, 360))
    assert verify_png(path)


def test_mp4_verification_rejects_tiny_file(tmp_path):
    path = tmp_path / "video.mp4"
    path.write_bytes(b"ftyp")
    assert not verify_mp4(path)
