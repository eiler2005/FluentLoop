from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from fluentloop.db.models import LessonPlan, LessonPlanItem, SourceMaterial, User
from fluentloop.learning import create_learning_item
from fluentloop.lesson_plans import (
    create_lesson_plan_from_source,
    link_lesson_items,
)
from fluentloop.materials import store_material

CURRICULUM_TAG = "curriculum:b2-b2plus"


@dataclass(frozen=True)
class CurriculumTarget:
    type_: str
    text: str
    meaning: str
    explanation: str
    examples: tuple[str, ...]


@dataclass(frozen=True)
class CurriculumLesson:
    slug: str
    title: str
    topic: str
    goal: str
    grammar_focus: tuple[str, ...]
    knowledge_areas: tuple[str, ...]
    target_chunks: tuple[str, ...]
    mistake_risks: tuple[str, ...]
    targets: tuple[CurriculumTarget, ...]

    @property
    def tags(self) -> list[str]:
        return [CURRICULUM_TAG, self.slug, *self.knowledge_areas]

    @property
    def raw_text(self) -> str:
        return "\n".join(
            [
                f"[{CURRICULUM_TAG}] {self.title}",
                f"Slug: {self.slug}",
                f"Topic: {self.topic}",
                f"Goal: {self.goal}",
                "Grammar focus: " + ", ".join(self.grammar_focus),
                "Knowledge areas: " + ", ".join(self.knowledge_areas),
                "Target chunks: " + ", ".join(self.target_chunks),
                "Mistake risks: " + ", ".join(self.mistake_risks),
                "Micro-drill plan: warmup 1, input 2, controlled practice 8, "
                "grammar/mistake focus 3, free production 1, recap 2.",
            ]
        )


def _target(
    type_: str,
    text: str,
    meaning: str,
    explanation: str,
    example: str,
) -> CurriculumTarget:
    return CurriculumTarget(type_, text, meaning, explanation, (example,))


CURRICULUM_LESSONS: tuple[CurriculumLesson, ...] = (
    CurriculumLesson(
        "diplomatic-stakeholder-pushback",
        "Diplomatic Stakeholder Pushback",
        "Stakeholder communication",
        "Push back on a risky plan without sounding defensive.",
        ("hedging recommendations", "modal verbs for suggestions"),
        ("stakeholders", "pushback", "register"),
        ("push back on", "I see one risk", "it may be worth"),
        ("too direct disagreement", "missing preposition after push back"),
        (
            _target(
                "expression",
                "push back on",
                "politely challenge an idea",
                "Use push back on + proposal/idea/timeline.",
                "I'd like to push back on the Friday timeline a bit.",
            ),
            _target(
                "expression",
                "I see one risk",
                "a calm way to introduce a concern",
                "A useful opener before disagreeing.",
                "I see one risk with shipping both changes together.",
            ),
            _target(
                "expression",
                "it may be worth",
                "soft recommendation",
                "A hedge for suggestions in business English.",
                "It may be worth splitting the release into two phases.",
            ),
            _target(
                "grammar_rule",
                "Hedging recommendations",
                "softening recommendations",
                "Use might, could, may be worth, and would lean towards.",
                "We might need to delay the rollout.",
            ),
        ),
    ),
    CurriculumLesson(
        "incident-updates-eta-caveats",
        "Incident Updates and ETA Caveats",
        "Incident and risk updates",
        "Write a concise production issue update with uncertainty.",
        ("articles with incidents", "modal verbs for next steps"),
        ("incidents", "risk", "status-updates"),
        ("root cause", "impact window", "ETA caveat"),
        ("overpromising an ETA", "unclear next step"),
        (
            _target(
                "word",
                "root cause",
                "underlying reason",
                "Use for the main technical reason behind an incident.",
                "We have narrowed the root cause down to a cache issue.",
            ),
            _target(
                "expression",
                "impact window",
                "period when users were affected",
                "Useful in concise incident summaries.",
                "The impact window was between 09:10 and 09:24 UTC.",
            ),
            _target(
                "expression",
                "ETA caveat",
                "qualification around timing",
                "Use caveats when the timing is still uncertain.",
                "Current ETA is 30 minutes, with a caveat around validation.",
            ),
            _target(
                "grammar_rule",
                "Articles with specific incidents",
                "the incident, the rollout, the fix",
                "Use the for known project events.",
                "The incident affected the checkout flow.",
            ),
        ),
    ),
    CurriculumLesson(
        "architecture-tradeoffs-recommendations",
        "Architecture Trade-offs and Recommendations",
        "Architecture trade-offs",
        "Compare options and recommend one without overselling it.",
        ("conditionals for risks", "comparatives"),
        ("architecture", "tradeoffs", "recommendations"),
        ("trade-off", "from a reliability perspective", "I would lean towards"),
        ("overselling certainty", "unclear recommendation"),
        (
            _target(
                "word",
                "trade-off",
                "balance between competing choices",
                "Use for cost/benefit choices in engineering.",
                "The main trade-off is latency versus reliability.",
            ),
            _target(
                "expression",
                "from a reliability perspective",
                "looking at reliability specifically",
                "Frames a recommendation by criterion.",
                "From a reliability perspective, the async option is safer.",
            ),
            _target(
                "expression",
                "I would lean towards",
                "soft recommendation",
                "A natural B2+ way to recommend without overclaiming.",
                "I would lean towards the async workflow.",
            ),
            _target(
                "grammar_rule",
                "Conditionals for risks",
                "if/provided/as long as for risk",
                "Use conditionals to explain trade-offs.",
                "If we skip validation, we may increase rollback risk.",
            ),
        ),
    ),
    CurriculumLesson(
        "reporting-verbs-workplace-opinions",
        "Reporting Verbs for Workplace Opinions",
        "Reported speech and workplace opinions",
        "Report suggestions, claims, doubts, and disagreements accurately.",
        ("reporting verbs", "gerund vs infinitive", "that-clauses"),
        ("reported-speech", "opinions", "verb-patterns"),
        ("suggest having", "claim that", "insist on"),
        ("wrong verb pattern", "missing preposition before gerund"),
        (
            _target(
                "expression",
                "suggest having",
                "suggest + gerund",
                "Use suggest having, not suggest to have.",
                "She suggested having one weekly planning meeting.",
            ),
            _target(
                "expression",
                "claim that",
                "report a claim",
                "Use claim that + clause for reported opinions.",
                "He claimed that the change was low risk.",
            ),
            _target(
                "expression",
                "insist on",
                "strongly request or maintain",
                "Use insist on + noun/gerund.",
                "They insisted on reviewing the rollout plan.",
            ),
            _target(
                "grammar_rule",
                "Reporting verb patterns",
                "verb + gerund / that-clause / infinitive",
                "Different reporting verbs take different patterns.",
                "They refused to approve it but suggested delaying it.",
            ),
        ),
    ),
    CurriculumLesson(
        "risk-mitigation-conditionals",
        "Risk Mitigation and Conditionals",
        "Risk mitigation",
        "Explain risks and mitigations using precise conditional language.",
        ("mixed conditionals", "unless/provided/as long as"),
        ("risk", "mitigation", "conditionals"),
        ("mitigate the risk", "provided that", "unless we"),
        ("unclear condition", "overusing if"),
        (
            _target(
                "word",
                "mitigate",
                "reduce a risk",
                "Use mitigate + risk/impact.",
                "We can mitigate the risk with a smaller release.",
            ),
            _target(
                "expression",
                "provided that",
                "only if",
                "Formal condition marker for requirements.",
                "We can proceed provided that monitoring is ready.",
            ),
            _target(
                "expression",
                "unless we",
                "if we do not",
                "Use unless for negative conditions.",
                "Unless we reduce scope, the timeline is risky.",
            ),
            _target(
                "grammar_rule",
                "Conditionals for risk",
                "if, unless, provided that, as long as",
                "Conditionals make risk logic explicit.",
                "If we delay QA, we may miss regressions.",
            ),
        ),
    ),
    CurriculumLesson(
        "sprint-planning-priority-negotiation",
        "Sprint Planning and Priority Negotiation",
        "Sprint planning",
        "Align on priorities and negotiate scope for a sprint.",
        ("articles with sprints", "preposition collocations"),
        ("planning", "priorities", "scope"),
        ("align on priorities", "scope it down", "nice-to-have"),
        ("align priorities without on", "missing article before sprint"),
        (
            _target(
                "expression",
                "align on priorities",
                "agree priorities",
                "Use align on + topic.",
                "We need to align on priorities before the sprint starts.",
            ),
            _target(
                "expression",
                "scope it down",
                "reduce scope",
                "Natural product planning phrase.",
                "Can we scope it down to the payment flow first?",
            ),
            _target(
                "expression",
                "nice-to-have",
                "optional feature",
                "Use for lower-priority work.",
                "The dashboard export is a nice-to-have for this sprint.",
            ),
            _target(
                "mistake_pattern",
                "Missing preposition after align",
                "align on, not align priorities",
                "Use align on + noun phrase.",
                "Let's align on the release priorities.",
            ),
        ),
    ),
    CurriculumLesson(
        "scope-clarification-requirements",
        "Scope Clarification and Requirements",
        "Requirements clarification",
        "Ask precise questions and clarify ambiguous requirements.",
        ("indirect questions", "embedded questions"),
        ("requirements", "scope", "questions"),
        ("clarify the scope", "what exactly do we mean by", "out of scope"),
        ("too direct questions", "unclear ownership"),
        (
            _target(
                "expression",
                "clarify the scope",
                "make scope clear",
                "Use with requirements and delivery boundaries.",
                "Can we clarify the scope before estimating this?",
            ),
            _target(
                "expression",
                "what exactly do we mean by",
                "ask for precision",
                "A diplomatic way to challenge vague wording.",
                "What exactly do we mean by real-time sync here?",
            ),
            _target(
                "expression",
                "out of scope",
                "not included",
                "Use for boundaries.",
                "Advanced analytics are out of scope for this release.",
            ),
            _target(
                "grammar_rule",
                "Indirect clarification questions",
                "Could you clarify / Do we mean",
                "Indirect questions sound more diplomatic.",
                "Could you clarify whether this includes mobile users?",
            ),
        ),
    ),
    CurriculumLesson(
        "technical-debt-refactoring-rationale",
        "Technical Debt and Refactoring Rationale",
        "Technical debt",
        "Explain why refactoring is worth doing now.",
        ("cause and result clauses", "discourse markers"),
        ("technical-debt", "refactoring", "rationale"),
        ("technical debt", "maintenance cost", "in the long run"),
        ("vague justification", "too technical explanation"),
        (
            _target(
                "expression",
                "technical debt",
                "accumulated maintenance burden",
                "Use for shortcuts that create future cost.",
                "This module has accumulated too much technical debt.",
            ),
            _target(
                "expression",
                "maintenance cost",
                "ongoing cost to keep something working",
                "Useful in refactoring rationale.",
                "The current design increases maintenance cost.",
            ),
            _target(
                "expression",
                "in the long run",
                "over time",
                "Connects current investment to future benefit.",
                "In the long run, refactoring will reduce incidents.",
            ),
            _target(
                "grammar_rule",
                "Cause and result clauses",
                "because, therefore, as a result",
                "Use clear logic to justify refactoring.",
                "Because the module is tightly coupled, changes take longer.",
            ),
        ),
    ),
    CurriculumLesson(
        "data-trends-business-reports",
        "Data Trends and Business Reports",
        "Data reporting",
        "Summarise trends and explain business impact.",
        ("modifying comparatives", "discourse markers"),
        ("data", "reports", "trends"),
        ("a slight increase", "a downward trend", "compared with"),
        ("wrong preposition with compared", "overclaiming from data"),
        (
            _target(
                "expression",
                "a slight increase",
                "small rise",
                "Use for careful data descriptions.",
                "We saw a slight increase in activation last week.",
            ),
            _target(
                "expression",
                "a downward trend",
                "falling pattern",
                "Use for trends over time.",
                "There is a downward trend in support tickets.",
            ),
            _target(
                "expression",
                "compared with",
                "in comparison to",
                "Use compared with/to for data comparisons.",
                "Conversion improved compared with the previous release.",
            ),
            _target(
                "grammar_rule",
                "Careful data claims",
                "appears to / suggests / may indicate",
                "Use hedging when evidence is limited.",
                "This may indicate better onboarding quality.",
            ),
        ),
    ),
    CurriculumLesson(
        "customer-feedback-feature-prioritisation",
        "Customer Feedback and Feature Prioritisation",
        "Product feedback",
        "Prioritise product work from customer feedback.",
        ("relative clauses", "ranking language"),
        ("product", "feedback", "prioritisation"),
        ("recurring feedback", "prioritise", "high-impact"),
        ("feature vs function confusion", "unclear priority reason"),
        (
            _target(
                "expression",
                "recurring feedback",
                "feedback that repeats",
                "Use for repeated customer signals.",
                "Recurring feedback points to onboarding friction.",
            ),
            _target(
                "word",
                "prioritise",
                "rank by importance",
                "Use prioritise + work/item/feature.",
                "We should prioritise the billing issue first.",
            ),
            _target(
                "expression",
                "high-impact",
                "with strong effect",
                "Useful for product prioritisation.",
                "This is a high-impact fix for enterprise users.",
            ),
            _target(
                "grammar_rule",
                "Relative clauses for product details",
                "which/that/who clauses",
                "Use relative clauses to specify customer groups or features.",
                "The users who rely on exports are blocked.",
            ),
        ),
    ),
    CurriculumLesson(
        "cross-team-dependencies-ownership",
        "Cross-team Dependencies and Ownership",
        "Cross-team collaboration",
        "Discuss dependencies, blockers, and ownership clearly.",
        ("noun + preposition collocations", "passive for ownership"),
        ("dependencies", "ownership", "blockers"),
        ("depend on", "dependency on", "own the follow-up"),
        ("dependencies from", "unclear owner"),
        (
            _target(
                "expression",
                "depend on",
                "rely on",
                "Use depend on, not depend from.",
                "We depend on the platform team for the migration.",
            ),
            _target(
                "expression",
                "dependency on",
                "required support from",
                "Use dependency on + team/system.",
                "There is a dependency on the billing service.",
            ),
            _target(
                "expression",
                "own the follow-up",
                "be responsible for the next action",
                "Clarifies accountability.",
                "I can own the follow-up with the API team.",
            ),
            _target(
                "mistake_pattern",
                "Wrong preposition after dependency",
                "dependency on, not dependency from",
                "Use on after dependency in this business meaning.",
                "We have a dependency on their release plan.",
            ),
        ),
    ),
    CurriculumLesson(
        "performance-latency-reliability",
        "Performance, Latency, and Reliability",
        "Performance engineering",
        "Explain performance issues and reliability trade-offs.",
        ("comparatives", "cause/result clauses"),
        ("performance", "latency", "reliability"),
        ("latency spike", "reliability concern", "under load"),
        ("confusing effect and cause", "missing article with metric"),
        (
            _target(
                "expression",
                "latency spike",
                "sudden increase in latency",
                "Use for performance incidents.",
                "We saw a latency spike after the deploy.",
            ),
            _target(
                "expression",
                "reliability concern",
                "risk to stable operation",
                "Use to explain non-functional risk.",
                "The retry logic creates a reliability concern.",
            ),
            _target(
                "expression",
                "under load",
                "when traffic is high",
                "Useful for performance conditions.",
                "The service becomes unstable under load.",
            ),
            _target(
                "grammar_rule",
                "Cause and result in performance updates",
                "due to / caused by / as a result",
                "State cause and effect clearly.",
                "The spike was caused by a slow database query.",
            ),
        ),
    ),
    CurriculumLesson(
        "security-privacy-risk-communication",
        "Security and Privacy Risk Communication",
        "Security risk",
        "Explain security/privacy risks without creating panic.",
        ("passive voice", "risk hedging"),
        ("security", "privacy", "risk"),
        ("potential exposure", "access control", "mitigation plan"),
        ("alarmist wording", "unclear risk severity"),
        (
            _target(
                "expression",
                "potential exposure",
                "possible data/security exposure",
                "Careful phrase for unconfirmed security risk.",
                "We are checking a potential exposure in the export flow.",
            ),
            _target(
                "expression",
                "access control",
                "permission management",
                "Use for security boundaries.",
                "The issue is related to access control.",
            ),
            _target(
                "expression",
                "mitigation plan",
                "plan to reduce risk",
                "Useful in security updates.",
                "The mitigation plan is to rotate the affected tokens.",
            ),
            _target(
                "grammar_rule",
                "Passive voice for incident focus",
                "was exposed / was affected",
                "Use passive when the affected object matters most.",
                "No customer data was exposed.",
            ),
        ),
    ),
    CurriculumLesson(
        "performance-feedback-diplomacy",
        "Performance Feedback Diplomacy",
        "Workplace feedback",
        "Give direct but respectful feedback to a colleague.",
        ("softening direct feedback", "modal verbs"),
        ("feedback", "diplomacy", "collaboration"),
        ("one thing to improve", "from my perspective", "next time"),
        ("too blunt criticism", "unclear actionable point"),
        (
            _target(
                "expression",
                "one thing to improve",
                "specific improvement area",
                "Keeps feedback focused and actionable.",
                "One thing to improve is the handover timing.",
            ),
            _target(
                "expression",
                "from my perspective",
                "softens personal viewpoint",
                "Useful when giving feedback.",
                "From my perspective, the update needed more context.",
            ),
            _target(
                "expression",
                "next time",
                "future-oriented feedback",
                "Makes criticism less personal.",
                "Next time, let's agree on the owner earlier.",
            ),
            _target(
                "grammar_rule",
                "Softening feedback",
                "could / might / it would help",
                "Softening makes feedback easier to accept.",
                "It would help to share the context earlier.",
            ),
        ),
    ),
    CurriculumLesson(
        "roadmap-updates-uncertainty",
        "Roadmap Updates Under Uncertainty",
        "Roadmap communication",
        "Explain roadmap changes and uncertainty clearly.",
        ("future forms", "hedging probability"),
        ("roadmap", "uncertainty", "planning"),
        ("tentative plan", "subject to change", "likely to"),
        ("overpromising", "unclear confidence level"),
        (
            _target(
                "expression",
                "tentative plan",
                "not final plan",
                "Use for early roadmap communication.",
                "The tentative plan is to start discovery next month.",
            ),
            _target(
                "expression",
                "subject to change",
                "may change",
                "Signals uncertainty clearly.",
                "The timeline is subject to change after discovery.",
            ),
            _target(
                "expression",
                "likely to",
                "probable future",
                "Use for evidence-based forecasts.",
                "The API work is likely to move to Q3.",
            ),
            _target(
                "grammar_rule",
                "Future forms for roadmap updates",
                "will / going to / likely to / due to",
                "Choose future forms based on certainty.",
                "We are due to revisit the plan after user research.",
            ),
        ),
    ),
    CurriculumLesson(
        "postmortems-lessons-learned",
        "Postmortems and Lessons Learned",
        "Postmortems",
        "Summarise causes and lessons without blaming people.",
        ("past perfect", "passive voice", "cause/result clauses"),
        ("postmortem", "lessons-learned", "incidents"),
        ("contributing factor", "lesson learned", "prevent recurrence"),
        ("blame-heavy language", "unclear sequence of events"),
        (
            _target(
                "expression",
                "contributing factor",
                "one factor among several",
                "Useful in balanced postmortems.",
                "A missing alert was a contributing factor.",
            ),
            _target(
                "expression",
                "lesson learned",
                "takeaway for future improvement",
                "Use in postmortem recaps.",
                "One lesson learned is to validate alerts after migration.",
            ),
            _target(
                "expression",
                "prevent recurrence",
                "stop the same issue happening again",
                "Useful for action items.",
                "This check should prevent recurrence.",
            ),
            _target(
                "grammar_rule",
                "Past perfect for event sequence",
                "had happened before another past event",
                "Use past perfect to clarify incident timelines.",
                "The alert had failed before the traffic spike started.",
            ),
        ),
    ),
    CurriculumLesson(
        "async-slack-email-updates",
        "Async Slack and Email Updates",
        "Async communication",
        "Write concise async updates with context and next steps.",
        ("discourse markers", "ellipsis in updates"),
        ("async", "slack", "email"),
        ("quick update", "for context", "next step"),
        ("too much detail", "missing ask"),
        (
            _target(
                "expression",
                "quick update",
                "short progress update",
                "Natural opener in Slack/email.",
                "Quick update: the migration is now in staging.",
            ),
            _target(
                "expression",
                "for context",
                "background information",
                "Use before relevant background.",
                "For context, this only affects new users.",
            ),
            _target(
                "expression",
                "next step",
                "following action",
                "Keeps async updates actionable.",
                "The next step is to validate the metrics.",
            ),
            _target(
                "grammar_rule",
                "Concise update structure",
                "context, status, next step, ask",
                "Async messages need a clear structure.",
                "For context, X. Current status: Y. Next step: Z.",
            ),
        ),
    ),
    CurriculumLesson(
        "deadline-negotiation-pushback",
        "Deadline Negotiation and Pushback",
        "Deadline negotiation",
        "Negotiate a deadline while protecting quality.",
        ("modals for negotiation", "conditionals"),
        ("deadlines", "negotiation", "quality"),
        ("move the deadline", "protect quality", "reduce scope"),
        ("sounding defensive", "unclear alternative"),
        (
            _target(
                "expression",
                "move the deadline",
                "change deadline later",
                "Use move for deadline changes.",
                "Could we move the deadline to Wednesday?",
            ),
            _target(
                "expression",
                "protect quality",
                "avoid quality loss",
                "Useful reason for pushback.",
                "This would help us protect quality.",
            ),
            _target(
                "expression",
                "reduce scope",
                "make the work smaller",
                "Offer this as an alternative to moving time.",
                "If the date is fixed, we should reduce scope.",
            ),
            _target(
                "grammar_rule",
                "Negotiation conditionals",
                "if the date is fixed, we can...",
                "Use conditionals to offer options.",
                "If Friday is fixed, we can ship the smaller version.",
            ),
        ),
    ),
    CurriculumLesson(
        "executive-summaries-recommendations",
        "Executive Summaries and Concise Recommendations",
        "Executive communication",
        "Write short summaries for decision-makers.",
        ("cleft sentences", "discourse markers"),
        ("executive-summary", "recommendations", "decisions"),
        ("bottom line", "recommended option", "key risk"),
        ("too much detail", "buried recommendation"),
        (
            _target(
                "expression",
                "bottom line",
                "main point",
                "Use to lead with the conclusion.",
                "Bottom line: the async option is safer.",
            ),
            _target(
                "expression",
                "recommended option",
                "choice you advise",
                "Useful in decision summaries.",
                "The recommended option is a phased rollout.",
            ),
            _target(
                "expression",
                "key risk",
                "main risk",
                "Focuses executive attention.",
                "The key risk is insufficient validation time.",
            ),
            _target(
                "grammar_rule",
                "Cleft sentences for emphasis",
                "What matters most is...",
                "Use cleft structures to highlight key points.",
                "What matters most is reducing rollback risk.",
            ),
        ),
    ),
    CurriculumLesson(
        "disagreeing-proposing-alternatives",
        "Disagreeing, Proposing Alternatives, and Aligning Next Steps",
        "Diplomatic disagreement",
        "Disagree clearly, propose an alternative, and align on next steps.",
        ("contrast clauses", "suggestions"),
        ("disagreement", "alternatives", "alignment"),
        ("I am not fully convinced", "an alternative would be", "align on next steps"),
        ("disagreeing without alternative", "too blunt contrast"),
        (
            _target(
                "expression",
                "I am not fully convinced",
                "soft disagreement",
                "Diplomatic way to challenge an idea.",
                "I'm not fully convinced this solves the root cause.",
            ),
            _target(
                "expression",
                "an alternative would be",
                "propose another option",
                "Pair disagreement with an alternative.",
                "An alternative would be to release behind a flag.",
            ),
            _target(
                "expression",
                "align on next steps",
                "agree follow-up actions",
                "Use for closing a disagreement productively.",
                "Let's align on next steps after the risk review.",
            ),
            _target(
                "grammar_rule",
                "Contrast clauses for disagreement",
                "although, however, whereas",
                "Use contrast markers to organise disagreement.",
                "Although this is faster, it increases operational risk.",
            ),
        ),
    ),
)


def seed_b2_curriculum(session: Session, user: User) -> dict[str, int]:
    plans = 0
    items = 0
    for lesson in CURRICULUM_LESSONS:
        material = _material_for_lesson(session, user, lesson)
        lesson_items = []
        for target in lesson.targets:
            item = create_learning_item(
                session,
                user,
                type_=target.type_,
                text=target.text,
                meaning=target.meaning,
                explanation=target.explanation,
                examples=list(target.examples),
                tags=[*lesson.tags, target.type_],
                source_material_id=material.id,
            )
            lesson_items.append(item)
        items += len(lesson_items)
        plan = create_lesson_plan_from_source(
            session,
            user,
            material,
            items=lesson_items,
            status="active",
            provider=None,
        )
        _apply_lesson_metadata(session, plan, lesson)
        link_lesson_items(session, plan, lesson_items)
        plans += 1
    session.flush()
    return {"lessons": plans, "items": items}


def render_curriculum_markdown() -> str:
    lines = [
        "# B2/B2+ Business and IT English Lesson Catalog",
        "",
        "Deterministic FluentLoop seed catalog. No DeepSeek call is required.",
        "",
    ]
    for index, lesson in enumerate(CURRICULUM_LESSONS, start=1):
        lines.extend(
            [
                f"## {index}. {lesson.title}",
                "",
                f"- Slug: `{lesson.slug}`",
                f"- Topic: {lesson.topic}",
                f"- Goal: {lesson.goal}",
                f"- Grammar focus: {', '.join(lesson.grammar_focus)}",
                f"- Knowledge areas: {', '.join(lesson.knowledge_areas)}",
                f"- Target chunks: {', '.join(lesson.target_chunks)}",
                f"- Mistake risks: {', '.join(lesson.mistake_risks)}",
                "- Micro-drills: warmup 1, input 2, controlled practice 8, "
                "grammar/mistake focus 3, free production 1, recap 2.",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _material_for_lesson(
    session: Session, user: User, lesson: CurriculumLesson
) -> SourceMaterial:
    existing = session.scalar(
        select(SourceMaterial).where(
            SourceMaterial.user_id == user.id,
            SourceMaterial.raw_text == lesson.raw_text,
        )
    )
    if existing is not None:
        return existing
    material = store_material(session, user, lesson.raw_text, type_="lesson_notes")
    material.summary = lesson.title
    session.add(material)
    session.flush()
    return material


def _apply_lesson_metadata(
    session: Session, plan: LessonPlan, lesson: CurriculumLesson
) -> None:
    plan.title = lesson.title
    plan.topic = lesson.topic
    plan.goal = lesson.goal
    plan.language_focus_json = list(lesson.grammar_focus)
    plan.tags_json = lesson.tags
    session.add(plan)
    for link in session.scalars(
        select(LessonPlanItem).where(LessonPlanItem.lesson_plan_id == plan.id)
    ):
        link.priority = max(1, link.priority)
        session.add(link)
