import json
from typing import Any

from backend.app.answering.schemas import EvidenceRecord

ANSWER_GENERATION_PROMPT = """You answer a scientific question using only SPARQL query results and evidence.

User question:
{question}

SPARQL query:
{sparql_query}

Query result rows:
{query_result}

Evidence:
{evidence}

Rules:
1. Answer only from the query result and evidence.
2. Do not use outside knowledge.
3. Mention the paper title when possible.
4. Mention the evidence briefly.
5. If query_result is empty, say the graph did not contain enough evidence.
6. Keep the answer concise.
"""


class AnswerGenerator:
    """Generate concise grounded answers from query results and evidence."""

    def build_prompt(
        self,
        question: str,
        sparql_query: str,
        query_result: dict[str, Any],
        evidence: list[EvidenceRecord],
    ) -> str:
        return ANSWER_GENERATION_PROMPT.format(
            question=question,
            sparql_query=sparql_query,
            query_result=json.dumps(query_result, indent=2),
            evidence=json.dumps([item.model_dump() for item in evidence], indent=2),
        )

    def generate(
        self,
        question: str,
        sparql_query: str,
        query_result: dict[str, Any],
        evidence: list[EvidenceRecord],
    ) -> str:
        del question, sparql_query

        status = query_result.get("status")
        if status == "validation_error":
            return "I could not answer the question because the generated SPARQL query was invalid."
        if status != "success":
            return "I could not answer the question because SPARQL execution failed."

        rows = query_result.get("rows", [])
        if not rows:
            return "The graph did not contain enough evidence to answer this question."

        row = rows[0]
        fallback_paper_title = evidence[0].paper_title if evidence else None
        paper_title = row.get("paperTitle") or fallback_paper_title or "The paper"
        evidence_text = self._normalize_sentence(
            row.get("evidenceText")
            or (evidence[0].text_span if evidence else "")
        )

        method_name = row.get("methodName")
        task_name = row.get("taskName")
        claim_text = row.get("claimText")
        benchmark_name = row.get("benchmarkName")

        if method_name and task_name:
            lead = (
                f"{paper_title} proposes {method_name} for "
                f"{self._normalize_sentence(task_name, terminal='')}"
            )
            answer = f"{lead}."
        elif claim_text:
            answer = (
                f"{paper_title} argues that "
                f"{self._normalize_sentence(claim_text, capitalize=False)}"
            )
        elif benchmark_name:
            answer = f"{paper_title} discusses {self._normalize_sentence(benchmark_name, terminal='')}."
        else:
            answer = f"{paper_title} is the best-supported result in the graph."

        if evidence_text:
            answer = f"{answer} The evidence states that {evidence_text}"
        return answer

    @staticmethod
    def _normalize_sentence(
        text: str,
        *,
        capitalize: bool = True,
        terminal: str = ".",
    ) -> str:
        cleaned = " ".join(str(text).split()).strip()
        if not cleaned:
            return ""
        cleaned = cleaned.rstrip(".")
        if capitalize:
            cleaned = cleaned[0].upper() + cleaned[1:]
        if terminal:
            cleaned = f"{cleaned}{terminal}"
        return cleaned

    @staticmethod
    def _lowercase_first(text: str) -> str:
        if not text:
            return text
        if len(text) == 1:
            return text.lower()
        return text[0].lower() + text[1:]
