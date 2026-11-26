"""
Cost guard (tiêu chí 8) — Cộng dồn chi phí LLM vào Redis.
"""
from datetime import datetime, timezone
import redis
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


def _budget_key() -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"budget:{today}"


def check_budget() -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → raise HTTPException(status_code=402)."""
    try:
        spent = float(r.get(_budget_key()) or 0.0)
        if spent >= settings.daily_budget_usd:
            raise HTTPException(status_code=402, detail="Daily budget exceeded")
    except HTTPException:
        raise
    except redis.RedisError:
        raise HTTPException(status_code=503, detail="Cost guard unavailable")


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí của request vào tổng, trả về chi phí request."""
    cost = (
        (input_tokens / 1000.0) * PRICE_INPUT_PER_1K
        + (output_tokens / 1000.0) * PRICE_OUTPUT_PER_1K
    )
    key = _budget_key()
    try:
        r.incrbyfloat(key, cost)
        r.expire(key, 2 * 24 * 3600)
    except redis.RedisError:
        pass
    return cost
