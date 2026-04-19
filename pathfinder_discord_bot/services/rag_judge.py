"""LLM-as-judge for evaluating RAG answers against required information points."""

import json
import logging
import re
from dataclasses import dataclass

from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)


@dataclass
class InfoPointVerdict:
    """Judgment on a single required information point."""

    info_point: str
    covered: bool
    explanation: str


@dataclass
class JudgeVerdict:
    """Full judgment on a RAG answer."""

    question_id: str
    passed: bool
    verdicts: list[InfoPointVerdict]
    raw_response: str


JUDGE_SYSTEM_PROMPT = """You are a strict evaluator for a Pathfinder 2nd Edition rules Q&A system.

You will be given:
1. A QUESTION that was asked
2. An ANSWER that was generated
3. A list of REQUIRED INFORMATION POINTS that the answer must cover

Your job is to determine whether each required information point is adequately covered \
by the answer. A point is "covered" if the answer conveys the same essential meaning, even \
if the exact wording differs. Minor omissions or simplifications are acceptable as long as \
the core fact is present and not contradicted.

Respond with a JSON array where each element has:
- "info_point": the required info point text (copied exactly)
- "covered": true or false
- "explanation": a brief (1 sentence) reason for your judgment

Respond ONLY with the JSON array, no other text."""


class RAGJudge:
    """Evaluates RAG answers using Claude as a judge."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model

    async def evaluate(
        self,
        question_id: str,
        question: str,
        answer: str,
        required_info_points: list[str],
    ) -> JudgeVerdict:
        """Judge whether an answer covers all required information points."""
        info_points_formatted = "\n".join(
            f"  {i}. {point}" for i, point in enumerate(required_info_points, 1)
        )

        user_message = (
            f"QUESTION:\n{question}\n\n"
            f"ANSWER:\n{answer}\n\n"
            f"REQUIRED INFORMATION POINTS:\n{info_points_formatted}"
        )

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=JUDGE_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )

            raw_text = response.content[0].text
            logger.debug(f"Judge raw response for {question_id}: {raw_text}")

            # Strip markdown code fences if present (```json ... ``` or ``` ... ```)
            json_text = raw_text.strip()
            fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", json_text, re.DOTALL)
            if fence_match:
                json_text = fence_match.group(1).strip()

            verdicts_data = json.loads(json_text)

            verdicts = [
                InfoPointVerdict(
                    info_point=v["info_point"],
                    covered=v["covered"],
                    explanation=v["explanation"],
                )
                for v in verdicts_data
            ]

            return JudgeVerdict(
                question_id=question_id,
                passed=all(v.covered for v in verdicts),
                verdicts=verdicts,
                raw_response=raw_text,
            )

        except json.JSONDecodeError as e:
            logger.exception(f"Judge returned invalid JSON for {question_id}: {e}")
            return JudgeVerdict(
                question_id=question_id,
                passed=False,
                verdicts=[
                    InfoPointVerdict(
                        info_point=point,
                        covered=False,
                        explanation="Judge returned invalid JSON — could not evaluate",
                    )
                    for point in required_info_points
                ],
                raw_response=raw_text,
            )
        except Exception as e:
            logger.exception(f"Judge evaluation failed for {question_id}: {e}")
            raise
