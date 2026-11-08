import pytest
from agent_retake.gather import gather
from agent_retake.storyboard import init_storyboard, select, load_board
from test_gather import DEMO


def test_refs_and_one_beat_per_prompt():
    data = gather([DEMO])
    board = init_storyboard(data)
    assert len(board.beats) == 1
    msgs = data.sessions[0].messages
    assert select(data, msgs[0].id + ".." + msgs[-1].id) == msgs
    with pytest.raises(ValueError):
        select(data, msgs[-1].id + ".." + msgs[0].id)


@pytest.mark.parametrize("bad", ["title: one\ntitle: two", "beats: wrong", "unknown: true"])
def test_board_rejects_invalid_yaml(tmp_path, bad):
    file = tmp_path / "board.yaml"
    file.write_text(bad)
    with pytest.raises(ValueError):
        load_board(file)
