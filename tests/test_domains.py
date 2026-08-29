import pytest

from lumaguard.domains import normalize_domain, unique_domains


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://www.Example.com/path?q=1", "example.com"),
        ("example.com:443", "example.com"),
        ("sub.example.co.uk", "sub.example.co.uk"),
    ],
)
def test_normalize_domain(value, expected):
    assert normalize_domain(value) == expected


@pytest.mark.parametrize("value", ["localhost", "not a domain", "192.0.2.1", "https://bad_domain.test"])
def test_reject_invalid_domains(value):
    with pytest.raises(ValueError):
        normalize_domain(value)


def test_unique_domains_is_stable_and_deduplicated():
    assert unique_domains(["Example.com", "www.example.com", "other.test"]) == ["example.com", "other.test"]

