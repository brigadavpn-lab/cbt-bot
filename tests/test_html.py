from app.utils.html import esc


def test_esc_none_returns_empty():
    assert esc(None) == ""


def test_esc_empty_string():
    assert esc("") == ""


def test_esc_plain_text():
    assert esc("hello") == "hello"


def test_esc_html_tags():
    assert esc("<script>alert(1)</script>") == "&lt;script&gt;alert(1)&lt;/script&gt;"


def test_esc_ampersand():
    assert esc("Tom & Jerry") == "Tom &amp; Jerry"


def test_esc_quotes():
    assert esc('say "hello"') == "say &quot;hello&quot;"


def test_esc_integer():
    assert esc(123) == "123"


def test_esc_zero_not_empty():
    # 0 is not None, so it must not short-circuit to '' via the None guard
    assert esc(0) == "0"
