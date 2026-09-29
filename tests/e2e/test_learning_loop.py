"""The demo, as a test: the learning loop through the HTTP API.

Hindsight is the stateful, deliberately LEAKY fake (recall returns every vendor's memories).
Groq is OVER-EAGER: it answers APPROVED at 0.95 no matter what. The recommendations below must
come out right anyway, and identically when Groq fails on every call.

    pytest tests/e2e -s        prints the transcript (it doubles as the demo script)
"""

import pytest

from tests.conftest import body
from tests.fakes import llm_json

REASON = "Contract price changed from ₹500 to ₹550 effective 2026-07-01"
NO_MEMORY = "No relevant verified historical memory found"


def say(text=""):
    print(text)


def show(step, data):
    say(f"\n── Step {step}: {data['invoice_id']} · {data['vendor']} ──")
    for exc in data["exceptions"]:
        say(f"   rule engine : {exc['type']} {exc['severity']} ({exc['reason']})")
    for m in data["hindsight_memories"]:
        say(f"   memory      : {m['vendor']} {m['decision']} at ₹{m['invoice_price']:g}, reason \"{m['human_reason']}\"")
    if not data["hindsight_memories"]:
        say("   memory      : none for this vendor")
    say(f"   reflection  : {data['reflection'] or '-'}")
    say(f"   evidence    : {data['evidence_level']}   memory_status: {data['memory_status']}")
    say(f"   RECOMMEND   : {data['recommendation']} ({data['confidence']:.0%})")
    say(f"   why         : {data['explanation']}")


@pytest.mark.parametrize("groq_mode", ["over-eager", "down"])
def test_learning_loop(client, fake_hindsight, fake_groq, groq_mode):
    if groq_mode == "over-eager":
        fake_groq.reply = llm_json("APPROVED", 0.95, "Everything looks fine to me.")
    else:
        fake_groq.fail_always = "timeout"
    say(f"\n════ Hindsight AP learning loop (Groq {groq_mode}) ════")
    process = lambda *a, **k: client.post("/api/v1/invoice/process", json=body(*a, **k)).json()  # noqa: E731

    # 1. ABC Pharma bills ₹550 against a ₹500 PO. Nothing in memory.
    step1 = process("INV001")
    show(1, step1)
    assert step1["exception_detected"]["type"] == "PRICE_MISMATCH"
    assert step1["hindsight_memories"] == [] and step1["recommendation"] == "NEEDS_REVIEW"
    assert NO_MEMORY in step1["explanation"]
    assert fake_hindsight.calls_to("retain") == []

    # 2. The reviewer approves, with a reason. That decision, and only that, is retained.
    stored = client.post("/api/v1/invoice/store-decision",
                         json={"invoice_id": "INV001", "human_decision": "APPROVED", "human_reason": REASON}).json()
    say(f"\n── Step 2: reviewer APPROVED INV001: \"{REASON}\" → retained={stored['retained']} ({stored['memory_id']})")
    assert stored["retained"] is True
    [retain] = fake_hindsight.calls_to("retain")
    assert retain["retain_async"] is False
    for fact in ("ABC Pharma", "550", "APPROVED", REASON):
        assert fact in retain["content"]

    # 3. ABC Pharma again, same ₹550. Hindsight recalls the decision; the agent approves and says why.
    step3 = process("INV002")
    show(3, step3)
    [memory] = step3["hindsight_memories"]
    assert (memory["vendor"], memory["decision"], memory["human_reason"]) == ("ABC Pharma", "APPROVED", REASON)
    [reflect] = fake_hindsight.calls_to("reflect")
    assert "ABC Pharma" in reflect["query"]
    assert (step3["evidence_level"], step3["recommendation"]) == ("VERIFIED_MATCH", "APPROVED")
    assert "INV001" in step3["explanation"] and REASON in step3["explanation"]

    # 4. XYZ Pharma, same ₹550. The leaky recall hands over ABC's memory; it must be dropped.
    step4 = process("INV003", vendor="XYZ Pharma", quantity=50)
    show(4, step4)
    assert step4["hindsight_memories"] == []
    assert len(fake_hindsight.calls_to("reflect")) == 1  # not called again
    if groq_mode == "over-eager":
        assert "ABC Pharma" not in fake_groq.prompt
    assert step4["recommendation"] == "NEEDS_REVIEW" and NO_MEMORY in step4["explanation"]

    # 5. ABC Pharma at ₹600: the ₹550 approval is context, not evidence.
    step5 = process("INV004", invoice_price=600)
    show(5, step5)
    assert [m["invoice_price"] for m in step5["hindsight_memories"]] == [550]
    assert (step5["evidence_level"], step5["recommendation"]) == ("NO_EVIDENCE", "NEEDS_REVIEW")

    if groq_mode == "down":
        for step in (step1, step3, step4, step5):
            assert "LLM was unavailable" in step["explanation"]
    say(f"\n   Recommendations: {[s['recommendation'] for s in (step1, step3, step4, step5)]}")
