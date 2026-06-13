"""Regression: add_triple ids must not collide on rapid invalidate -> re-add,
even when the wall clock returns the same instant for both adds."""
import datetime as _dt

import mempalace.knowledge_graph as kgmod


class _FrozenDateTime:
    @staticmethod
    def now():
        return _dt.datetime(2026, 1, 1, 0, 0, 0)


def test_rapid_invalidate_re_add_no_id_collision(kg, monkeypatch):
    # Freeze the clock so both add_triple calls hash an identical timestamp.
    monkeypatch.setattr(kgmod, "datetime", _FrozenDateTime)
    t1 = kg.add_triple("Alice", "works_at", "Acme")
    kg.invalidate("Alice", "works_at", "Acme", ended="2025-01-01")
    t2 = kg.add_triple("Alice", "works_at", "Acme")  # same frozen instant
    assert t1 != t2  # must be a distinct id, no IntegrityError
