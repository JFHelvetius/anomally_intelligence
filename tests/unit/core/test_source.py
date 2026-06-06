"""Tests unitarios de ``aip.core.source``."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from pydantic import ValidationError

from aip.core.source import (
    Actor,
    ActorKind,
    AuthorityLevel,
    Source,
    SourceKind,
)


def _make_source(**overrides: Any) -> Source:
    base: dict[str, Any] = {
        "id": "blue-book-nara",
        "kind": SourceKind.GOVERNMENT_ARCHIVE,
        "name": "Project Blue Book records",
        "authority": AuthorityLevel.SECONDARY,
    }
    base.update(overrides)
    return Source(**base)


# ---------------------------------------------------------------- enum cardinalidad


def test_source_kind_has_thirteen_values_adr_0005() -> None:
    assert len(list(SourceKind)) == 13


def test_authority_level_has_four_values_adr_0005() -> None:
    assert len(list(AuthorityLevel)) == 4


def test_actor_kind_has_four_values_adr_0005() -> None:
    assert len(list(ActorKind)) == 4


# ---------------------------------------------------------------- Source construcción


def test_source_constructs_with_minimal_required_fields() -> None:
    s = _make_source()
    assert s.id == "blue-book-nara"
    assert s.kind == SourceKind.GOVERNMENT_ARCHIVE
    assert s.authority == AuthorityLevel.SECONDARY
    assert s.jurisdiction is None
    assert s.license is None
    assert s.first_seen is None
    assert s.notes is None


def test_source_accepts_full_optional_fields() -> None:
    s = _make_source(
        jurisdiction="US",
        license="public_domain",
        first_seen=dt.date(2026, 6, 4),
        notes="Demo fixture per Pre-F1.C.",
    )
    assert s.jurisdiction == "US"
    assert s.license == "public_domain"
    assert s.first_seen == dt.date(2026, 6, 4)


# ---------------------------------------------------------------- Source.id


def test_source_id_rejects_empty() -> None:
    with pytest.raises(ValidationError):
        _make_source(id="")


def test_source_id_rejects_leading_separator() -> None:
    with pytest.raises(ValidationError, match="must start"):
        _make_source(id="-bad")


def test_source_id_rejects_whitespace() -> None:
    with pytest.raises(ValidationError, match="must start"):
        _make_source(id="blue book")


def test_source_id_accepts_kebab_dot_underscore() -> None:
    for good in ["a", "a-b", "a.b", "a_b", "Source01", "blue-book-nara"]:
        _make_source(id=good)


# ---------------------------------------------------------------- Source.jurisdiction


def test_source_rejects_lowercase_jurisdiction() -> None:
    with pytest.raises(ValidationError):
        _make_source(jurisdiction="us")


def test_source_rejects_three_letter_jurisdiction() -> None:
    with pytest.raises(ValidationError):
        _make_source(jurisdiction="USA")


def test_source_accepts_canonical_iso3166() -> None:
    for code in ["US", "MX", "FR", "JP", "BR"]:
        _make_source(jurisdiction=code)


# ---------------------------------------------------------------- Source — otros


def test_source_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        _make_source(unexpected="x")


def test_source_is_frozen() -> None:
    s = _make_source()
    with pytest.raises(ValidationError):
        s.name = "other"  # type: ignore[misc]


def test_source_rejects_empty_name() -> None:
    with pytest.raises(ValidationError):
        _make_source(name="")


# ---------------------------------------------------------------- Actor


def test_actor_defaults_to_anonymous() -> None:
    a = Actor(id="@anon")
    assert a.kind == ActorKind.ANONYMOUS
    assert a.display_name is None


def test_actor_constructs_full() -> None:
    a = Actor(
        id="@jfhelvetius",
        kind=ActorKind.PERSON,
        display_name="J.F. Helvetius",
    )
    assert a.id == "@jfhelvetius"
    assert a.kind == ActorKind.PERSON
    assert a.display_name == "J.F. Helvetius"


def test_actor_is_frozen() -> None:
    a = Actor(id="@anon")
    with pytest.raises(ValidationError):
        a.kind = ActorKind.PERSON  # type: ignore[misc]


def test_actor_rejects_empty_id() -> None:
    with pytest.raises(ValidationError):
        Actor(id="")


def test_actor_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        Actor(id="x", unknown_field="y")  # type: ignore[call-arg]
