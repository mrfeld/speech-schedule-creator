import csv
from collections import defaultdict
from models import (
    Student, Goal, Requirement, ClassPeriod,
    DAYS, RESTRICTED_CLASSES, EIGHTH_GRADE_RESTRICTED, PUSH_IN_ELIGIBLE_CLASSES
)


def load_students(data_dir: str) -> dict[str, Student]:
    students = {}
    path = f"{data_dir}/students.csv"
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row["name"].strip()
            students[name] = Student(
                name=name,
                grade=int(row["grade"].strip()),
                class_id=row["class_id"].strip(),
            )
    return students


def load_goals(data_dir: str, students: dict[str, Student]) -> None:
    path = f"{data_dir}/goals.csv"
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row["student_name"].strip()
            if name not in students:
                raise ValueError(f"goals.csv: unknown student '{name}'")
            students[name].goals.append(Goal(
                category=row["goal_category"].strip(),
                level=row["goal_level"].strip(),
            ))


def load_schedules(data_dir: str) -> dict[str, list[ClassPeriod]]:
    """Returns dict of class_id -> list of ClassPeriod."""
    schedules: dict[str, list[ClassPeriod]] = defaultdict(list)
    path = f"{data_dir}/schedules.csv"
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            class_id = row["class_id"].strip()
            day = row["day"].strip()
            period = int(row["period"].strip())
            class_name = row["class_name"].strip()
            if day not in DAYS:
                raise ValueError(f"schedules.csv: invalid day '{day}'")
            if not 1 <= period <= 8:
                raise ValueError(f"schedules.csv: period must be 1-8, got {period}")
            schedules[class_id].append(ClassPeriod(class_id, day, period, class_name))
    return dict(schedules)


def load_requirements(data_dir: str, students: dict[str, Student]) -> dict[str, Requirement]:
    reqs = {}
    path = f"{data_dir}/requirements.csv"
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row["student_name"].strip()
            if name not in students:
                raise ValueError(f"requirements.csv: unknown student '{name}'")
            reqs[name] = Requirement(
                student_name=name,
                push_in_individual=int(row.get("push_in_individual", 0) or 0),
                push_in_group=int(row.get("push_in_group", 0) or 0),
                pull_out_individual=int(row.get("pull_out_individual", 0) or 0),
                pull_out_group=int(row.get("pull_out_group", 0) or 0),
                max_group_size=int(row.get("max_group_size", 2) or 2),
            )
    return reqs


def load_exclusions(data_dir: str, students: dict[str, Student]) -> set[frozenset]:
    exclusions = set()
    path = f"{data_dir}/exclusions.csv"
    try:
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                a = row["student_name_1"].strip()
                b = row["student_name_2"].strip()
                for name in (a, b):
                    if name not in students:
                        raise ValueError(f"exclusions.csv: unknown student '{name}'")
                exclusions.add(frozenset({a, b}))
    except FileNotFoundError:
        pass
    return exclusions


def build_student_busy_slots(
    students: dict[str, Student],
    schedules: dict[str, list[ClassPeriod]],
) -> dict[str, set[tuple[str, int]]]:
    """Returns {student_name: set of (day, period) they cannot be pulled out}."""
    busy: dict[str, set[tuple[str, int]]] = {}
    warnings = []

    for name, student in students.items():
        class_periods = schedules.get(student.class_id, [])
        blocked = set()
        has_science = False
        for cp in class_periods:
            is_restricted = cp.class_name in RESTRICTED_CLASSES
            if student.grade == 8 and cp.class_name in EIGHTH_GRADE_RESTRICTED:
                is_restricted = True
            if cp.class_name == "Science":
                has_science = True
            if is_restricted:
                blocked.add((cp.day, cp.period))
        if student.grade == 8 and not has_science:
            warnings.append(f"WARNING: 8th grader '{name}' (class_id={student.class_id}) has no Science period listed.")
        busy[name] = blocked

    for w in warnings:
        print(w)
    return busy


def build_push_in_slots(
    students: dict[str, Student],
    schedules: dict[str, list[ClassPeriod]],
) -> dict[str, dict[tuple[str, int], str]]:
    """Returns {student_name: {(day, period): class_name}} for push-in eligible slots."""
    result: dict[str, dict[tuple[str, int], str]] = {}
    for name, student in students.items():
        class_periods = schedules.get(student.class_id, [])
        eligible = {}
        for cp in class_periods:
            if cp.class_name in PUSH_IN_ELIGIBLE_CLASSES:
                if student.grade == 8 and cp.class_name == "Science":
                    pass  # 8th graders can still have push-in during science
                eligible[(cp.day, cp.period)] = cp.class_name
        result[name] = eligible
    return result


def load_all(data_dir: str):
    students = load_students(data_dir)
    load_goals(data_dir, students)
    schedules = load_schedules(data_dir)
    requirements = load_requirements(data_dir, students)
    exclusions = load_exclusions(data_dir, students)
    busy_slots = build_student_busy_slots(students, schedules)
    push_in_slots = build_push_in_slots(students, schedules)
    return students, schedules, requirements, exclusions, busy_slots, push_in_slots
