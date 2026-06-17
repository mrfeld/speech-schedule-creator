# Special Education Session Scheduler

A local Python CLI tool that generates a weekly pull-out/push-in session schedule for a special education teacher's caseload.

## Running the Scheduler

```bash
python main.py --data-dir ./data
python main.py --data-dir ./data --output-csv my_schedule.csv
python main.py --data-dir ./data --max-attempts 100
```

Output: terminal grid + CSV saved to `<data-dir>/schedule_output.csv` by default.

`--max-attempts` (default 50) controls how many randomized attempts the scheduler runs
before keeping its best result; see [Retry search](#retry-search).

## Input Files

All files are CSV and live in the data directory you point to. Edit them in Excel or Google Sheets.

### `students.csv`
| Column | Description |
|--------|-------------|
| `name` | Student name — **primary key**, must be unique |
| `grade` | Grade level (e.g. `8`) |
| `class_id` | All students sharing a `class_id` follow the same class schedule all day |

### `goals.csv`
One row per goal. A student can have multiple goals.

| Column | Description |
|--------|-------------|
| `student_name` | Must match a name in `students.csv` |
| `goal_category` | e.g. `reading`, `math`, `behavior` |
| `goal_level` | Proficiency level at that goal (e.g. `1`, `2`, `3`) |

Goals are used to cluster students into compatible groups (same category + level = better match).

### `schedules.csv`
Full weekly schedule for each `class_id`. Include **all** periods — the program decides which ones are restricted. All students sharing a `class_id` are assumed to be in the same room for every period.

| Column | Description |
|--------|-------------|
| `class_id` | Matches `students.csv` |
| `day` | `Monday` through `Friday` |
| `period` | `1` through `8` |
| `class_name` | e.g. `Math`, `ELA`, `Gym`, `Lunch`, `Science`, `Social Studies`, `Art`, `History` |

**Automatically blocked (cannot schedule over):**
- All students: `Math`, `ELA`, `Gym`, `Lunch`
- 8th graders additionally: `Science`

**Push-in eligible (teacher goes to their classroom):**
- `ELA`, `Science`, `Social Studies`

### `requirements.csv`
| Column | Description |
|--------|-------------|
| `student_name` | Must match `students.csv` |
| `push_in_individual` | Required push-in individual sessions/week |
| `push_in_group` | Required push-in group sessions/week |
| `pull_out_individual` | Required pull-out individual sessions/week |
| `pull_out_group` | Required pull-out group sessions/week |
| `max_group_size` | Max number of students in any group session with this student |

### `exclusions.csv` (optional)
Pairs of students who must never be in the same group session.

| Column | Description |
|--------|-------------|
| `student_name_1` | First student |
| `student_name_2` | Second student |

## How Scheduling Works

### Teacher blocked periods
3 periods are blocked per day:
- 1 **Lunch** — automatically placed in Period 4, 5, or 6
- 2 **Prep/Admin** — placed in any period

For each day the algorithm exhaustively tries every valid block (lunch in P4–6 + 2 prep
periods) and keeps the one that preserves the most *session demand* in the remaining
open periods — i.e. periods where students who still need pull-out are free, or where
students who need push-in have an eligible class. On retry attempts (see
[Retry search](#retry-search)) it samples among the top-scoring blocks rather than always
taking the single best, so different attempts try different teacher schedules.

### Group formation
Groups are formed separately for push-in and pull-out:
- **Pull-out groups**: students with `pull_out_group > 0`. Exclusion pairs and `max_group_size` are enforced.
- **Push-in groups**: students with `push_in_group > 0` who share the same `class_id` (they must be in the same classroom). Same exclusion/size rules apply.

When placing a student, the grouper applies these **soft preferences** (honored when
feasible, but never at the cost of leaving a student ungrouped):
1. **Same group-session count** — prefer groups whose members need the same number of
   group sessions as the student. Mixed-count groups are still allowed when no same-count
   group fits.
2. **Goal similarity** — among feasible groups, prefer the best goal match: goals shared
   at the same category *and* level rank highest, then goals that merely share a category.

### Scheduling constraints
- Each student must be assigned **exactly** the number of sessions specified in `requirements.csv` — no more, no less.
- Each student may have **at most one session per day** across all session types.
- Group requirements are tracked **per member**. If a mixed-count group meets fewer
  sessions than a higher-need member requires, that member is topped up individually in
  the backfill step (grouped with still-eligible group-mates when possible, otherwise
  solo). Any remaining shortfall is reported per student against their actual requirement.

### Scheduling order (most constrained first)
1. Push-in group sessions
2. Pull-out group sessions
3. Push-in individual sessions
4. Pull-out individual sessions
5. **Backfill** — remaining open teacher slots are filled for any student who still has
   an unmet requirement, preferring to re-form sub-groups of existing groups before
   falling back to individual sessions.

### Retry search
The scheduler runs up to `--max-attempts` randomized attempts and keeps the result with
the fewest unschedulable sessions, stopping early if everything is scheduled. Attempt 1 is
deterministic; later attempts seed a PRNG that varies the group formation, the within-phase
ordering, and the teacher's blocked periods, so each attempt explores a different schedule.
The search is greedy with no backtracking within an attempt — randomized restarts are how
it explores alternatives.

### Session type tags in output
| Tag | Meaning |
|-----|---------|
| `PI` | Push-in individual |
| `PIG` | Push-in group |
| `PO` | Pull-out individual |
| `POG` | Pull-out group |

## File Structure

```
sped_scheduler/
├── main.py       # CLI entry point
├── models.py     # Dataclasses and constants
├── loader.py     # CSV parsing and validation
├── grouper.py    # Group formation logic
├── scheduler.py  # Constraint solving and slot assignment
├── output.py     # Terminal grid and CSV export
└── data/         # Your data files go here
    ├── students.csv
    ├── goals.csv
    ├── schedules.csv
    ├── requirements.csv
    └── exclusions.csv  (optional)
```

## Notes

- No external dependencies — standard library only (`csv`, `dataclasses`, `argparse`, `collections`, `itertools`)
- Runs on Python 3.10+ (uses `list[...]` / `dict[...]` type hints)
- The scheduler is greedy within each attempt (not exhaustive) but uses randomized retries to explore alternatives. If it can't meet a required session count, it reports the shortfall per student at the end.
- 8th graders with no Science period listed in their `class_id`'s schedule will trigger a warning.
