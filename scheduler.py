import random
from itertools import combinations
from collections import defaultdict
from models import (
    Student, Requirement, Group, ScheduledSession, TimeSlot, DAYS,
    SESSION_PULL_OUT_INDIVIDUAL, SESSION_PULL_OUT_GROUP,
    SESSION_PUSH_IN_INDIVIDUAL, SESSION_PUSH_IN_GROUP,
)


def choose_teacher_off_periods(
    all_slots: list[TimeSlot],
    busy_slots: dict[str, set[tuple]],
    push_in_slots: dict[str, dict[tuple, str]],
) -> tuple[set[TimeSlot], set[TimeSlot]]:
    """Picks 3 blocked teacher periods per day (1 lunch in P4-6, 2 prep any).
    Returns (lunch_slots, prep_slots)."""
    lunch_slots: set[TimeSlot] = set()
    prep_slots: set[TimeSlot] = set()
    all_possible = {(slot.day, slot.period) for slot in all_slots}

    for day in DAYS:
        day_slots = [s for s in all_slots if s.day == day]
        periods = [s.period for s in day_slots]

        lunch_options = [p for p in periods if p in {4, 5, 6}]
        if not lunch_options:
            lunch_options = [4]

        best_combo = None
        best_score = -1

        for lunch_p in lunch_options:
            remaining = [p for p in periods if p != lunch_p]
            for prep1, prep2 in combinations(remaining, 2):
                blocked_periods = {lunch_p, prep1, prep2}
                preserved = sum(
                    sum(1 for busy in busy_slots.values() if (day, p) not in busy)
                    for p in periods
                    if p not in blocked_periods
                )
                if preserved > best_score:
                    best_score = preserved
                    best_combo = (lunch_p, prep1, prep2)

        if best_combo:
            lunch_p, prep1, prep2 = best_combo
            lunch_slots.add(TimeSlot(day=day, period=lunch_p))
            prep_slots.add(TimeSlot(day=day, period=prep1))
            prep_slots.add(TimeSlot(day=day, period=prep2))

    return lunch_slots, prep_slots


def _slots_per_day(slots: list[TimeSlot]) -> dict[str, list[TimeSlot]]:
    by_day: dict[str, list[TimeSlot]] = defaultdict(list)
    for s in slots:
        by_day[s.day].append(s)
    return dict(by_day)


def _common_free_slots(
    names: list[str],
    busy_slots: dict[str, set[tuple]],
    teacher_available: set[TimeSlot],
) -> list[TimeSlot]:
    result = []
    for slot in teacher_available:
        key = (slot.day, slot.period)
        if all(key not in busy_slots[n] for n in names):
            result.append(slot)
    return result


def _common_push_in_slots(
    names: list[str],
    push_in_slots: dict[str, dict[tuple, str]],
    teacher_available: set[TimeSlot],
) -> list[tuple[TimeSlot, str]]:
    result = []
    for slot in teacher_available:
        key = (slot.day, slot.period)
        class_names = [push_in_slots[n].get(key) for n in names]
        if all(c is not None for c in class_names) and len(set(class_names)) == 1:
            result.append((slot, class_names[0]))
    return result


def _spread_score(slot: TimeSlot, day_counts: dict[str, int]) -> int:
    """Lower is better — prefer days with fewer sessions so far."""
    return day_counts.get(slot.day, 0)


def _pick_slots(
    available: list[TimeSlot],
    count: int,
    day_counts: dict[str, int],
    used_slots: set[TimeSlot],
) -> list[TimeSlot]:
    """Pick `count` slots from available, preferring spread across days, avoiding used_slots."""
    candidates = [s for s in available if s not in used_slots]
    candidates.sort(key=lambda s: _spread_score(s, day_counts))
    return candidates[:count]


def _pick_push_in_slots(
    available: list[tuple[TimeSlot, str]],
    count: int,
    day_counts: dict[str, int],
    used_slots: set[TimeSlot],
) -> list[tuple[TimeSlot, str]]:
    candidates = [(s, c) for s, c in available if s not in used_slots]
    candidates.sort(key=lambda x: _spread_score(x[0], day_counts))
    return candidates[:count]


def build_schedule(
    students: dict[str, Student],
    requirements: dict[str, Requirement],
    pull_out_groups: list[Group],
    push_in_groups: list[Group],
    busy_slots: dict[str, set[tuple]],
    push_in_slots: dict[str, dict[tuple, str]],
    rng: random.Random | None = None,
) -> tuple[list[ScheduledSession], list[str]]:

    all_slots = [
        TimeSlot(day=day, period=period)
        for day in DAYS
        for period in range(1, 9)
    ]

    lunch_slots, prep_slots = choose_teacher_off_periods(all_slots, busy_slots, push_in_slots)
    teacher_blocked = lunch_slots | prep_slots
    teacher_available = {s for s in all_slots if s not in teacher_blocked}

    sessions: list[ScheduledSession] = []
    unscheduled: list[str] = []
    used_slots: set[TimeSlot] = set(teacher_blocked)
    day_counts: dict[str, int] = defaultdict(int)

    # Track how many required sessions each student still needs scheduled
    remaining: dict[str, dict[str, int]] = {}
    for name, req in requirements.items():
        remaining[name] = {
            SESSION_PUSH_IN_GROUP: req.push_in_group,
            SESSION_PULL_OUT_GROUP: req.pull_out_group,
            SESSION_PUSH_IN_INDIVIDUAL: req.push_in_individual,
            SESSION_PULL_OUT_INDIVIDUAL: req.pull_out_individual,
        }

    def schedule_session(slot: TimeSlot, names: list[str], stype: str, class_name=None):
        sessions.append(ScheduledSession(slot=slot, students=names, session_type=stype, class_name=class_name))
        used_slots.add(slot)
        day_counts[slot.day] += 1
        for n in names:
            if stype in remaining.get(n, {}):
                remaining[n][stype] = max(0, remaining[n][stype] - 1)

    if rng:
        push_in_groups = list(push_in_groups)
        rng.shuffle(push_in_groups)
        pull_out_groups = list(pull_out_groups)
        rng.shuffle(pull_out_groups)

    # 1. Push-in group sessions
    for group in push_in_groups:
        names = group.students
        needed = min(requirements[n].push_in_group for n in names)
        available = _common_push_in_slots(names, push_in_slots, teacher_available)
        picks = _pick_push_in_slots(available, needed, day_counts, used_slots)
        for slot, cls in picks:
            schedule_session(slot, names, SESSION_PUSH_IN_GROUP, cls)
        shortfall = needed - len(picks)
        if shortfall > 0:
            unscheduled.append(f"Push-in group {names}: {shortfall} session(s) unschedulable")

    # 2. Pull-out group sessions
    for group in pull_out_groups:
        names = group.students
        needed = min(requirements[n].pull_out_group for n in names)
        available = _common_free_slots(names, busy_slots, teacher_available)
        picks = _pick_slots(available, needed, day_counts, used_slots)
        for slot in picks:
            schedule_session(slot, names, SESSION_PULL_OUT_GROUP)
        shortfall = needed - len(picks)
        if shortfall > 0:
            unscheduled.append(f"Pull-out group {names}: {shortfall} session(s) unschedulable")

    # 3. Push-in individual sessions
    push_in_indiv_students = sorted(
        [n for n, req in requirements.items() if req.push_in_individual > 0],
        key=lambda n: len([s for s in teacher_available
                           if (s.day, s.period) in push_in_slots[n]])
    )
    if rng:
        rng.shuffle(push_in_indiv_students)
    for name in push_in_indiv_students:
        needed = remaining[name][SESSION_PUSH_IN_INDIVIDUAL]
        available = _common_push_in_slots([name], push_in_slots, teacher_available)
        picks = _pick_push_in_slots(available, needed, day_counts, used_slots)
        for slot, cls in picks:
            schedule_session(slot, [name], SESSION_PUSH_IN_INDIVIDUAL, cls)
        shortfall = needed - len(picks)
        if shortfall > 0:
            unscheduled.append(f"Push-in individual {name}: {shortfall} session(s) unschedulable")

    # 4. Pull-out individual sessions
    pull_out_indiv_students = sorted(
        [n for n, req in requirements.items() if req.pull_out_individual > 0],
        key=lambda n: len([s for s in teacher_available
                           if (s.day, s.period) not in busy_slots[n]])
    )
    if rng:
        rng.shuffle(pull_out_indiv_students)
    for name in pull_out_indiv_students:
        needed = remaining[name][SESSION_PULL_OUT_INDIVIDUAL]
        available = _common_free_slots([name], busy_slots, teacher_available)
        picks = _pick_slots(available, needed, day_counts, used_slots)
        for slot in picks:
            schedule_session(slot, [name], SESSION_PULL_OUT_INDIVIDUAL)
        shortfall = needed - len(picks)
        if shortfall > 0:
            unscheduled.append(f"Pull-out individual {name}: {shortfall} session(s) unschedulable")

    # 5. Fill remaining open slots by splitting groups (only for students with unmet requirements)
    # Build student → group-members lookups so we can form sub-groups from existing groups.
    student_po_group: dict[str, list[str]] = {}
    for g in pull_out_groups:
        for n in g.students:
            student_po_group[n] = g.students

    student_pi_group: dict[str, list[str]] = {}
    for g in push_in_groups:
        for n in g.students:
            student_pi_group[n] = g.students

    def largest_free_subgroup(
        group_members: list[str],
        stype: str,
        key: tuple,
        pi_slots: dict | None = None,
    ) -> list[str]:
        """Return members of group_members who have remaining requirements of stype and are free."""
        if pi_slots is not None:
            return [m for m in group_members
                    if remaining.get(m, {}).get(stype, 0) > 0
                    and key in pi_slots.get(m, {})]
        return [m for m in group_members
                if remaining.get(m, {}).get(stype, 0) > 0
                and key not in busy_slots.get(m, set())]

    open_slots = sorted(
        [s for s in teacher_available if s not in used_slots],
        key=lambda s: day_counts[s.day]
    )

    for slot in open_slots:
        key = (slot.day, slot.period)

        # Try pull-out group sub-groups: find the largest subset of any group
        # where all members are free and still need POG sessions.
        best_po: list[str] = []
        seen_po: set[frozenset] = set()
        for name in student_po_group:
            gkey = frozenset(student_po_group[name])
            if gkey in seen_po:
                continue
            seen_po.add(gkey)
            sub = largest_free_subgroup(student_po_group[name], SESSION_PULL_OUT_GROUP, key)
            if len(sub) > len(best_po):
                best_po = sub
        if len(best_po) >= 1:
            # 2+ members → group session; 1 member → counts against their POG requirement solo
            schedule_session(slot, best_po, SESSION_PULL_OUT_GROUP)
            continue

        # Try push-in group sub-groups
        best_pi: list[str] = []
        best_pi_class: str = ""
        seen_pi: set[frozenset] = set()
        for name in student_pi_group:
            gkey = frozenset(student_pi_group[name])
            if gkey in seen_pi:
                continue
            seen_pi.add(gkey)
            sub = largest_free_subgroup(student_pi_group[name], SESSION_PUSH_IN_GROUP, key,
                                        pi_slots=push_in_slots)
            if len(sub) > len(best_pi):
                cls = push_in_slots[sub[0]].get(key, "")
                if cls:
                    best_pi = sub
                    best_pi_class = cls
        if len(best_pi) >= 1:
            schedule_session(slot, best_pi, SESSION_PUSH_IN_GROUP, best_pi_class)
            continue

        # Try individual pull-out sessions for students with remaining PO requirements
        po_indiv = [
            n for n in students
            if remaining.get(n, {}).get(SESSION_PULL_OUT_INDIVIDUAL, 0) > 0
            and key not in busy_slots.get(n, set())
        ]
        if po_indiv:
            schedule_session(slot, [po_indiv[0]], SESSION_PULL_OUT_INDIVIDUAL)
            continue

        # Try individual push-in sessions for students with remaining PI requirements
        pi_indiv = [
            (n, push_in_slots[n][key])
            for n in students
            if remaining.get(n, {}).get(SESSION_PUSH_IN_INDIVIDUAL, 0) > 0
            and key in push_in_slots.get(n, {})
        ]
        if pi_indiv:
            name, cls = pi_indiv[0]
            schedule_session(slot, [name], SESSION_PUSH_IN_INDIVIDUAL, cls)
            continue
        # No student has remaining requirements for this slot — leave it empty.

    for slot in lunch_slots:
        sessions.append(ScheduledSession(slot=slot, students=[], session_type="LUNCH"))
    for slot in prep_slots:
        sessions.append(ScheduledSession(slot=slot, students=[], session_type="PREP"))

    return sessions, unscheduled, lunch_slots, prep_slots
