"""
chat_copilot.py - Explainable Risk Copilot

Two paths, both grounded in the same structured facts (never free-form
invention of numbers):

1. LLM path (used when an API key is configured): the structured facts
   (contributing factors, evidence present/missing, scores, thresholds)
   are passed to the model as the ONLY source of truth it's allowed to
   describe, with an explicit instruction not to invent additional
   numbers or claims. Provider is chosen by whichever *_API_KEY env var is
   set (ANTHROPIC_API_KEY preferred, then OPENAI_API_KEY, then
   GEMINI_API_KEY).

2. Deterministic template fallback (used when no key is set, or the LLM
   call fails/times out): renders the same structured facts as clean
   bulleted English directly. No network call, cannot fail from a bad key
   or quota limit -- this is the path that guarantees the copilot never
   goes down during judging.

Both paths are scoped to: (a) a small fixed project glossary, and (b) the
structured result of whichever module produced the thing being explained.
Neither path answers open-ended financial advice questions.
"""
import os
import json

# Anything outside this system's actual domain (regulatory rules, general
# financial/legal advice, unrelated topics) gets an explicit "not something I
# can answer" rather than a guessed answer. This list is deliberately broad --
# false positives here (refusing something borderline) are far cheaper than
# false negatives (answering a regulatory/legal question as if grounded).
OUT_OF_SCOPE_MARKERS = [
    "rbi", "reserve bank", "regulation", "regulatory", "law", "legal", "illegal",
    "compliant", "compliance", "certified", "certification", "sebi", "income tax",
    "gst", "court", "lawsuit", "sue", "sued", "police", "fir", "invest", "stock",
    "mutual fund", "crypto", "loan", "credit score", "cibil", "insurance",
    "should i buy", "should i sell", "personal advice", "medical", "diagnos",
]

GLOSSARY_KB = {
    "rto": "Return to Origin (RTO): an order that is returned to the merchant before or at delivery -- "
           "common with Cash on Delivery (COD) orders where the customer refuses or is unreachable.",
    "chargeback": "A forced transaction reversal initiated by the cardholder's issuing bank, under a "
                  "card network's dispute reason code, that a merchant can contest with evidence.",
    "representment": "The process of a merchant contesting a chargeback by submitting evidence to the "
                      "card network / issuing bank arguing the transaction was legitimate.",
    "abuse ring": "A cluster of accounts that share identifying signals (device, IP, delivery address) "
                  "in a pattern suggestive of one person or group operating multiple accounts to exploit "
                  "promotions, referral bonuses, or return policies.",
    "3ds": "3D-Secure: a card-payment authentication step (OTP or similar) that shifts fraud liability "
           "toward the issuing bank when successfully completed.",
    "avs": "Address Verification System: a check comparing the billing address given at checkout against "
           "the address on file with the card issuer.",
    "false positive": "A case the system flagged as risky that was actually legitimate -- the cost of "
                       "over-flagging is unnecessary friction/review on a good order.",
    "false negative": "A genuinely risky case the system failed to flag -- the cost of under-flagging is "
                       "the loss (fraud, missed return signal, etc.) going undetected.",
    "audit trail": "The permanent log of every flag/score this system produces, including which module "
                   "made the call, what evidence it used, and when -- kept separate from the live dashboard.",
}

SYSTEM_INSTRUCTION = (
    "You are a risk-explanation assistant for a merchant fraud/returns/chargeback tool. "
    "You may ONLY describe the specific structured facts given to you below -- scores, thresholds, "
    "evidence flags, and glossary definitions. Do not invent additional numbers, claims, or financial "
    "advice. Do not speculate beyond the given facts. Do not answer questions about legal, regulatory, "
    "tax, investment, or medical matters, or anything outside explaining this project's own risk "
    "scores and evidence -- if asked, say plainly that it's outside what this demo covers. "
    "Keep the answer to 3-5 short sentences, plain language, suitable for someone with no financial "
    "background."
)

OUT_OF_SCOPE_REPLY = (
    "That's outside what this demo covers. I can only explain the risk scores, evidence, and "
    "flags produced by this project's own fraud/return/abuse-ring/chargeback models -- I'm not able "
    "to give regulatory, legal, tax, investment, or other financial advice. Any recommendation you see "
    "here comes from this project's model and policy logic, not from a verified external rule."
)


def _is_out_of_scope(query_lower: str) -> bool:
    return any(marker in query_lower for marker in OUT_OF_SCOPE_MARKERS)


def _wants_definition(query_lower: str) -> bool:
    """Distinguish a glossary lookup ('what is RTO?') from a question about
    a specific live result ('why is this transaction 94% risk?') even when
    both happen to mention a glossary term."""
    return any(p in query_lower for p in ["what is", "what's", "define", "meaning of", "explain the term"])


def _try_llm_call(query: str, grounding_facts: dict) -> str | None:
    """Attempt a real LLM call using whichever provider key is configured.
    Returns the reply text, or None if no key is set or the call fails
    (caller falls back to the deterministic template in either case)."""
    prompt = (
        f"{SYSTEM_INSTRUCTION}\n\n"
        f"Structured facts (the only source of truth):\n{json.dumps(grounding_facts, indent=2)}\n\n"
        f"User question: {query}"
    )

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_key)
            resp = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip() or None
        except Exception:
            return None

    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        try:
            import requests
            r = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_key}"},
                json={"model": "gpt-4o-mini", "max_tokens": 300,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=10,
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip() or None
        except Exception:
            return None

    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        try:
            import requests
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}",
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=10,
            )
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip() or None
        except Exception:
            return None

    return None  # no provider key configured


def _template_fallback(context_result: dict | None) -> str:
    """Deterministic, network-free explanation from the same structured facts."""
    if not context_result:
        return ("I'm the Aegis Copilot. Ask me about RTO, chargebacks, abuse rings, or 3DS -- "
                "or select a scored transaction/dispute/cluster and I'll explain the result.")

    lines = []
    if "score" in context_result:
        lines.append(f"Risk score: {context_result['score']:.0%} ({context_result.get('risk_level', 'n/a')} risk).")
        factors = context_result.get("contributing_factors", [])
        if factors:
            lines.append("Contributing factors:")
            for f in factors:
                lines.append(f"  - {f.get('feature')}: {f.get('value')} ({f.get('impact')})")
        lines.append(f"Recommended action: {context_result.get('recommended_action', 'n/a')}")
    elif "win_probability" in context_result:
        lines.append(f"Estimated dispute win-likelihood: {context_result['win_probability']:.0%}.")
        if context_result.get("evidence_present"):
            lines.append("Evidence present: " + "; ".join(context_result["evidence_present"]))
        if context_result.get("evidence_missing"):
            lines.append("Evidence missing: " + "; ".join(context_result["evidence_missing"]))
        lines.append(f"Recommendation: {context_result.get('recommendation', 'n/a')}")
    elif "in_ring" in context_result:
        if context_result["in_ring"]:
            lines.append(f"This account is part of a cluster of {context_result.get('cluster_size')} accounts "
                          f"sharing identifiers: {', '.join(context_result.get('shared_entities', []))}.")
        else:
            lines.append("No shared-identity signal was found for this account.")
        lines.append(f"Recommended action: {context_result.get('recommended_action', 'n/a')}")
    else:
        lines.append("Here is the result: " + json.dumps(context_result))

    return "\n".join(lines)


def explain_risk(query: str, context_result: dict | None = None) -> dict:
    """Intent routing, in priority order:

    1. Out-of-scope (regulatory/legal/financial-advice/unrelated) -> explicit
       refusal, regardless of whether a result is selected. This is checked
       FIRST and unconditionally -- scope safety should never be skippable
       by having a result open.
    2. A specific live result is selected AND the question isn't a bare
       definition request -> grounded explanation of THAT result (LLM path
       with template fallback). This is checked before glossary so that
       "explain the RTO risk on this transaction" reaches the actual
       transaction's evidence instead of a generic definition.
    3. Glossary definition request -> fixed KB lookup, no LLM needed.
    4. Nothing matched -> generic scoped intro, not a guess.
    """
    query_lower = query.lower()

    if _is_out_of_scope(query_lower):
        return {"reply": OUT_OF_SCOPE_REPLY, "source": "scope_refusal", "grounded": True,
                "intent": "out_of_scope"}

    if context_result and not _wants_definition(query_lower):
        llm_reply = _try_llm_call(query, context_result)
        if llm_reply:
            return {"reply": llm_reply, "source": "llm", "grounded": True, "intent": "result_explanation"}
        return {"reply": _template_fallback(context_result), "source": "template_fallback",
                "grounded": True, "intent": "result_explanation"}

    for key, explanation in GLOSSARY_KB.items():
        if key in query_lower:
            return {"reply": explanation, "source": "glossary", "grounded": True, "intent": "glossary"}

    return {"reply": _template_fallback(context_result), "source": "template_fallback",
            "grounded": True, "intent": "unmatched"}
