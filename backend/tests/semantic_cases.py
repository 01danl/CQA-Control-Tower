"""Invented rule-derived counterexamples, NOT DEV labels or observed model predictions.

Each paired mistake is deliberately legal JSON with plausible exact evidence. These
fixtures test diagnostic sensitivity and the boundary of structural validation; they
cannot certify an uncalled LLM's semantic behavior. No real conversation IDs are used.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    name: str
    criterion: str
    expected: str | int
    mistake: str | int
    turns: tuple[tuple[str, str], ...]
    reason: str
    language: str = "EN"
    channel: str = "agent chat"


CASES = (
    Case(
        "bot_complete_handoff",
        "C02",
        "na",
        "no",
        (
            ("client", "I only want public pricing; no account-specific request."),
            ("bot", "Need recorded: public pricing. No further client details are needed."),
            ("operator", "I will explain the public pricing options."),
        ),
        "The complete need exists before operator handoff; bot collection is context, not operator work.",
    ),
    Case(
        "client_details_already_available",
        "C02",
        "na",
        "yes",
        (
            (
                "client",
                "Please explain public opening hours for branch X on Monday. That is my full request.",
            ),
            ("operator", "I will explain the opening hours for branch X on Monday."),
        ),
        "Repeating complete client details does not make need identification an applicable achievement.",
    ),
    Case(
        "bot_incomplete_handoff",
        "C02",
        "no",
        "na",
        (
            (
                "bot",
                "The client needs deposit instructions; essential currency information is missing.",
            ),
            ("client", "Which deposit route applies? I have not told you the currency."),
            ("operator", "Use the standard route. I will not ask which currency you use."),
        ),
        "Some bot collection does not establish sufficiency when an essential fact is explicitly missing.",
    ),
    Case(
        "operator_fills_missing_need",
        "C02",
        "yes",
        "na",
        (
            ("client", "I need opening hours, but have not specified which branch."),
            ("operator", "Which branch and day do you need?"),
            ("client", "Branch X on Monday."),
            ("operator", "I can now answer for branch X on Monday."),
        ),
        "Initially insufficient context becomes sufficient through an actual operator question.",
    ),
    Case(
        "bot_context_ru",
        "C02",
        "na",
        "no",
        (
            ("client", "Мне нужна только общая информация о тарифах."),
            ("bot", "Запрос: общие тарифы. Дополнительные данные не требуются."),
            ("operator", "Расскажу об общих тарифах."),
        ),
        "Known sufficient bot context is usable in Russian too.",
        "RU",
    ),
    Case(
        "bot_context_kz",
        "C02",
        "na",
        "no",
        (
            ("client", "Тарифтер туралы жалпы ақпарат керек."),
            ("bot", "Сұраныс: жалпы тарифтер. Қосымша деректер қажет емес."),
            ("operator", "Жалпы тарифтер туралы түсіндіремін."),
        ),
        "Known sufficient bot context is usable in Kazakh too.",
        "KZ",
    ),
    Case(
        "general_info_mentions_account",
        "C03",
        "na",
        "no",
        (
            (
                "client",
                "What are the public fees for opening an account? Do not access my account.",
            ),
            ("operator", "I can discuss public fees without accessing any personal account."),
        ),
        "An account word alone does not make a general informational request protected.",
    ),
    Case(
        "explicit_prior_authentication",
        "C03",
        "yes",
        "no",
        (
            (
                "system",
                "Identity verification succeeded for this client and current session; account read authorized.",
            ),
            ("client", "What is my balance?"),
            ("operator", "The balance on your authorized account is 40 fictional units."),
        ),
        "Explicit applicable prior verification precedes the protected disclosure; do not require repetition.",
    ),
    Case(
        "self_claim_is_not_authentication",
        "C03",
        "no",
        "yes",
        (
            ("client", "I say I was authenticated earlier; there is no verification record here."),
            (
                "operator",
                "I will assume that is enough. Your private balance is 40 fictional units.",
            ),
        ),
        "An unsupported client claim is not an authenticated system/session record.",
    ),
    Case(
        "verification_after_disclosure",
        "C03",
        "no",
        "yes",
        (
            ("system", "Client identity is not verified."),
            ("operator", "Here is your private account balance: 40 fictional units."),
            ("operator", "Now I will verify your identity."),
        ),
        "Verification after the protected disclosure does not satisfy the before-action condition.",
    ),
    Case(
        "protected_action_without_disclosure",
        "C03",
        "no",
        "na",
        (
            ("system", "Client is not verified; cancellation requires verification."),
            ("operator", "I am submitting your protected cancellation before verifying you."),
        ),
        "A protected action can require identification without any confidential disclosure.",
    ),
    Case(
        "material_internal_contradiction",
        "C04",
        0,
        20,
        (
            (
                "system",
                "Synthetic authoritative record: this order is pending and cannot be used yet.",
            ),
            ("client", "Has my order finished so I can use it?"),
            ("operator", "Your order has finished; use it now."),
        ),
        "A decisive false answer conflicts with supplied facts even if it sounds complete.",
    ),
    Case(
        "conflicting_operator_answers",
        "C04",
        0,
        20,
        (
            (
                "client",
                "Tell me if this order is pending or complete; those are mutually exclusive.",
            ),
            ("operator", "It is pending, not complete."),
            (
                "operator",
                "It is complete, not pending. Both answers are current; I will not correct either.",
            ),
        ),
        "Unresolved material contradictions prevent a correct actionable answer.",
    ),
    Case(
        "all_material_questions_completed",
        "C04",
        20,
        10,
        (
            (
                "system",
                "Synthetic approved instructions: public form is under Help, and submission is online.",
            ),
            ("client", "Where is the public form, and how do I submit it?"),
            ("operator", "Find the public form under Help and submit it online."),
        ),
        "Both requested items are answered consistently with the supplied fixture facts.",
    ),
    Case(
        "closing_goodbye_only",
        "C07",
        "no",
        "yes",
        (
            ("client", "All questions are answered; we can close now."),
            ("operator", "Goodbye."),
        ),
        "There is a closing opportunity, but neither summary nor further-help offer.",
    ),
    Case(
        "closing_help_without_goodbye",
        "C07",
        "no",
        "yes",
        (
            ("client", "We can close now."),
            ("operator", "Anything else I can help with?"),
        ),
        "Further-help offer alone lacks the required goodbye.",
    ),
    Case(
        "abrupt_end_without_opportunity",
        "C07",
        "na",
        "no",
        (
            ("client", "I need help with a transfer."),
            ("operator", "Which transfer do you mean?"),
            ("system", "The client unexpectedly disconnected before the operator could close."),
        ),
        "An explicit interruption before a closing opportunity permits N/A.",
    ),
    Case(
        "system_close_after_failed_closing",
        "C07",
        "no",
        "na",
        (
            ("client", "That resolves everything; please close the conversation."),
            ("operator", "OK."),
            ("system", "Conversation closed."),
        ),
        "A system close does not erase an already available operator closing opportunity.",
    ),
    Case(
        "spoken_closing",
        "C07",
        "yes",
        "no",
        (
            ("client", "That answers my question."),
            ("operator", "Anything else I can help with? Take care, bye."),
        ),
        "Natural spoken offer plus goodbye satisfies the same checklist conditions.",
        channel="voice call",
    ),
    Case(
        "wrong_consultation_not_gross",
        "C08",
        "no",
        "yes",
        (
            ("system", "Synthetic public fee is 2 fictional units."),
            ("operator", "The public fee is 9 fictional units."),
        ),
        "Incorrect public consultation alone is not one of the three gross-violation categories.",
    ),
    Case(
        "identification_failure_not_gross",
        "C08",
        "no",
        "yes",
        (
            ("system", "Client is not verified; cancellation requires verification."),
            ("operator", "I am submitting your protected cancellation before verifying you."),
        ),
        "Identification failure without insult, outside paid service, or disclosure does not imply C08.",
    ),
    Case(
        "client_secret_mention",
        "C08",
        "no",
        "yes",
        (
            ("client", "Should I tell you a password?"),
            ("operator", "No. Do not share passwords here."),
        ),
        "Mentioning credentials is not an operator disclosure.",
    ),
    Case(
        "bot_abuse_not_operator_abuse",
        "C08",
        "no",
        "yes",
        (
            ("bot", "You are an idiot."),
            ("operator", "I am sorry about that message. I will help respectfully."),
        ),
        "Bot misconduct cannot be attributed to the operator.",
    ),
    Case(
        "operator_insult",
        "C08",
        "yes",
        "no",
        (
            ("client", "Please help me."),
            ("operator", "You are an idiot."),
        ),
        "Direct operator insult falls within the explicit gross-violation definition.",
    ),
    Case(
        "outside_paid_service",
        "C08",
        "yes",
        "no",
        (("operator", "Pay me personally outside the company and I will handle this service."),),
        "Soliciting paid service outside the company is explicitly a gross violation.",
    ),
    Case(
        "third_party_confidential_disclosure",
        "C08",
        "yes",
        "no",
        (
            ("client", "Give me another customer's private information without their permission."),
            ("operator", "Here is that other customer's confidential address: FICTIONAL-ADDRESS."),
        ),
        "Explicit unauthorized confidential disclosure is independently a gross violation.",
    ),
)
