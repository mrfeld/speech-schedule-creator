import csv
from models import (
    ScheduledSession, TimeSlot, DAYS, SESSION_TAGS, SESSION_LUNCH, SESSION_PREP,
    SESSION_PUSH_IN_INDIVIDUAL, SESSION_PUSH_IN_GROUP,
    SESSION_PULL_OUT_INDIVIDUAL, SESSION_PULL_OUT_GROUP,
)


def _cell_text(sessions: list[ScheduledSession]) -> str:
    if not sessions:
        return ""
    s = sessions[0]
    if s.session_type in (SESSION_LUNCH, SESSION_PREP):
        return s.session_type
    tag = SESSION_TAGS.get(s.session_type, s.session_type)
    names = ", ".join(s.students)
    return f"{names} [{tag}]"


def build_grid(sessions: list[ScheduledSession]) -> dict[tuple, list[ScheduledSession]]:
    grid: dict[tuple, list[ScheduledSession]] = {}
    for s in sessions:
        key = (s.slot.day, s.slot.period)
        grid.setdefault(key, []).append(s)
    return grid


def print_schedule(sessions: list[ScheduledSession]):
    grid = build_grid(sessions)
    col_width = 30
    header = f"{'Period':<8}" + "".join(f"{day:<{col_width}}" for day in DAYS)
    print("\n" + "=" * (8 + col_width * 5))
    print(header)
    print("=" * (8 + col_width * 5))
    for period in range(1, 9):
        row = f"P{period:<7}"
        for day in DAYS:
            cell = _cell_text(grid.get((day, period), []))
            row += f"{cell:<{col_width}}"
        print(row)
    print("=" * (8 + col_width * 5) + "\n")


def write_csv(sessions: list[ScheduledSession], output_path: str):
    grid = build_grid(sessions)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Period"] + DAYS)
        for period in range(1, 9):
            row = [f"P{period}"]
            for day in DAYS:
                row.append(_cell_text(grid.get((day, period), [])))
            writer.writerow(row)


def print_summary(
    sessions: list[ScheduledSession],
    requirements: dict,
    unscheduled: list[str],
    lunch_slots: set,
    prep_slots: set,
):
    print("--- SESSION SUMMARY ---")
    # Count per student
    counts: dict[str, dict[str, int]] = {}
    for s in sessions:
        if s.session_type in (SESSION_LUNCH, SESSION_PREP):
            continue
        for name in s.students:
            counts.setdefault(name, {})
            counts[name][s.session_type] = counts[name].get(s.session_type, 0) + 1

    for name, req in sorted(requirements.items()):
        student_counts = counts.get(name, {})
        parts = []
        for stype, label, required in [
            (SESSION_PUSH_IN_INDIVIDUAL, "PI", req.push_in_individual),
            (SESSION_PUSH_IN_GROUP, "PIG", req.push_in_group),
            (SESSION_PULL_OUT_INDIVIDUAL, "PO", req.pull_out_individual),
            (SESSION_PULL_OUT_GROUP, "POG", req.pull_out_group),
        ]:
            if required > 0 or student_counts.get(stype, 0) > 0:
                got = student_counts.get(stype, 0)
                flag = " !" if got < required else ""
                parts.append(f"{label}: {got}/{required}{flag}")
        total = sum(student_counts.values())
        print(f"  {name}: {', '.join(parts)} | total sessions: {total}")

    print("\n--- TEACHER BLOCKED PERIODS ---")
    for day in DAYS:
        lunch = sorted([s.period for s in lunch_slots if s.day == day])
        prep = sorted([s.period for s in prep_slots if s.day == day])
        lunch_str = f"Lunch=P{lunch[0]}" if lunch else "Lunch=?"
        prep_str = f"Prep=P{', P'.join(str(p) for p in prep)}" if prep else "Prep=none"
        print(f"  {day}: {lunch_str}, {prep_str}")

    if unscheduled:
        print("\n--- UNSCHEDULABLE SESSIONS ---")
        for msg in unscheduled:
            print(f"  ! {msg}")
    print()
