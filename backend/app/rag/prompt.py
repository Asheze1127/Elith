"""Prompt layer: turns tenant_config into the LLM's answering instructions (#9).

multi-tenant-design.md §5: "プロンプト層：config を回答方針に反映する." This is
the one place tenant_config's `answer.*` / `category_policies` fields become
natural-language instructions for the model. It does not decide anything
itself (no citation formatting, no confidence scoring, no category
classification) -- it only writes instructions and lets the model follow
them; ground_check/cite/etc. (later issues) are what actually enforce/verify
policy against the model's output.

Design choice -- category matching happens inside the instructions, not in
Python: this module has no query-categorization mechanism (out of scope, and
no such component exists anywhere in the repo yet), so rather than guessing a
category itself, it emits a conditional instruction per configured category
("if the question is about X, do Y") and lets the model apply it. This keeps
category_policies reflection squarely a prompt-text concern, matching the
issue's framing that there is no dedicated "mode step" / "category step" in
the pipeline -- mode and category_policies are reflected here, not as steps.
"""

from __future__ import annotations

from typing import Any

from app.models.chunk import Chunk


def build_prompt(config: dict[str, Any], chunks: list[Chunk], query: str) -> str:
    """Build the final prompt string for ``get_llm_provider().generate(...)``.

    Reflects, at minimum:
    - ``answer.default_mode`` (multi-tenant-design.md §3): external vs.
      internal changes tone and whether internal-only detail may be shown
      (permission-design.md §5).
    - ``answer.citation == "required"``: instructs the model to ground every
      claim and refuse to guess instead of asserting unfounded facts
      (permission-design.md §6-1). The actual verification of that is
      `ground_check`/`cite`'s job (#10/#11), not this function's.
    - ``answer.low_confidence_action == "needs_review"``: tells the model to
      flag low-confidence answers instead of asserting them.
    - ``category_policies``: each configured category becomes one conditional
      instruction (tone override and/or a human-check notice), covering
      permission-design.md §6-2's "contract -> require_human_check" example.

    ``chunks`` are inlined verbatim as numbered context entries; no citation
    formatting is applied (that is #10's job) -- numbering here only gives the
    model a stable way to refer back to a passage if it chooses to.
    """
    answer_cfg = config.get("answer", {})
    mode = answer_cfg.get("default_mode", "internal")
    citation_required = answer_cfg.get("citation") == "required"
    category_policies = config.get("category_policies", {})

    lines: list[str] = [
        "You are a RAG assistant. Answer the user's question using only the "
        "context passages below.",
        "",
        f"User question: {query}",
        "",
        "Context:",
    ]
    if chunks:
        lines.extend(f"[{i}] {chunk.content}" for i, chunk in enumerate(chunks, start=1))
    else:
        lines.append("(no relevant context was found)")

    lines.append("")
    lines.append("Answering policy:")

    if mode == "external":
        lines.append(
            "- Mode: external. Use polite, customer-facing language and do not reveal "
            "internal-only information (internal notes, process detail, or anything not "
            "meant for an outside customer)."
        )
    else:
        lines.append(
            "- Mode: internal. You may include source detail and the reasoning behind the "
            "answer for an internal, already-authorized reader."
        )

    if citation_required:
        lines.append(
            "- Every factual claim must be grounded in the context above. Do not state "
            "anything the context does not support; if the context is insufficient, say so "
            "instead of guessing."
        )
    else:
        lines.append(
            "- Ground claims in the context above when possible, but citation is not mandatory."
        )

    if answer_cfg.get("low_confidence_action") == "needs_review":
        lines.append(
            "- If you are not confident the context answers the question, say the question "
            "needs review rather than guessing."
        )

    for category, policy in category_policies.items():
        if not isinstance(policy, dict):
            continue
        tone = policy.get("tone")
        if tone:
            lines.append(f"- If the question is about '{category}', respond in a {tone} tone.")
        if policy.get("require_human_check"):
            lines.append(
                f"- If the question is about '{category}', explicitly note that a human must "
                "confirm the answer before it is treated as final."
            )

    return "\n".join(lines)
