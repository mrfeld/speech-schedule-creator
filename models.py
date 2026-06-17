from dataclasses import dataclass, field
from typing import Optional

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

RESTRICTED_CLASSES = {"Math", "ELA", "Gym", "Lunch"}
EIGHTH_GRADE_RESTRICTED = {"Science"}
PUSH_IN_ELIGIBLE_CLASSES = {"ELA", "Science", "Social Studies"}

SESSION_PULL_OUT_INDIVIDUAL = "pull_out_individual"
SESSION_PULL_OUT_GROUP = "pull_out_group"
SESSION_PUSH_IN_INDIVIDUAL = "push_in_individual"
SESSION_PUSH_IN_GROUP = "push_in_group"

SESSION_TAGS = {
    SESSION_PULL_OUT_INDIVIDUAL: "PO",
    SESSION_PULL_OUT_GROUP: "POG",
    SESSION_PUSH_IN_INDIVIDUAL: "PI",
    SESSION_PUSH_IN_GROUP: "PIG",
}


@dataclass
class Goal:
    category: str
    level: str


@dataclass
class Student:
    name: str
    grade: int
    class_id: str
    goals: list[Goal] = field(default_factory=list)


@dataclass
class Requirement:
    student_name: str
    push_in_individual: int
    push_in_group: int
    pull_out_individual: int
    pull_out_group: int
    max_group_size: int


@dataclass(frozen=True)
class TimeSlot:
    day: str
    period: int

    def __str__(self):
        return f"{self.day} P{self.period}"


@dataclass
class ClassPeriod:
    class_id: str
    day: str
    period: int
    class_name: str


@dataclass
class Group:
    students: list[str]
    session_type: str


@dataclass
class ScheduledSession:
    slot: TimeSlot
    students: list[str]
    session_type: str
    class_name: Optional[str] = None  # for push-in sessions
