import importlib


def _reload(monkeypatch, tmp_path, account="alan@fwfg.com", harness="openai-agents-sdk"):
    monkeypatch.setenv("MEMPALACE_PALACE_PATH", str(tmp_path / "palace"))
    monkeypatch.setenv("MEMPALACE_REGISTRY_PATH", str(tmp_path / "wing_registry.yaml"))
    if account is None:
        monkeypatch.delenv("MEMPALACE_ACCOUNT", raising=False)
    else:
        monkeypatch.setenv("MEMPALACE_ACCOUNT", account)
    monkeypatch.setenv("MEMPALACE_HARNESS", harness)
    import mempalace.config as config
    import mempalace.mcp_server as srv
    importlib.reload(config)
    importlib.reload(srv)
    return srv


def test_bootstrap_account_scopes_wings(monkeypatch, tmp_path):
    from mempalace import wing_registry as wr
    wr.save_registry(wr.Registry(entries=[
        wr.WingEntry(slug="fwfg-deploy", kind="project", account="alan@fwfg.com", description="work"),
        wr.WingEntry(slug="pdev-foundation", kind="project", account="ja.powell@gmail.com", description="personal"),
    ]), tmp_path / "wing_registry.yaml")
    srv = _reload(monkeypatch, tmp_path)
    out = srv.tool_bootstrap()
    slugs = [w["slug"] for w in out["wings"]]
    assert "fwfg-deploy" in slugs
    assert "pdev-foundation" not in slugs            # personal hidden from work caller
    assert out["provenance"]["harness"] == "openai-agents-sdk"
    assert "protocol" in out and "aaak_dialect" in out and "filing_rules" in out


def test_bootstrap_warns_on_missing_account(monkeypatch, tmp_path):
    srv = _reload(monkeypatch, tmp_path, account=None)
    out = srv.tool_bootstrap()
    assert any("account" in w.lower() for w in out["warnings"])
