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
