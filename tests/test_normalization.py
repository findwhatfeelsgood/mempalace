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
