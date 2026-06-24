# Spec: `classify_safety_tier()`

**File:** `safety.py`
**Status:** Spec incomplete — fill in all blank fields before implementing

---

## Purpose

Determine whether a home repair question is safe to answer directly, requires a cautionary response, or should be refused with a referral to a licensed professional.

---

## Input / Output Contract

**Input:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `question` | `str` | The user's home repair question |

**Output:** `dict`

| Key | Type | Description |
|-----|------|-------------|
| `"tier"` | `str` | One of: `"safe"`, `"caution"`, `"refuse"` |
| `"reason"` | `str` | One sentence explaining why this tier was assigned |

---

## Design Decisions

*Complete the fields below before writing any code. Use your AI tool in Plan or Ask mode to help you reason through what belongs here — but the decisions are yours.*

---

### Tier definitions

*Write a one-sentence definition for each tier that is precise enough to use as part of your classification prompt. Vague definitions produce inconsistent classifications.*

**safe:**
```
Routine maintenance or low-risk repairs most homeowners can complete with basic
tools, where the worst realistic outcome of a mistake is cosmetic damage or a
broken fixture — never injury, fire, or flooding. No permit or license required.
```

**caution:**
```
Repairs a motivated homeowner can do with care, involving water or electrical
systems where a mistake has real cost or mild injury risk, but the worst case is
recoverable — a leak, a broken fixture, or a tripped breaker. This includes
like-for-like swaps of an existing component at the same location with no new
wiring or piping (e.g. replacing an existing outlet, switch, or faucet).
```

**refuse:**
```
Repairs where an amateur mistake can cause fire, flooding, structural failure,
serious injury, or death — or where local code requires a licensed professional
and a permit. This includes any work that runs NEW wiring or piping, opens the
electrical panel, touches gas, or removes/modifies a wall. Do not provide DIY
instructions.
```

---

### Classification approach

*How will the LLM classify the question? Will you give it just the tier definitions, or also examples (few-shot)? Will you ask it to reason step-by-step before naming the tier, or output the tier directly?*

*Consider: what happens when a question is genuinely ambiguous — e.g., "can I replace my own outlets?" Which tier should that land in, and how does your approach handle questions at the boundary?*

```
Definitions + a few targeted few-shot examples + reason-before-classify.

- Definitions alone leave the caution/refuse boundary to the model's judgment,
  which drifts. So I include 3-4 few-shot examples chosen specifically to teach
  the boundary, not random ones: the replace-vs-add outlet pair, a "framing
  doesn't change the tier" case (move a switch 6 inches), and a gas case.
- I ask the model to state a one-line reason BEFORE it names the tier. Forcing
  the reason first makes it apply the boundary rule explicitly instead of
  pattern-matching to a word like "outlet," which improves the hard cases.

Ambiguity handling: when a question is under-specified ("can I replace my own
outlets?"), classify on the most likely intent given the wording. "Replace" an
existing outlet reads as a like-for-like swap -> caution. If wording implies new
infrastructure ("add", "install a new", "run", "move") -> refuse. When it's
genuinely impossible to tell which, fail toward the safer (higher) tier.
```

---

### Output format

*How will the LLM communicate the tier and reason back to you? Describe the exact text format you'll ask it to use, so you can parse it reliably.*

*The format you used in Lab 3 (`Label: X / Reasoning: Y`) is a reasonable starting point, but you're not required to use it. Whatever you choose, you'll need to parse it in code — so consider how much variation the LLM might introduce and how you'll handle that.*

```
Two labeled lines, reason first so the model "thinks" before committing:

    Reason: <one sentence>
    Tier: <safe|caution|refuse>

Parsing plan:
- Find the line starting with "Tier:" (case-insensitive), take the text after
  the colon.
- Normalize: lowercase, strip whitespace, strip surrounding quotes and any
  trailing punctuation (a period, etc.).
- Validate against VALID_TIERS. Only a clean match is accepted.
- Pull the "Reason:" line the same way for the reason string.

I chose plain labeled text over JSON because it's simpler to parse robustly and
the model rarely breaks it; if I later wanted stricter structure I'd switch to
JSON and json.loads. Putting Reason before Tier is deliberate — it nudges the
model to justify, then label.
```

---

### Prompt structure

*Write the actual prompt you'll use — both the system message and the user message. Don't describe it — write it. Vague prompt descriptions produce vague prompts, which produce inconsistent classifications.*

**System message:**
```
You are a safety classifier for a home-repair assistant. Your only job is to
sort each repair question into exactly one of three tiers. You are not answering
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
Tier: <safe|caution|refuse>
```

**User message:**
```
Classify this home repair question:

"{question}"
```

---

### Caution/refuse boundary

*The most consequential classification decision is whether a question lands in "caution" or "refuse." Write down your rule for this boundary — one sentence. Then give two examples of questions that sit close to the line and explain which side they fall on and why.*

```
RULE: If a mistake during the repair could cause fire, flooding, structural
failure, injury, or death — or the work creates NEW electrical/plumbing/gas
infrastructure or opens the panel — it is refuse; if the worst realistic outcome
is a leak, a broken fixture, or a tripped breaker, it is caution.

Example 1 — "Can I replace a GFCI outlet that won't reset?"  -> caution.
Like-for-like swap of an existing device on an existing circuit at the same
location. No new wire, no panel work. Worst case is a tripped breaker — recoverable.

Example 2 — "Can I install a new outlet behind my TV?"  -> refuse.
"New" means running a new circuit/wire from the panel to a location that has
none. An amateur wiring mistake creates a hidden fire hazard. The component is
the same as Example 1, but the WORK is new infrastructure, which crosses the line.
```

---

### Fallback behavior

*What does your function return if the LLM response can't be parsed — e.g., if it produces free-form prose instead of your expected format? What happens when tier validation against `VALID_TIERS` fails?*

*Note: failing open (returning "safe" as a fallback) is more dangerous than failing closed (returning "caution"). Which makes more sense here, and why?*

```
Fail CLOSED. If the "Tier:" line is missing, or the parsed value isn't in
VALID_TIERS, or the API call raises, the function returns:

    {"tier": "caution", "reason": "Could not classify reliably; defaulting to
     caution for safety."}

Why "caution" and not "safe": a wrong "safe" tells the downstream responder it's
fine to give full DIY instructions for what might be panel or gas work — the
exact failure the safety layer exists to prevent. "caution" makes the responder
add guardrails, which is the harmless wrong answer. I default to caution rather
than refuse so a parse glitch doesn't block a genuinely simple question; caution
is the conservative-but-still-useful middle. (Could be argued up to refuse for a
stricter system — documented as a deliberate choice.)
```

---

## Implementation Notes

*Fill this in after implementing, before moving to Milestone 2.*

**One classification that surprised you — question, tier you expected, tier it returned, and why:**

```
"Replace a water heater" -> I half-expected caution (it's a "replacement," and my
caution definition treats like-for-like swaps as caution). It returned refuse,
correctly. The reason: a water heater needs a permit in most jurisdictions and a
mishandled pressure-relief valve can explode — so it's the worst case (explosion),
not the word "replace," that decides the tier. Good reminder that the
replace-vs-add rule is an electrical heuristic, not a universal override of the
core "can it cause fire/flood/injury?" question.
```

**One prompt change you made after seeing the first few outputs, and what it fixed:**

```
First draft gave the model definitions only and let it output the tier directly.
On the framing-trap question ("move my switch six inches, tiny job") it wobbled
toward caution because the wording sounds minor. Two changes fixed it: (1) added
the explicit "classify on what the WORK ACTUALLY REQUIRES, not how the user frames
it" rule plus that exact case as a few-shot example, and (2) switched the output
format to put Reason BEFORE Tier so the model justifies against the rule before
committing to a label. After that, the framing trap reliably lands in refuse.
```
