import chromadb
from mempalace import normalization as norm
from mempalace import wing_registry as wr


def test_classify_agent_claude_code():
    assert norm.classify_agent("claude-code") == ("claude-code", None)


def test_classify_agent_opus_models_all_spellings():
    for a in ("claude-opus-4-7", "claude-opus-4.7", "claude-opus-4-7-1m", "claude-code-opus47"):
        harness, model = norm.classify_agent(a)
        assert harness == "claude-code"
        assert model == "claude-opus-4.7"
    assert norm.classify_agent("claude-opus-4-8") == ("claude-code", "claude-opus-4.8")


def test_classify_agent_fable():
    assert norm.classify_agent("claude-fable-5") == ("claude-code", "claude-fable-5")


def test_classify_agent_bare_claude_is_harness_only():
    # 'claude' / project-nickname agents: harness known-ish, model unknown -> None (never guessed)
    assert norm.classify_agent("claude") == ("claude-code", None)
    assert norm.classify_agent("opus-fwfg-deploy") == ("claude-code", None)


def test_classify_agent_unknown_stays_null():
    assert norm.classify_agent("") == (None, None)
    assert norm.classify_agent(None) == (None, None)
    assert norm.classify_agent("some-future-harness") == (None, None)


def test_account_for_wing_personal():
    assert norm.account_for_wing("pdev-foundation") == ("ja.powell@gmail.com", False)
    assert norm.account_for_wing("pdev-anything") == ("ja.powell@gmail.com", False)


def test_account_for_wing_work():
    for w in ("fwfg-deploy", "fwfg-data-warehouse", "dev", "wing_claude-opus-4-8",
              "apple-revenue-economics", "mempalace-bq", "inbox-triage"):
        account, review = norm.account_for_wing(w)
        assert account == "alan@fwfg.com" and review is False


def test_account_for_wing_unknown_is_flagged_not_defaulted():
    account, review = norm.account_for_wing("totally-unrecognized-thing")
    assert account is None and review is True


def _make_palace(tmp_path, drawers):
    """drawers: list of (id, document, metadata). Returns palace dir path."""
    p = tmp_path / "palace"
    client = chromadb.PersistentClient(path=str(p))
    col = client.get_or_create_collection("mempalace_drawers", metadata={"hnsw:space": "cosine"})
    col.add(ids=[d[0] for d in drawers], documents=[d[1] for d in drawers],
            metadatas=[d[2] for d in drawers])
    del col, client
    return str(p)


def test_seed_registry_assigns_accounts_and_flags_unknown(tmp_path):
    palace = _make_palace(tmp_path, [
        ("d1", "x", {"wing": "fwfg-deploy", "room": "decisions"}),
        ("d2", "y", {"wing": "pdev-foundation", "room": "decisions"}),
        ("d3", "z", {"wing": "mystery-wing", "room": "r"}),
        ("d4", "w", {"wing": "wing_claude-opus-4-8", "room": "diary"}),
    ])
    out = tmp_path / "wing_registry.yaml"
    norm.seed_registry_from_palace(palace, registry_path=out, dry_run=False)
    reg = wr.load_registry(out)
    by_slug = {e.slug: e for e in reg.entries}
    assert by_slug["fwfg-deploy"].account == "alan@fwfg.com"
    assert by_slug["pdev-foundation"].account == "ja.powell@gmail.com"
    assert by_slug["wing-claude-opus-4-8"].account == "alan@fwfg.com"
    # unknown wing is present but flagged (account None, status review)
    assert by_slug["mystery-wing"].account is None
    assert by_slug["mystery-wing"].status == "review"


def test_seed_registry_dry_run_writes_nothing(tmp_path):
    palace = _make_palace(tmp_path, [("d1", "x", {"wing": "fwfg-deploy", "room": "r"})])
    out = tmp_path / "wing_registry.yaml"
    norm.seed_registry_from_palace(palace, registry_path=out, dry_run=True)
    assert not out.exists()


def test_backfill_adds_provenance_preserves_existing_meta(tmp_path):
    palace = _make_palace(tmp_path, [
        ("d1", "doc one", {"wing": "fwfg-deploy", "room": "decisions",
                            "agent": "claude-opus-4-8", "filed_at": "2026-05-01T00:00:00"}),
        ("d2", "doc two", {"wing": "pdev-foundation", "room": "diary",
                           "agent": "claude-code", "_synced_from": "home-pc"}),
    ])
    reg = tmp_path / "wing_registry.yaml"
    norm.seed_registry_from_palace(palace, registry_path=reg, dry_run=False)
    changed = norm.backfill_provenance(palace, registry_path=reg, dry_run=False, backup=False)
    assert changed == 2

    client = chromadb.PersistentClient(path=palace)
    col = client.get_collection("mempalace_drawers")
    g = col.get(ids=["d1", "d2"], include=["documents", "metadatas"])
    m = {i: meta for i, meta in zip(g["ids"], g["metadatas"])}
    # provenance added
    assert m["d1"]["harness"] == "claude-code" and m["d1"]["model"] == "claude-opus-4.8"
    assert m["d1"]["account"] == "alan@fwfg.com"
    assert m["d2"]["account"] == "ja.powell@gmail.com"
    assert m["d2"]["machine"] == "home-pc"        # from _synced_from
    # existing metadata preserved; document untouched (verbatim)
    assert m["d1"]["room"] == "decisions" and m["d1"]["filed_at"] == "2026-05-01T00:00:00"
    assert g["documents"][g["ids"].index("d1")] == "doc one"


def test_backfill_is_idempotent(tmp_path):
    palace = _make_palace(tmp_path, [
        ("d1", "x", {"wing": "fwfg-deploy", "room": "r", "agent": "claude-code"})])
    reg = tmp_path / "wing_registry.yaml"
    norm.seed_registry_from_palace(palace, registry_path=reg, dry_run=False)
    norm.backfill_provenance(palace, registry_path=reg, dry_run=False, backup=False)
    second = norm.backfill_provenance(palace, registry_path=reg, dry_run=False, backup=False)
    assert second == 0          # nothing left to change


def test_backfill_dry_run_changes_nothing(tmp_path):
    palace = _make_palace(tmp_path, [
        ("d1", "x", {"wing": "fwfg-deploy", "room": "r", "agent": "claude-code"})])
    reg = tmp_path / "wing_registry.yaml"
    norm.seed_registry_from_palace(palace, registry_path=reg, dry_run=False)
    would = norm.backfill_provenance(palace, registry_path=reg, dry_run=True, backup=False)
    assert would == 1
    client = chromadb.PersistentClient(path=palace)
    col = client.get_collection("mempalace_drawers")
    assert "harness" not in (col.get(ids=["d1"], include=["metadatas"])["metadatas"][0])
