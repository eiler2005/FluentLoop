from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Final


@dataclass(frozen=True)
class L1Hit:
    rule_id: str
    category: str
    matched_text: str
    suggestion: str
    explanation: str
    mistake_type: str

    def as_feedback_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class L1Rule:
    rule_id: str
    category: str
    pattern: re.Pattern[str]
    suggestion: str
    explanation: str
    mistake_type: str


def _rule(
    rule_id: str,
    category: str,
    pattern: str,
    suggestion: str,
    explanation: str,
    mistake_type: str,
) -> L1Rule:
    return L1Rule(
        rule_id,
        category,
        re.compile(pattern, re.IGNORECASE),
        suggestion,
        explanation,
        mistake_type,
    )


RULES: Final[tuple[L1Rule, ...]] = (
    _rule(
        "l1_make_mistake",
        "verb_noun_calque",
        r"\bdo(?:ing|ne)? a mistake\b",
        "make a mistake",
        "Russian often maps 'делать ошибку' too literally.",
        "collocation",
    ),
    _rule(
        "l1_start_business",
        "verb_noun_calque",
        r"\bopen(?:ed|ing)? a business\b",
        "start/launch a business",
        "English normally uses start or launch for a company.",
        "collocation",
    ),
    _rule(
        "l1_do_research",
        "verb_noun_calque",
        r"\bmake(?:s|ing| made)? (?:a )?research\b",
        "do/conduct research",
        "Research is usually a mass noun and takes do/conduct.",
        "collocation",
    ),
    _rule(
        "l1_take_decision",
        "verb_noun_calque",
        r"\btake(?:s|n|ing)? a decision\b",
        "make a decision",
        "For the main FluentLoop business register, make a decision is the default.",
        "collocation",
    ),
    _rule(
        "l1_put_question",
        "verb_noun_calque",
        r"\bput(?:s|ting)? a question\b",
        "ask/raise a question",
        "Question collocates with ask or raise, not put.",
        "collocation",
    ),
    _rule(
        "l1_strong_rain",
        "adjective_noun",
        r"\bstrong rain\b",
        "heavy rain",
        "Rain takes heavy rather than strong.",
        "collocation",
    ),
    _rule(
        "l1_strong_pain",
        "adjective_noun",
        r"\bstrong pain\b",
        "severe pain",
        "Pain is usually severe, acute, or intense.",
        "collocation",
    ),
    _rule(
        "l1_big_price",
        "adjective_noun",
        r"\bbig price\b",
        "high price",
        "Prices are high or low, not big or small.",
        "collocation",
    ),
    _rule(
        "l1_cheap_quality",
        "adjective_noun",
        r"\bcheap quality\b",
        "poor/low quality",
        "Cheap describes price; quality is poor or low.",
        "collocation",
    ),
    _rule(
        "l1_depend_from",
        "preposition",
        r"\bdepend(?:s|ed|ing)? from\b",
        "depend on",
        "Depend takes on in standard English.",
        "preposition",
    ),
    _rule(
        "l1_consist_from",
        "preposition",
        r"\bconsist(?:s|ed|ing)? from\b",
        "consist of",
        "Consist takes of, not from.",
        "preposition",
    ),
    _rule(
        "l1_discuss_about",
        "preposition",
        r"\bdiscuss(?:es|ed|ing)? about\b",
        "discuss",
        "Discuss is transitive: discuss the topic.",
        "preposition",
    ),
    _rule(
        "l1_participate_at",
        "preposition",
        r"\bparticipate(?:s|d|ing)? at\b",
        "participate in",
        "Participate takes in for activities and meetings.",
        "preposition",
    ),
    _rule(
        "l1_influence_on",
        "preposition",
        r"\binfluence(?:s|d|ing)? on\b",
        "influence",
        "As a verb, influence is direct: influence the result.",
        "preposition",
    ),
    _rule(
        "l1_actual_current",
        "false_friend",
        r"\bactual (?:version|problem|task|question|state|status)\b",
        "current/latest",
        "Actual usually means real, not current.",
        "lexis",
    ),
    _rule(
        "l1_normal_ok",
        "false_friend",
        r"\bit is normal\b",
        "it is fine/acceptable",
        "Normal can sound colder than the Russian 'нормально'.",
        "register",
    ),
    _rule(
        "l1_technic",
        "false_friend",
        r"\btechnic\b",
        "technique/technology/equipment",
        "Technic is rarely the right noun in business English.",
        "lexis",
    ),
    _rule(
        "l1_economy_science",
        "false_friend",
        r"\bstudy economy\b",
        "study economics",
        "Economics is the field of study; economy is the system.",
        "lexis",
    ),
    _rule(
        "l1_politics_policy",
        "false_friend",
        r"\bcompany politics\b",
        "company policy",
        "Policy is a rule/position; politics is power dynamics.",
        "lexis",
    ),
    _rule(
        "l1_present_perfect_yesterday",
        "tense",
        r"\bhave \w+(?:ed|en)? .{0,24}\byesterday\b",
        "past simple with yesterday",
        "Finished past time markers normally need past simple.",
        "tense",
    ),
    _rule(
        "l1_if_would_have",
        "tense",
        r"\bif I would have\b",
        "if I had",
        "Third conditional uses if + past perfect.",
        "tense",
    ),
    _rule(
        "l1_if_we_would_have",
        "tense",
        r"\bif we would have\b",
        "if we had",
        "Third conditional uses if + past perfect.",
        "tense",
    ),
    _rule(
        "l1_missed_past_perfect",
        "tense",
        r"\bbefore we (?:fixed|released|started), we (?:found|saw|noticed)\b",
        "had + past participle for earlier past",
        "Earlier past events often need past perfect in narratives.",
        "tense",
    ),
    _rule(
        "l1_abstract_zero_article",
        "articles",
        r"^(?:Project|Product|Management|Architecture|Infrastructure) is\b",
        "the/a + noun when specific",
        "Russian L1 often drops articles before specific abstract nouns.",
        "articles",
    ),
    _rule(
        "l1_generic_the",
        "articles",
        r"\bthe developers in general\b",
        "developers in general",
        "Generic plurals usually do not take the.",
        "articles",
    ),
    _rule(
        "l1_in_university",
        "articles",
        r"\bin the university\b",
        "at university / at the university",
        "Institutions need article choice based on meaning.",
        "articles",
    ),
    _rule(
        "l1_bare_imperative_email",
        "pragmatics",
        r"^(?:Send|Give|Fix|Check|Explain|Do)\b",
        "Could you / Please / It would help if...",
        "Bare imperatives can sound too direct in workplace English.",
        "pragmatics",
    ),
    _rule(
        "l1_insufficient_hedging",
        "pragmatics",
        r"\byou must\b",
        "you might need to / it may be worth",
        "Must can sound over-direct in stakeholder contexts.",
        "pragmatics",
    ),
    _rule(
        "l1_of_course",
        "pragmatics",
        r"\bof course\b",
        "sure / absolutely / that makes sense",
        "Of course can sound impatient in some business replies.",
        "pragmatics",
    ),
    _rule(
        "l1_in_my_opinion",
        "pragmatics",
        r"\bin my opinion\b",
        "I would argue / my read is",
        "In my opinion is often overused where a sharper stance marker works better.",
        "pragmatics",
    ),
)


def detect_l1_interference(text: str, *, limit: int = 5) -> list[L1Hit]:
    hits: list[L1Hit] = []
    for rule in RULES:
        match = rule.pattern.search(text)
        if match is None:
            continue
        hits.append(
            L1Hit(
                rule_id=rule.rule_id,
                category=rule.category,
                matched_text=match.group(0),
                suggestion=rule.suggestion,
                explanation=rule.explanation,
                mistake_type=rule.mistake_type,
            )
        )
        if len(hits) >= limit:
            break
    return hits
