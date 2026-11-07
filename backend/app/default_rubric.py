"""Seed only. Scoring, evidence and model logic never depend on these IDs."""

from app.contracts import RubricDraft


def initial_rubric() -> RubricDraft:
    rows = [
        (
            "C01",
            "Start/intent",
            "Установление контакта",
            "binary",
            10,
            False,
            "In the first operator response, greet in the client's language AND introduce self.",
            "",
        ),
        (
            "C02",
            "Start/intent",
            "Выявление потребности",
            "binary",
            15,
            True,
            "Use known details and ask for missing ones before responding.",
            "Enough details were available from the outset.",
        ),
        (
            "C03",
            "Safety/solution",
            "Идентификация",
            "binary",
            20,
            True,
            "Verify identity BEFORE revealing sensitive details or performing protected actions.",
            "The request did not require identity verification, e.g. general pricing.",
        ),
        (
            "C04",
            "Safety/solution",
            "Корректная и полная консультация",
            "numeric_scale",
            20,
            True,
            "20: all material questions solved or valid next step; 15: primary solved with minor omission; "
            "10: substantive issue remains; 5: generic hint with no clear action; "
            "0: no substantive answer or materially wrong advice. Without reliable policy knowledge, "
            "mark uncertainty/human review; never invent policy citations.",
            "Conversation ended before the customer stated a request; no other N/A reason is legal.",
        ),
        (
            "C05",
            "Conduct/closing",
            "Эмпатия и клиентоориентированность",
            "binary",
            15,
            False,
            "Be polite and respond to the specific frustration or inconvenience when expressed.",
            "",
        ),
        (
            "C06",
            "Conduct/closing",
            "Управление диалогом, скорость и грамотность",
            "numeric_scale",
            15,
            False,
            "10: clear/coherent with wait warning where appropriate; 7: one notable problem but "
            "understandable; 4: customer has to re-ask due to presentation/order; 0: contradictory/incoherent. "
            "Do not score a three-minute threshold, tags, attachments, intonation or diction.",
            "",
        ),
        (
            "C07",
            "Conduct/closing",
            "Завершение",
            "binary",
            5,
            True,
            "Summarize or offer further help AND say goodbye.",
            "Conversation ended before the operator had an opportunity to close.",
        ),
        (
            "C08",
            "Gross errors",
            "Грубые ошибки",
            "violation",
            0,
            False,
            "Yes ONLY for customer insults, paid service outside the company, or confidential disclosure. "
            "An independent violation flag; never points or automatic score zero.",
            "",
        ),
    ]
    criteria = []
    for cid, section, name, kind, weight, allows_na, instructions, na_rule in rows:
        scale = [0, 5, 10, 15, 20] if cid == "C04" else [0, 4, 7, 10]
        criteria.append(
            {
                "id": cid,
                "name": name,
                "section": section,
                "type": kind,
                "weight": weight,
                "allows_na": allows_na,
                "na_rule": na_rule,
                "description": name,
                "instructions": instructions,
                "allowed_values": scale if kind == "numeric_scale" else ["yes", "no"],
            }
        )
    return RubricDraft.model_validate({"name": "CQA initial checklist", "criteria": criteria})
