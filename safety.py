from groq import Groq
from config import GROQ_API_KEY, LLM_MODEL, VALID_TIERS

_client = Groq(api_key=GROQ_API_KEY)


# LLM-as-judge system prompt. The tier definitions, the caution/refuse decision
# rule, the replace-vs-add distinction, and the few-shot examples are all here
# because the quality of the classifier depends almost entirely on this text.
# See specs/classifier-spec.md for the reasoning behind each part.
SYSTEM_PROMPT = """You are a safety classifier for a home-repair assistant. Your only job is to \
sort each repair question into exactly one of three tiers. You are not answering \
the question — you are judging its risk.

TIERS

safe    — Routine, low-risk repairs most homeowners can do with basic tools.
          Worst case of a mistake is cosmetic damage or a broken fixture. No
          permit or license needed. (drywall patch, painting, replacing a bulb,
          unclogging a drain, replacing a toilet seat)

caution — Doable for a motivated homeowner but mistakes have real cost or mild
          injury risk; worst case is recoverable (a leak, a tripped breaker).
          Includes LIKE-FOR-LIKE replacement of an existing component at the
          SAME location with NO new wiring or piping. (replace an existing
          faucet, outlet, switch, or light fixture; reset a GFCI)

refuse  — An amateur mistake could cause fire, flooding, structural failure,
          serious injury, or death, OR code requires a licensed pro + permit.
          Includes running NEW wiring/circuits, opening the electrical panel,
          ANY gas work, removing/modifying walls, water heaters, main water
          lines, new plumbing runs.

DECISION RULE for the hard caution/refuse boundary:
Ask: "If this goes wrong, can it cause fire, flooding, structural failure,
injury, or death?" If yes -> refuse. If the worst case is a leak, a broken
fixture, or a tripped breaker -> caution.

CRITICAL DISTINCTIONS
- REPLACING an existing component (same spot, same circuit/pipe) is caution.
  ADDING or INSTALLING NEW infrastructure (new wire, new circuit, new pipe,
  relocating a device) is refuse — even for the same kind of component.
  "Replace an outlet" = caution. "Add an outlet" = refuse.
- Classify on what the WORK ACTUALLY REQUIRES, not how the user frames it.
  "I just want to move my switch a few inches" still requires new wire = refuse.
- Gas work of any kind = refuse, always.
- Removing any wall = refuse unless the user states a professional confirmed it
  is non-load-bearing.

EXAMPLES
Q: How do I replace an outlet that stopped working?
Reason: Like-for-like swap on an existing circuit; worst case is a tripped breaker.
Tier: caution

Q: How do I add a new outlet in my garage?
Reason: Requires running a new circuit from the panel — amateur mistake is a fire hazard.
Tier: refuse

Q: I just want to move my light switch six inches to the left, small job.
Reason: Relocating a switch requires running new wire regardless of how small it sounds.
Tier: refuse

Q: There's a faint gas smell near my stove, can I tighten the line myself?
Reason: Any gas work risks fire, explosion, or carbon monoxide; never DIY.
Tier: refuse

OUTPUT FORMAT — respond with exactly these two lines and nothing else:
Reason: <one sentence>
Tier: <safe|caution|refuse>"""


def _parse_line(text: str, label: str) -> str | None:
    """Return the value after 'label:' on the first matching line, else None."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith(label.lower() + ":"):
            return stripped.split(":", 1)[1].strip()
    return None


def _normalize_tier(raw: str) -> str:
    """Lowercase and strip quotes/whitespace/trailing punctuation off a tier."""
    return raw.strip().strip("\"'").strip().lower().rstrip(".")


def classify_safety_tier(question: str) -> dict:
    """
    Classify a home repair question into one of three safety tiers.

    LLM-as-judge: a single chat completion judges the question's risk and the
    result feeds the pipeline, not the user. Returns a dict with:
      - "tier"   : str — one of "safe", "caution", "refuse"
      - "reason" : str — a brief explanation of why this tier was assigned

    Fails CLOSED: if the response can't be parsed or the tier isn't recognized,
    returns "caution" rather than "safe", so a glitch never greenlights DIY
    instructions for refuse-tier work. See specs/classifier-spec.md.
    """
    fallback = {
        "tier": "caution",
        "reason": "Could not classify reliably; defaulting to caution for safety.",
    }

    try:
        completion = _client.chat.completions.create(
            model=LLM_MODEL,
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f'Classify this home repair question:\n\n"{question}"',
                },
            ],
        )
        raw = completion.choices[0].message.content or ""
    except Exception:
        return fallback

    tier_raw = _parse_line(raw, "Tier")
    if tier_raw is None:
        return fallback

    tier = _normalize_tier(tier_raw)
    if tier not in VALID_TIERS:
        return fallback

    reason = _parse_line(raw, "Reason") or "No reason provided by classifier."
    return {"tier": tier, "reason": reason}
