"""Small, local question matcher; history influences repetition, not predictions."""

import json
import random
import re
from pathlib import Path

from storage.transactions import immediate_transaction

OUTCOMES = ("yes", "maybe", "no")
CATEGORIES = ("general", "statement", "prediction", "advice", "ability")
MAX_QUESTION_LENGTH = 400
HISTORY_LIMIT = 100


def question_category(question: str) -> str:
    question = " ".join(question.casefold().replace("’", "'").split())
    if re.match(r"^(should|shall|could|would) i\b", question):
        return "advice"
    if re.match(r"^can i\b", question):
        return "ability"
    if re.match(r"^(will|won't)\b", question):
        return "prediction"
    if re.match(r"^(is|are|am|was|were|isn't|aren't|wasn't|weren't|does|do|did|doesn't|don't|didn't|has|have)\b", question):
        return "statement"
    return "general"


class EightBallService:
    def __init__(self, db, *, responses_path: Path | None = None):
        self.db = db
        path = responses_path or Path(__file__).with_name("eight_ball_responses.json")
        self.responses = json.loads(path.read_text(encoding="utf-8"))
        self._validate_responses()

    def _validate_responses(self) -> None:
        ids = set()
        for response in self.responses:
            if (not isinstance(response["id"], str) or not response["id"]
                    or response["id"] in ids or response["outcome"] not in OUTCOMES
                    or not response["categories"] or not set(response["categories"]) <= set(CATEGORIES)
                    or not isinstance(response["text"], str) or not response["text"].strip()
                    or len(response["text"]) > 200 or "\n" in response["text"]):
                raise ValueError("Invalid 8ball response definition")
            ids.add(response["id"])
        for outcome in OUTCOMES:
            if sum(r["outcome"] == outcome and "general" in r["categories"] for r in self.responses) < 2:
                raise ValueError(f"8ball requires at least two general {outcome} responses")

    async def answer(self, broadcaster_id: str, question: str) -> str:
        question = " ".join(question.split())
        if not question or len(question) > MAX_QUESTION_LENGTH:
            raise ValueError(f"Ask a question between 1 and {MAX_QUESTION_LENGTH} characters")
        category = question_category(question)
        # Choose the verdict independently of pool sizes and previous answers.
        outcome = random.choice(OUTCOMES)
        candidates = [r for r in self.responses if r["outcome"] == outcome
                      and (category in r["categories"] or "general" in r["categories"])]

        async with self.db.acquire() as connection:
            async with immediate_transaction(connection):
                recent = await connection.fetchall(
                    "SELECT response_id FROM eight_ball_history WHERE broadcaster_id = ? ORDER BY id DESC LIMIT ?",
                    (broadcaster_id, HISTORY_LIMIT),
                )
                recent_ids = [row["response_id"] for row in recent]
                # Relax the oldest exclusion first if this outcome's pool is exhausted.
                for count in range(len(recent_ids), -1, -1):
                    available = [r for r in candidates if r["id"] not in recent_ids[:count]]
                    if available:
                        selected = random.choice(available)
                        break
                await connection.execute(
                    "INSERT INTO eight_ball_history (broadcaster_id, question, category, outcome, response_id) VALUES (?, ?, ?, ?, ?)",
                    (broadcaster_id, question, category, outcome, selected["id"]),
                )
                await connection.execute(
                    """DELETE FROM eight_ball_history WHERE broadcaster_id = ? AND id NOT IN
                       (SELECT id FROM eight_ball_history WHERE broadcaster_id = ? ORDER BY id DESC LIMIT ?)""",
                    (broadcaster_id, broadcaster_id, HISTORY_LIMIT),
                )
        return selected["text"]
