import pytest
from agent_retake.scan import find_hits, scan_board, review_board
from agent_retake.scene import prepare_scene
from agent_retake.storyboard import load_board, save_board, initialize
from agent_retake.gather import gather
from test_gather import DEMO


@pytest.fixture
def episode(tmp_path):
    conv = gather([DEMO])
    conv.sessions[0].messages[1].tool = "private.invalid"
    conv.sessions[0].messages[-1].text = "Contact person@example.org"
    data = tmp_path / "sessions.json"
    data.write_text(conv.model_dump_json())
    path = tmp_path / "board.yaml"
    initialize(data, path)
    board = load_board(path)
    board.beats[0].title = "person@example.org"
    board.beats[0].shots[-1].highlight = ["person@example.org"]
    save_board(board, path)
    return path


def test_review_binding_and_private_sidecar(episode):
    scan_board(episode)
    assert "person@example.org" not in load_board(episode).redactions.model_dump_json()
    with pytest.raises(ValueError, match="review"):
        prepare_scene(episode)
    review_board(episode)
    assert "person@example.org" not in str(prepare_scene(episode))
    board = load_board(episode)
    board.beats[0].title = "changed"
    save_board(board, episode)
    with pytest.raises(ValueError):
        prepare_scene(episode)


@pytest.mark.parametrize("change", ["remove", "version", "bundle", "keep", "collision"])
def test_gate_rechecks(episode, change):
    scan_board(episode)
    board = load_board(episode)
    if change == "remove":
        board.redactions.rules.pop()
    if change == "keep":
        rule = board.redactions.rules[0]
        rule.keep, rule.replace, rule.reason = True, None, ""
    if change == "version":
        board.redactions.scan_version = 99
    if change == "bundle":
        with episode.with_name("sessions.json").open("a") as stream:
            stream.write(" ")
    if change == "collision":
        board.redactions.rules[0].replace = "person@example.org"
    save_board(board, episode)
    with pytest.raises(ValueError) as err:
        review_board(episode)
    assert "person@example.org" not in str(err.value)


def test_detectors():
    values = ["person@example.org", "192.0.2.44", "2001:db8::5", "/home/operator",
              "demo.internal", "123456789012", "a13c" * 10,
              "U3ludGhldGljQ29udGVudExvbmdFbm91Z2g=", "+1 (202) 555-0117",
              "sk-" + "0123456789abcdefghijklmnopqrstuvwxyz"]
    found = find_hits(values)
    for value in values:
        assert value in found


def test_trim_after_redaction_keeps_original_out(episode):
    from agent_retake.storyboard import Shot
    b = load_board(episode)
    base = b.beats[0].shots[-1]
    b.beats[0].shots = [Shot(message=base.message, show="still", span=[8, 15])]
    save_board(b, episode)
    scan_board(episode)
    review_board(episode)
    text = prepare_scene(episode).beats[0].shots[0].text
    assert text == "editor-"


def test_new_theme_string_invalidates_review_and_is_sanitized(episode):
    from agent_retake.render.page import compile_board, page_html
    secret = "sk-proj-INVENTED000001"
    scan_board(episode)
    review_board(episode)
    (episode.parent / "retake.yaml").write_text("themes:\n  neutral:\n    glyphs:\n      claude: " + secret)
    with pytest.raises(ValueError):
        compile_board(episode)
    scan_board(episode)
    review_board(episode)
    b = load_board(episode)
    b.beats[0].start, b.beats[0].end = 0.0, 20.0
    save_board(b, episode)
    beats, _, theme = compile_board(episode)
    assert secret not in page_html(beats[0][1], theme, controls=True)


def test_changed_selection_requires_review(episode):
    scan_board(episode)
    review_board(episode)
    b = load_board(episode)
    b.beats[0].shots = b.beats[0].shots[1:]
    save_board(b, episode)
    with pytest.raises(ValueError, match="review"):
        prepare_scene(episode)


def test_keep_cannot_override_nested_replacement(episode):
    from agent_retake.scan import sidecar_values
    scan_board(episode)
    b = load_board(episode)
    values = sidecar_values(episode, b)
    rule = next(r for r in b.redactions.rules if values[r.id]=="person@example.org")
    rule.replace, rule.keep, rule.reason = None, True, "public email"
    save_board(b, episode)
    with pytest.raises(ValueError):
        review_board(episode)


def test_invalid_rule_and_field_never_echo_literals(episode,capsys):
    from agent_retake.cli import main
    secret = "sk-proj-INVENTED000001"
    scan_board(episode)
    b = load_board(episode)
    b.redactions.rules[0].id = secret
    save_board(b, episode)
    assert main(["scan",str(episode),"--review"]) != 0
    assert secret not in capsys.readouterr().err
    with episode.open("a") as f:
        f.write(secret + ": true\n")
    assert main(["preview",str(episode),"--beat","1","--html"]) != 0
    assert secret not in capsys.readouterr().err


def test_condensed_preserves_headers_lists_and_one_sentence_per_paragraph():
    from agent_retake.scene import condensed
    text = "**Outcome**\nWe tested\nthe idea. Another sentence.\n\n- A result. Extra.\n- B result."
    assert condensed(text) == "**Outcome**\nWe tested the idea.\n- A result.\n- B result."
