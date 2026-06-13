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
