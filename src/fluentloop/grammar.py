from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from fluentloop.db.models import GrammarConcept

SEED_CONCEPTS = [
    ("Articles", "Using a/an/the and zero article."),
    ("Modal verbs", "Can, could, may, might, must, should."),
    (
        "Modal verbs for recommendations",
        "Soft recommendations with could/should/might.",
    ),
    ("Hedging recommendations", "Diplomatic stakeholder recommendations."),
    ("Conditionals", "If clauses for risks and trade-offs."),
    ("Reported speech", "Reporting decisions and feedback."),
    ("Tense consistency", "Keeping project timelines clear."),
    ("Prepositions in business English", "Collocations like align on and depend on."),
    ("Polite disagreement", "Pushing back without sounding abrupt."),
    ("Risk language", "Describing likelihood, impact, and mitigation."),
]


def seed_concepts(session: Session) -> None:
    if session.scalar(select(GrammarConcept).limit(1)) is not None:
        return
    concepts = [
        GrammarConcept(title=title, description=description, examples=[])
        for title, description in SEED_CONCEPTS
    ]
    session.add_all(concepts)
    session.flush()
    by_title = {concept.title: concept for concept in concepts}
    link_parent(
        session, by_title["Modal verbs for recommendations"], by_title["Modal verbs"]
    )
    link_parent(
        session,
        by_title["Hedging recommendations"],
        by_title["Modal verbs for recommendations"],
    )


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
