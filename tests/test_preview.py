from playwright.sync_api import sync_playwright
import pytest
from agent_retake.cli import main
from agent_retake.scan import scan_board, review_board
from agent_retake.storyboard import load_board, save_board
from test_scan import episode


@pytest.fixture
def timed(episode):
    board = load_board(episode)
    beat = board.beats[0]
    beat.start, beat.end = 0.0, 16.0
    beat.title = "</script><script>window.bad=true</script>"
    save_board(board, episode)
    scan_board(episode)
    return episode


@pytest.mark.parametrize("options", [[], ["--html"]])
def test_unreviewed_creates_nothing(timed, options):
    assert main(["preview", str(timed), "--beat", "1", *options]) != 0
    assert not (timed.parent / "footage").exists()


def test_html_seeks_in_both_directions(timed):
    review_board(timed)
    assert main(["preview", str(timed), "--beat", "1", "--html"]) == 0
    html = next((timed.parent / "footage").glob("*.html"))
    assert "person@example.org" not in html.read_text()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.goto(html.as_uri())
        page.evaluate("seek(0)")
        assert not page.locator("#lines").inner_text().strip()
        page.evaluate("seek(9)")
        first = page.locator("#lines").inner_text()
        page.evaluate("seek(15)")
        page.evaluate("seek(9)")
        assert page.locator("#lines").inner_text() == first
        assert not page.evaluate("window.bad")
        assert "</script>" in page.locator("#title").inner_text()
        browser.close()


def test_overlapping_intervals_fail_preflight(timed):
    from agent_retake.render.page import compile_board
    data=load_board(timed)
    second=data.beats[0].model_copy(deep=True)
    second.id=2
    second.start=1
    second.end=18
    data.beats.append(second)
    save_board(data,timed)
    scan_board(timed)
    review_board(timed)
    with pytest.raises(ValueError,match="overlap|order"):
        compile_board(timed)


def test_html_preview_uses_export_canvas_size(timed):
    review_board(timed)
    assert main(["preview", str(timed), "--beat", "1", "--html"]) == 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width":800, "height":650})
        page.goto(next((timed.parent / "footage").glob("*.html")).as_uri())
        page.evaluate("seek(12)")
        layout = page.locator("#viewport").evaluate("(el) => [el.clientWidth,el.scrollHeight]")
        page.set_viewport_size({"width":1050, "height":700})
        assert page.locator("#viewport").evaluate("(el) => [el.clientWidth,el.scrollHeight]") == layout
        assert layout[0] > 1800
        browser.close()


def test_prompt_composes_at_bottom_then_submits_once():
    from agent_retake.render.page import page_html
    from agent_retake.scene import SafeShot
    from agent_retake.storyboard import Theme
    from agent_retake.timing import TimedShot, Timeline

    question = "What changed?"
    timeline = Timeline("Orchard", 8, [
        TimedShot(SafeShot("typed", "claude", question, []), 0, 2),
        TimedShot(SafeShot("full", "claude", "A late frost.", []), 2, 4),
        TimedShot(SafeShot("typed", "claude", "When?", []), 4, 6),
    ])
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.set_content(page_html(timeline, Theme()))
        history = page.locator("#lines")
        page.evaluate("seek(1)")
        assert history.inner_text() == ""
        draft = page.locator("#draft")
        assert draft.inner_text() == "What ch"
        assert draft.bounding_box()["y"] > page.viewport_size["height"] * 0.8
        page.evaluate("seek(1.99)")
        assert draft.inner_text() == question and history.inner_text() == ""
        page.evaluate("seek(2)")
        assert history.inner_text().strip() == question
        assert not draft.inner_text()
        assert not page.locator("#caret").is_visible()
        page.evaluate("seek(3)")
        assert history.locator(".line").count() == 2
        assert history.locator(".line").first.inner_text() == question
        assert "A late" in history.locator(".line").last.inner_text()
        page.evaluate("seek(5)")
        assert history.locator(".earlier").count() == 2
        assert history.locator(".line").last.inner_text() == "• A late frost."
        assert draft.inner_text() == "Whe"
        page.evaluate("seek(3)")
        assert history.locator(".earlier").count() == 0
        page.evaluate("seek(1)")
        assert history.inner_text() == "" and draft.inner_text() == "What ch"
        browser.close()


def test_reviewed_history_stays_visible_while_composing_the_next_prompt(timed):
    from agent_retake.render.page import compile_board, page_html

    board = load_board(timed)
    second = board.beats[0].model_copy(deep=True)
    second.id = 2
    second.start, second.end = 16.0, 32.0
    board.beats.append(second)
    save_board(board, timed)
    scan_board(timed)
    review_board(timed)
    timelines, _, theme = compile_board(timed, 2)
    timeline = timelines[0][1]
    previous_text = timeline.shots[0].shot.text
    typing = timeline.shots[0]
    halfway = (typing.start + typing.end) / 2
    html = page_html(timeline, theme)
    assert "person@example.org" not in html

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.set_content(html)
        history = page.locator("#history .line")
        assert history.count() == len(board.beats[0].shots)
        assert history.first.inner_text() == previous_text
        before = history.all_text_contents()
        for t in (halfway, typing.end, halfway):
            page.evaluate("t => seek(t)", t)
            assert history.all_text_contents() == before
            assert page.locator("#lines .user-message").count() == int(t >= typing.end)
            assert bool(page.locator("#draft").inner_text()) == (t < typing.end)
        assert 0.5 < page.locator("#history").evaluate("el => +getComputedStyle(el).opacity") < 1
        browser.close()
