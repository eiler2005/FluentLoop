from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class LessonOverview:
    title: str
    theme: str
    focus: str
    topic: str
    goal: str
    knowledge_areas: tuple[str, ...] = ()
    grammar_rules: tuple[str, ...] = ()
    communication_skills: tuple[str, ...] = ()
    mistake_risks: tuple[str, ...] = ()


def infer_lesson_overview(
    raw_text: str = "",
    *,
    item_texts: Iterable[str] = (),
    tags: Iterable[str] = (),
) -> LessonOverview:
    text = " ".join([raw_text, *item_texts, *tags]).lower()
    if _has_any(
        text,
        [
            "introvert",
            "extrovert",
            "reported speech",
            "reported sentences",
            "direct speech",
            "suggested having",
            "boasted about",
            "accused",
        ],
    ):
        return LessonOverview(
            title="Reported Speech: Introverts, Extroverts, and Workplace Opinions",
            theme=(
                "Workplace personality preferences and how people report "
                "suggestions, claims, doubts, and accusations."
            ),
            focus=(
                "Reporting verbs and verb patterns: suggest/recommend + gerund, "
                "insist on + gerund, claim/admit that, accuse/apologize for + gerund."
            ),
            topic="Reported speech and workplace personality",
            goal=(
                "Report opinions, recommendations, and conflicts naturally in "
                "workplace English."
            ),
            knowledge_areas=(
                "reported speech",
                "reporting verbs",
                "verb patterns",
                "workplace opinions",
            ),
            grammar_rules=(
                "suggest/recommend + gerund",
                "insist/apologize/boast + preposition + gerund",
                "claim/admit/doubt/suggest + that-clause",
                "threaten/refuse + infinitive",
                "accuse/question + object + preposition + gerund",
            ),
            communication_skills=(
                "reporting what someone said",
                "summarising disagreement",
                "checking claims and details",
            ),
            mistake_risks=(
                "wrong verb pattern after reporting verbs",
                "missing preposition before a gerund",
                "over-direct reporting of workplace conflict",
            ),
        )
    if _has_any(text, ["architecture", "trade-off", "tradeoff", "reliability"]):
        return LessonOverview(
            title="Architecture Trade-offs and Stakeholder Communication",
            theme=(
                "Explaining technical trade-offs, risks, and recommendations to "
                "stakeholders."
            ),
            focus=(
                "Hedging recommendations, reliability/risk collocations, and concise "
                "stakeholder updates."
            ),
            topic="Architecture trade-offs",
            goal="Explain trade-offs, risks, and recommendations diplomatically.",
            knowledge_areas=(
                "architecture trade-offs",
                "stakeholder communication",
                "risk language",
            ),
            grammar_rules=(
                "modal verbs for recommendations",
                "conditionals for risks",
                "articles with specific project events",
            ),
            communication_skills=(
                "explaining trade-offs",
                "making a recommendation",
                "pushing back diplomatically",
            ),
            mistake_risks=(
                "too direct recommendations",
                "unclear risk ownership",
                "missing article before a specific release or incident",
            ),
        )
    if _has_any(text, ["incident", "root cause", "eta", "rollback", "production"]):
        return LessonOverview(
            title="Incident Updates and Risk Mitigation",
            theme="Concise production-issue updates with uncertainty and next steps.",
            focus="ETA caveats, mitigation language, and conditional risk statements.",
            topic="Incident and risk updates",
            goal="Write clear stakeholder updates about incidents and mitigations.",
            knowledge_areas=("incident updates", "risk mitigation", "ETA caveats"),
            grammar_rules=(
                "conditionals for risk",
                "modal verbs for next steps",
                "articles with incident/release references",
            ),
            communication_skills=(
                "communicating uncertainty",
                "setting expectations",
                "summarising mitigation plans",
            ),
            mistake_risks=(
                "overpromising an ETA",
                "unclear next step",
                "missing caveat around uncertainty",
            ),
        )
    if _has_any(text, ["stakeholder", "push back", "hedg", "align on"]):
        return LessonOverview(
            title="Diplomatic Stakeholder Communication",
            theme="Aligning, pushing back, and setting expectations at work.",
            focus="Diplomatic disagreement, hedging, and business collocations.",
            topic="Stakeholder communication",
            goal="Use diplomatic workplace language in concise exchanges.",
            knowledge_areas=(
                "stakeholder communication",
                "diplomatic disagreement",
                "business collocations",
            ),
            grammar_rules=(
                "modal verbs for soft recommendations",
                "prepositions in business collocations",
            ),
            communication_skills=(
                "aligning on priorities",
                "pushing back politely",
                "setting expectations",
            ),
            mistake_risks=(
                "too blunt disagreement",
                "wrong preposition in a collocation",
            ),
        )
    return LessonOverview(
        title="15-minute Workplace English Lesson",
        theme="Reusable business/IT English from the uploaded material.",
        focus="Useful chunks, grammar patterns, and active recall.",
        topic="Business/IT communication",
        goal="Practice useful workplace language in a staged 15-minute session.",
        knowledge_areas=(
            "business/IT English",
            "active vocabulary",
            "grammar patterns",
        ),
        grammar_rules=("material-specific grammar patterns",),
        communication_skills=("concise workplace responses",),
        mistake_risks=("using a chunk in the wrong pattern",),
    )


def _has_any(text: str, needles: Iterable[str]) -> bool:
    return any(needle in text for needle in needles)
