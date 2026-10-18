"""Token budget guard so a run can't silently get expensive."""
from dataclasses import dataclass, field


@dataclass
class Budget:
    max_usd: float = 1.00
    spent_usd: float = 0.0
    calls: list = field(default_factory=list)
    # Conservative blended fallback ($/1k tokens) when OpenRouter omits a price.
    _est_per_1k: float = 0.005

    def record(self, model_id: str, usage: dict, pricing: dict | None = None) -> None:
        usage = usage or {}
        cost = float(usage.get("cost") or 0.0)
        estimated = False
        if cost <= 0.0:
            prompt = float(usage.get("prompt_tokens") or 0)
            completion = float(usage.get("completion_tokens") or 0)
            if prompt or completion:
                if pricing:
                    cost = (prompt * float(pricing.get("prompt_price") or 0)
                            + completion * float(pricing.get("completion_price") or 0)) / 1_000_000
                else:
                    cost = (prompt + completion) / 1000 * self._est_per_1k
                estimated = True
        self.spent_usd += cost
        self.calls.append({"model": model_id, "cost": cost, "estimated": estimated, "usage": usage})
        if self.spent_usd > self.max_usd:
            raise RuntimeError(f"Budget exceeded: ${self.spent_usd:.4f} > ${self.max_usd:.2f}")
