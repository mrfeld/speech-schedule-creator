import random
from models import (
    Student, Requirement, Group,
    SESSION_PULL_OUT_GROUP, SESSION_PUSH_IN_GROUP,
)


def _shares_goal(s1: Student, s2: Student) -> bool:
    cats1 = {g.category for g in s1.goals}
    cats2 = {g.category for g in s2.goals}
    return bool(cats1 & cats2)


def _shared_goal_level_score(s1: Student, s2: Student) -> int:
    """Returns number of goals shared at the same level (higher = more similar)."""
    by_cat1 = {g.category: g.level for g in s1.goals}
    by_cat2 = {g.category: g.level for g in s2.goals}
    shared_cats = set(by_cat1) & set(by_cat2)
    return sum(1 for c in shared_cats if by_cat1[c] == by_cat2[c])


def _sort_key(student: Student) -> tuple:
    cats = sorted(g.category for g in student.goals)
    levels = sorted(g.level for g in student.goals)
    return (student.grade, cats, levels)


def _can_add_to_group(
    candidate: str,
    group: list[str],
    students: dict,
    exclusions: set[frozenset],
    max_size: int,
    reqs: dict,
) -> bool:
    if len(group) >= max_size:
        return False
    for member in group:
        if frozenset({candidate, member}) in exclusions:
            return False
        member_max = reqs[member].max_group_size
        if len(group) >= member_max:
            return False
    return True


def _common_slots(names: list[str], available_slots: dict[str, set]) -> set:
    if not names:
        return set()
    result = set(available_slots[names[0]])
    for name in names[1:]:
        result &= available_slots[name]
    return result


def _find_group(
    candidate: str,
    groups: list[list[str]],
    students: dict,
    exclusions: set[frozenset],
    requirements: dict,
    available_slots: dict[str, set],
    count_attr: str,
) -> list[str] | None:
    """Find an existing group the candidate can join, or None.

    Only groups whose members all require the same number of group sessions as the
    candidate are considered, so differing counts are not mixed into one group.
    Callers start a new group when this returns None. This keeps the "same number
    of group sessions" property as a strong preference: it is honored whenever a
    compatible same-count group has room and shared slots, and otherwise the
    candidate simply seeds its own group.
    """
    cand_count = getattr(requirements[candidate], count_attr)
    for group in groups:
        if any(getattr(requirements[m], count_attr) != cand_count for m in group):
            continue
        max_size = min(requirements[m].max_group_size for m in group)
        if not _can_add_to_group(candidate, group, students, exclusions, max_size, requirements):
            continue
        tentative = group + [candidate]
        if len(_common_slots(tentative, available_slots)) >= cand_count:
            return group
    return None


def form_pull_out_groups(
    students: dict,
    requirements: dict,
    exclusions: set[frozenset],
    busy_slots: dict[str, set[tuple]],
    all_slots: set[tuple],  # all (day, period) pairs
    rng: random.Random | None = None,
) -> list[Group]:
    """Forms pull-out groups. Available slots = all_slots minus busy."""
    candidates = [
        name for name, req in requirements.items()
        if req.pull_out_group > 0
    ]
    candidates.sort(key=lambda n: _sort_key(students[n]))
    if rng:
        rng.shuffle(candidates)

    free_slots = {
        name: all_slots - busy_slots[name]
        for name in candidates
    }

    groups: list[list[str]] = []

    for candidate in candidates:
        # Join a group whose members need the same number of group sessions, or
        # start a new group rather than mixing differing counts.
        group = _find_group(candidate, groups, students, exclusions, requirements,
                            free_slots, "pull_out_group")
        if group is not None:
            group.append(candidate)
        else:
            groups.append([candidate])

    return [Group(students=g, session_type=SESSION_PULL_OUT_GROUP) for g in groups if len(g) > 0]


def form_push_in_groups(
    students: dict,
    requirements: dict,
    exclusions: set[frozenset],
    push_in_slots: dict[str, dict[tuple, str]],
    rng: random.Random | None = None,
) -> list[Group]:
    """Forms push-in groups. Students must share class_id and have common push-in eligible slots."""
    candidates = [
        name for name, req in requirements.items()
        if req.push_in_group > 0
    ]
    candidates.sort(key=lambda n: _sort_key(students[n]))
    if rng:
        rng.shuffle(candidates)

    push_in_available = {
        name: set(push_in_slots[name].keys())
        for name in candidates
    }

    groups_by_class: dict[str, list[list[str]]] = {}

    for candidate in candidates:
        class_id = students[candidate].class_id
        if class_id not in groups_by_class:
            groups_by_class[class_id] = []

        class_groups = groups_by_class[class_id]
        group = _find_group(candidate, class_groups, students, exclusions, requirements,
                            push_in_available, "push_in_group")
        if group is not None:
            group.append(candidate)
        else:
            class_groups.append([candidate])

    result = []
    for groups in groups_by_class.values():
        for g in groups:
            result.append(Group(students=g, session_type=SESSION_PUSH_IN_GROUP))
    return result
