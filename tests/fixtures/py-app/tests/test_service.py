from app.service import verify


def test_verify_rejects_empty():
    assert not verify(None, "")
