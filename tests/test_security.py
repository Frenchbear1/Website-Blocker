from website_blocker.security import create_pin_hash, verify_pin


def test_pin_round_trip_and_wrong_pin():
    salt, digest = create_pin_hash("4827")
    assert verify_pin("4827", salt, digest)
    assert not verify_pin("4828", salt, digest)
    assert "4827" not in digest


def test_each_pin_hash_uses_a_unique_salt():
    first = create_pin_hash("same-pin")
    second = create_pin_hash("same-pin")
    assert first != second

