from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from fluentloop.db.models import GrammarConcept, LearningItem, MistakePattern

SEED_CONCEPTS = [
    (
        "Articles",
        "Use a/an/the and zero article to make project references precise.",
        ["Review it before the sprint starts.", "We discussed the incident."],
    ),
    (
        "Articles with specific project events",
        "Use the for a specific sprint, release, incident, or decision.",
        ["The release is risky.", "Let's revisit it after the sprint."],
    ),
    (
        "Zero article in business collocations",
        "Use zero article in broad collocations like at work or in production.",
        ["We saw this in production.", "Let's discuss it at work."],
    ),
    (
        "Modal verbs",
        "Use modal verbs to express certainty, permission, and recommendations.",
        ["We could delay the release.", "We should align on priorities."],
    ),
    (
        "Modal verbs for recommendations",
        "Use could, should, might, and would to make recommendations.",
        ["We might need to split the release.", "I would suggest a smaller scope."],
    ),
    (
        "Hedging recommendations",
        "Soften direct recommendations for stakeholder communication.",
        ["It may be worth delaying the release.", "I would lean towards option B."],
    ),
    (
        "Diplomatic disagreement",
        "Push back without sounding abrupt or defensive.",
        ["I'd like to push back on this timeline a bit."],
    ),
    (
        "Register and tone in stakeholder communication",
        "Adapt direct feedback into calm, collaborative stakeholder language.",
        ["I see the concern; the safest next step is a smaller rollout."],
    ),
    (
        "Conditionals",
        "Use if clauses to discuss risks and trade-offs.",
        ["If we rush the release, we may increase support load."],
    ),
    (
        "Conditionals for discussing risks",
        "Use conditionals to connect a decision to a likely project impact.",
        ["If we delay by one day, we can mitigate the reliability risk."],
    ),
    (
        "Reported speech",
        "Report decisions, claims, suggestions, and feedback accurately.",
        ["She suggested reducing the number of meetings."],
    ),
    (
        "Reported speech for recommendations",
        "Report suggestions and recommendations with natural verb patterns.",
        ["He recommended bringing a laptop.", "They suggested that we stay."],
    ),
    (
        "Tense consistency",
        "Keep project timelines clear when reporting updates.",
        ["We planned it yesterday, and we are shipping it tomorrow."],
    ),
    (
        "Prepositions in business English",
        "Use natural business collocations with prepositions.",
        ["align on priorities", "depend on the release window"],
    ),
    (
        "Business collocations with prepositions",
        "Use chunks like align on, depend on, push back on, and apologize for.",
        ["We need to align on priorities.", "I'd push back on that assumption."],
    ),
    (
        "Countable / uncountable business nouns",
        "Use nouns like feedback, progress, impact, and management naturally.",
        ["The feedback was useful.", "We made progress on the release."],
    ),
    (
        "Polite disagreement",
        "Pushing back without sounding abrupt.",
        ["I'm not fully convinced this is the safest path."],
    ),
    (
        "Risk language",
        "Describing likelihood, impact, and mitigation.",
        ["The main risk is reliability; we can mitigate it with a canary rollout."],
    ),
]

SEED_LINKS = [
    ("Articles with specific project events", "Articles"),
    ("Zero article in business collocations", "Articles"),
    ("Modal verbs for recommendations", "Modal verbs"),
    ("Hedging recommendations", "Modal verbs for recommendations"),
    ("Diplomatic disagreement", "Hedging recommendations"),
    ("Register and tone in stakeholder communication", "Diplomatic disagreement"),
    ("Conditionals for discussing risks", "Conditionals"),
    ("Reported speech for recommendations", "Reported speech"),
    ("Business collocations with prepositions", "Prepositions in business English"),
]

CONCEPT_KEYWORDS = [
    ("hedg", "Hedging recommendations"),
    ("modal", "Modal verbs for recommendations"),
    ("article", "Articles with specific project events"),
    ("preposition", "Business collocations with prepositions"),
    ("align on", "Business collocations with prepositions"),
    ("push back", "Diplomatic disagreement"),
    ("condition", "Conditionals for discussing risks"),
    ("risk", "Conditionals for discussing risks"),
    ("countable", "Countable / uncountable business nouns"),
    ("feedback", "Countable / uncountable business nouns"),
    ("reported", "Reported speech for recommendations"),
    ("tone", "Register and tone in stakeholder communication"),
    ("register", "Register and tone in stakeholder communication"),
]


def seed_concepts(session: Session) -> None:
    existing = {
        concept.title: concept
        for concept in session.scalars(
            select(GrammarConcept).order_by(GrammarConcept.id)
        )
    }
    for title, description, examples in SEED_CONCEPTS:
        concept = existing.get(title)
        if concept is None:
            concept = GrammarConcept(
                title=title,
                description=description,
                examples=examples,
            )
            session.add(concept)
            existing[title] = concept
        else:
            concept.description = description
            if not concept.examples:
                concept.examples = examples
            session.add(concept)
    session.flush()
    by_title = {
        concept.title: concept
        for concept in session.scalars(
            select(GrammarConcept).order_by(GrammarConcept.id)
        )
    }
    for child_title, parent_title in SEED_LINKS:
        child = by_title.get(child_title)
        parent = by_title.get(parent_title)
        if child is not None and parent is not None:
            link_parent(session, child, parent)


def link_parent(
    session: Session, child: GrammarConcept, parent: GrammarConcept
) -> None:
    if parent.id == child.id:
        raise ValueError("A concept cannot be its own parent")
    child_parents = set(child.parent_ids or [])
    parent_children = set(parent.child_ids or [])
    child_parents.add(parent.id)
    parent_children.add(child.id)
    child.parent_ids = sorted(child_parents)
    parent.child_ids = sorted(parent_children)
    session.add_all([child, parent])
    session.flush()


def unlink_parent(
    session: Session, child: GrammarConcept, parent: GrammarConcept
) -> None:
    child.parent_ids = sorted(set(child.parent_ids or []) - {parent.id})
    parent.child_ids = sorted(set(parent.child_ids or []) - {child.id})
    session.add_all([child, parent])
    session.flush()


def parents_of(
    session: Session, concept_id: int, *, depth: int = 1
) -> list[GrammarConcept]:
    found: list[GrammarConcept] = []
    frontier = [concept_id]
    seen = {concept_id}
    for _ in range(depth):
        next_frontier: list[int] = []
        for current_id in frontier:
            concept = session.get(GrammarConcept, current_id)
            if concept is None:
                continue
            for parent_id in concept.parent_ids or []:
                if parent_id in seen:
                    continue
                parent = session.get(GrammarConcept, parent_id)
                if parent is not None:
                    found.append(parent)
                    seen.add(parent_id)
                    next_frontier.append(parent_id)
        frontier = next_frontier
    return found


def children_of(
    session: Session, concept_id: int, *, depth: int = 1
) -> list[GrammarConcept]:
    found: list[GrammarConcept] = []
    frontier = [concept_id]
    seen = {concept_id}
    for _ in range(depth):
        next_frontier: list[int] = []
        for current_id in frontier:
            concept = session.get(GrammarConcept, current_id)
            if concept is None:
                continue
            for child_id in concept.child_ids or []:
                if child_id in seen:
                    continue
                child = session.get(GrammarConcept, child_id)
                if child is not None:
                    found.append(child)
                    seen.add(child_id)
                    next_frontier.append(child_id)
        frontier = next_frontier
    return found


def select_focus_concept(
    session: Session,
    *,
    items: list[LearningItem] | None = None,
    patterns: list[MistakePattern] | None = None,
) -> GrammarConcept | None:
    items = items or []
    patterns = patterns or []
    for pattern in patterns:
        if pattern.linked_grammar_concept_id is not None:
            concept = session.get(GrammarConcept, pattern.linked_grammar_concept_id)
            if concept is not None:
                return concept
    for item in items:
        if item.linked_grammar_concept_id is not None:
            concept = session.get(GrammarConcept, item.linked_grammar_concept_id)
            if concept is not None:
                return concept
    text = " ".join(
        [
            *(item.text for item in items),
            *(item.explanation or "" for item in items),
            *(tag for item in items for tag in (item.tags or [])),
            *(pattern.description for pattern in patterns),
            *(pattern.mistake_type for pattern in patterns),
        ]
    ).lower()
    for keyword, title in CONCEPT_KEYWORDS:
        if keyword in text:
            concept = session.scalar(
                select(GrammarConcept).where(GrammarConcept.title == title)
            )
            if concept is not None:
                return concept
    return session.scalar(
        select(GrammarConcept)
        .where(GrammarConcept.title == "Hedging recommendations")
        .limit(1)
    )
