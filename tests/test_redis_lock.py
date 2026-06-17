import asyncio
import pytest


# Lua unlock script mirrored from app/bot/handlers/my_situation.py
_LUA_UNLOCK = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""

LOCK_KEY = "ai_lock:12345"


# ---------------------------------------------------------------------------
# T8 — SETNX returns None when lock is already held
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_setnx_fails_when_lock_held(fake_redis):
    await fake_redis.set(LOCK_KEY, "other_token", nx=True, ex=30)

    acquired = await fake_redis.set(LOCK_KEY, "new_token", nx=True, ex=30)

    assert acquired is None  # SETNX returned 0 → lock not acquired


# ---------------------------------------------------------------------------
# T9 — TTL expiry: after key deleted, new SETNX succeeds
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_setnx_succeeds_after_ttl_expiry(fake_redis):
    await fake_redis.set(LOCK_KEY, "old_token", nx=True, ex=30)

    # Simulate TTL expiry by explicit delete (result is identical for the test)
    await fake_redis.delete(LOCK_KEY)

    acquired = await fake_redis.set(LOCK_KEY, "new_token", nx=True, ex=30)

    assert acquired is True


# ---------------------------------------------------------------------------
# T10 — Lua unlock does NOT delete a lock owned by a different token
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_lua_unlock_does_not_delete_foreign_lock(fake_redis):
    await fake_redis.set(LOCK_KEY, "token_b", nx=True, ex=30)

    # Process A tries to unlock with token_a — should be a no-op
    result = await fake_redis.eval(_LUA_UNLOCK, 1, LOCK_KEY, "token_a")

    assert result == 0  # Lua script returned 0 — nothing deleted
    assert await fake_redis.get(LOCK_KEY) == b"token_b"  # process B's lock intact


# ---------------------------------------------------------------------------
# T11 — Concurrent asyncio.gather: exactly one winner out of two SETNX calls
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concurrent_setnx_exactly_one_winner(fake_redis):
    results = await asyncio.gather(
        fake_redis.set(LOCK_KEY, "t1", nx=True, ex=30),
        fake_redis.set(LOCK_KEY, "t2", nx=True, ex=30),
    )

    true_count = sum(1 for r in results if r is True)
    assert true_count == 1, f"Expected exactly 1 winner, got results={results}"
