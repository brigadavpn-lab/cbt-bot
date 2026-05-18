from app.bot.handlers.check_answer import _level_for_xp


def test_level_starts_at_1():
    assert _level_for_xp(0) == 1
    assert _level_for_xp(99) == 1


def test_level_increments_every_100():
    assert _level_for_xp(100) == 2
    assert _level_for_xp(250) == 3
    assert _level_for_xp(999) == 10
