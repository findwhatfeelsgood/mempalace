from mempalace.config import match_tree

TREES = [
    {"path": r"C:\dev", "account": "alan@fwfg.com"},
    {"path": r"C:\pdev", "account": "ja.powell@gmail.com"},
]


def test_exact_and_nested_match():
    assert match_tree(r"C:\dev", TREES) == ("alan@fwfg.com", r"C:\dev")
    assert match_tree(r"C:\dev\mempalace", TREES) == ("alan@fwfg.com", r"C:\dev")
    assert match_tree(r"C:\pdev\foo\bar", TREES) == ("ja.powell@gmail.com", r"C:\pdev")


def test_no_match_returns_none():
    assert match_tree(r"C:\Users\alan", TREES) == (None, None)


def test_boundary_not_substring():
    # C:\developer must NOT match C:\dev
    assert match_tree(r"C:\developer\x", TREES) == (None, None)


def test_case_insensitive():
    assert match_tree(r"c:\DEV\Mempalace", TREES) == ("alan@fwfg.com", r"C:\dev")


def test_longest_prefix_wins():
    trees = [
        {"path": r"C:\dev", "account": "work@x"},
        {"path": r"C:\dev\personal-sub", "account": "personal@x"},
    ]
    assert match_tree(r"C:\dev\personal-sub\proj", trees) == ("personal@x", r"C:\dev\personal-sub")


def test_skips_malformed_entries():
    trees = [{"path": r"C:\dev"}, {"account": "x"}, {"path": r"C:\dev", "account": "ok@x"}]
    assert match_tree(r"C:\dev\x", trees) == ("ok@x", r"C:\dev")
