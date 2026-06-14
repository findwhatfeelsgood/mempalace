from mempalace import normalization as norm


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
