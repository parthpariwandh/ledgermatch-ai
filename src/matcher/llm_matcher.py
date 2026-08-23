from __future__ import annotations

import json
import os
from dataclasses import dataclass

from pydantic import BaseModel, Field

from src.models.transactions import MatchPair, Transaction


class LLMDecision(BaseModel):
    decision: str = Field(pattern="^(match|no_match)$")
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    bank_txn_id: str | None = None
    ledger_txn_id: str | None = None


@dataclass
class LLMMatcher:
    model: str = "gpt-4o-mini"

    def _heuristic_decision(self, r: Transaction, bank_candidates: list[Transaction], ledger_candidates: list[Transaction]) -> LLMDecision:
        best: tuple[Transaction, Transaction, float] | None = None
        for b in bank_candidates:
            for l in ledger_candidates:
                ref_bonus = 0.0
                if r.reference and b.reference and l.reference:
                    rr = r.reference.lower().strip()
                    if rr in b.reference.lower() and rr in l.reference.lower():
                        ref_bonus = 0.2
                amount_score = max(0.0, 1.0 - (abs(r.amount - b.amount) + abs(r.amount - l.amount)) / 10.0)
                date_score = max(0.0, 1.0 - (abs((r.txn_date - b.txn_date).days) + abs((r.txn_date - l.txn_date).days)) / 6.0)
                score = 0.5 * amount_score + 0.3 * date_score + ref_bonus
                if not best or score > best[2]:
                    best = (b, l, score)

        if best and best[2] >= 0.74:
            return LLMDecision(
                decision="match",
                confidence=min(0.9, best[2]),
                reason="Heuristic LLM fallback matched based on amount/date/reference proximity",
                bank_txn_id=best[0].txn_id,
                ledger_txn_id=best[1].txn_id,
            )

        return LLMDecision(decision="no_match", confidence=0.35, reason="No robust candidate pair in ambiguous set")

    def decide(self, r: Transaction, bank_candidates: list[Transaction], ledger_candidates: list[Transaction]) -> LLMDecision:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return self._heuristic_decision(r, bank_candidates, ledger_candidates)

        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key)
            prompt = {
                "task": "Resolve an ambiguous financial reconciliation case.",
                "rules": [
                    "Only return strict JSON",
                    "decision must be match or no_match",
                    "If match, select exactly one bank_txn_id and one ledger_txn_id",
                ],
                "razorpay": r.model_dump(mode="json"),
                "bank_candidates": [b.model_dump(mode="json") for b in bank_candidates],
                "ledger_candidates": [l.model_dump(mode="json") for l in ledger_candidates],
            }
            completion = client.responses.create(
                model=self.model,
                input=[{"role": "user", "content": json.dumps(prompt)}],
                temperature=0,
            )
            content = completion.output_text.strip()
            return LLMDecision.model_validate_json(content)
        except Exception:
            return self._heuristic_decision(r, bank_candidates, ledger_candidates)

    def match(self, ambiguous: list[tuple[Transaction, list[Transaction], list[Transaction]]], used_r: set[str], used_b: set[str], used_l: set[str]) -> tuple[list[MatchPair], set[str], set[str], set[str]]:
        matches: list[MatchPair] = []
        for r, bank_candidates, ledger_candidates in ambiguous:
            if r.txn_id in used_r:
                continue
            bank_filtered = [b for b in bank_candidates if b.txn_id not in used_b]
            ledger_filtered = [l for l in ledger_candidates if l.txn_id not in used_l]
            if not bank_filtered or not ledger_filtered:
                continue
            decision = self.decide(r, bank_filtered, ledger_filtered)
            if decision.decision == "match" and decision.bank_txn_id and decision.ledger_txn_id:
                b = next((x for x in bank_filtered if x.txn_id == decision.bank_txn_id), None)
                l = next((x for x in ledger_filtered if x.txn_id == decision.ledger_txn_id), None)
                if b and l:
                    matches.append(
                        MatchPair(
                            razorpay_txn_id=r.txn_id,
                            bank_txn_id=b.txn_id,
                            ledger_txn_id=l.txn_id,
                            confidence=decision.confidence,
                            method="llm",
                            notes=decision.reason,
                        )
                    )
                    used_r.add(r.txn_id)
                    used_b.add(b.txn_id)
                    used_l.add(l.txn_id)

        return matches, used_r, used_b, used_l
