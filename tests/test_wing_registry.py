import pytest

from mempalace import wing_registry as wr


def test_normalize():
    assert wr.normalize("  FWFG Deploy ") == "fwfg-deploy"
    assert wr.normalize("fwfg_data_warehouse") == "fwfg-data-warehouse"
    assert wr.normalize("wing__claude__code") == "wing-claude-code"


def test_load_missing_returns_empty(tmp_path):
    reg = wr.load_registry(tmp_path / "nope.yaml")
    assert reg.entries == []


def test_save_then_load_roundtrip(tmp_path):
    p = tmp_path / "reg.yaml"
    reg = wr.Registry(entries=[wr.WingEntry(
        slug="fwfg-deploy", display="FWFG Deploy", kind="project",
        account="alan@fwfg.com", aliases=["fwfg_deploy"], status="active",
        description="deploy repo")])
    wr.save_registry(reg, p)
    reloaded = wr.load_registry(p)
    assert reloaded.entries[0].slug == "fwfg-deploy"
    assert "fwfg_deploy" in reloaded.entries[0].aliases


@pytest.fixture
def reg():
    return wr.Registry(entries=[
        wr.WingEntry(slug="fwfg-deploy", kind="project", account="alan@fwfg.com",
                     aliases=["fwfg_deploy"]),
        wr.WingEntry(slug="fwfg-data-warehouse", kind="project", account="alan@fwfg.com"),
        wr.WingEntry(slug="pdev-foundation", kind="project", account="ja.powell@gmail.com"),
    ])


def test_exact_alias_match_is_canonical(reg):
    r = wr.canonicalize_wing("fwfg_deploy", account="alan@fwfg.com", kind="project", registry=reg)
    assert r.slug == "fwfg-deploy" and r.status == "canonical"


def test_high_confidence_fuzzy_is_canonical_no_alias_learn(reg):
    r = wr.canonicalize_wing("fwfg-data-warehous", account="alan@fwfg.com", kind="project", registry=reg)
    assert r.slug == "fwfg-data-warehouse" and r.status == "canonical"
    # no auto-learn: alias list unchanged
    assert "fwfg-data-warehous" not in [a for e in reg.entries for a in e.aliases]


def test_no_match_is_provisional(reg):
    r = wr.canonicalize_wing("brand-new-thing", account="alan@fwfg.com", kind="project", registry=reg)
    assert r.slug == "brand-new-thing" and r.status == "provisional"


def test_other_account_wing_never_canonicalizes(reg):
    r = wr.canonicalize_wing("pdev-foundation", account="alan@fwfg.com", kind="project", registry=reg)
    assert r.status == "provisional" and r.slug == "pdev-foundation"


def test_missing_registry_is_unverified(tmp_path):
    r = wr.canonicalize_wing("whatever", account="alan@fwfg.com", kind="project",
                             registry=wr.load_registry(tmp_path / "absent.yaml"))
    assert r.status == "unverified" and r.slug == "whatever"


def test_canonicalize_agent_strips_wing_prefix_and_normalizes():
    assert wr.canonicalize_agent("wing_claude-code") == "claude-code"
    assert wr.canonicalize_agent("Claude Code") == "claude-code"
    assert wr.canonicalize_agent("wing_wing_claude-code") == "claude-code"
    assert wr.canonicalize_agent("openai-agents-sdk") == "openai-agents-sdk"


def test_canonicalize_agent_all_prefix_becomes_unknown():
    assert wr.canonicalize_agent("wing_") == "unknown"
    assert wr.canonicalize_agent("wing_wing_") == "unknown"
    assert wr.canonicalize_agent("WING_") == "unknown"


def test_register_wing_creates_new(reg):
    out = wr.register_wing(reg, slug="new-thing", account="alan@fwfg.com", kind="project",
                           display="New Thing", description="d")
    assert out.status == "canonical"
    assert any(e.slug == "new-thing" for e in reg.entries)


def test_register_wing_merge_adds_alias(reg):
    out = wr.register_wing(reg, slug="fwfg-deploy", account="alan@fwfg.com", kind="project",
                           merge_alias="fwfgdeploy")
    assert out.status == "canonical" and out.slug == "fwfg-deploy"
    entry = next(e for e in reg.entries if e.slug == "fwfg-deploy")
    assert "fwfgdeploy" in entry.aliases


def test_fallback_paths_preserve_input_name():
    # empty registry -> unverified, name preserved (underscores NOT dashed)
    r = wr.canonicalize_wing("test_wing", account=None, kind="project", registry=wr.Registry())
    assert r.status == "unverified" and r.slug == "test_wing"
    # registry present but no match -> provisional, name preserved
    reg = wr.Registry(entries=[wr.WingEntry(slug="fwfg-deploy", kind="project", account="alan@fwfg.com")])
    r2 = wr.canonicalize_wing("my_new_proj", account="alan@fwfg.com", kind="project", registry=reg)
    assert r2.status == "provisional" and r2.slug == "my_new_proj"
