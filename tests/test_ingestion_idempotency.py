from app.services.ingestion_service import file_sha256


def test_file_sha256_stable(tmp_path):
    p = tmp_path / "sample.txt"
    p.write_bytes(b"same-content")
    assert file_sha256(str(p)) == file_sha256(str(p))
