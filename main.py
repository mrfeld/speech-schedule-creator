import argparse
import os
import random
import sys
from loader import load_all
from grouper import form_pull_out_groups, form_push_in_groups
from scheduler import build_schedule
from output import print_schedule, write_csv, print_summary
from models import DAYS


def main():
    parser = argparse.ArgumentParser(description="Special Education Session Scheduler")
    parser.add_argument("--data-dir", required=True, help="Directory containing CSV input files")
    parser.add_argument("--output-csv", default=None, help="Path for CSV output (default: <data-dir>/schedule_output.csv)")
    parser.add_argument("--max-attempts", type=int, default=50, help="Max retry attempts if sessions cannot be scheduled (default: 50)")
    args = parser.parse_args()

    data_dir = args.data_dir
    if not os.path.isdir(data_dir):
        print(f"Error: data directory '{data_dir}' not found.", file=sys.stderr)
        sys.exit(1)

    output_csv = args.output_csv or os.path.join(data_dir, "schedule_output.csv")

    print(f"Loading data from {data_dir}...")
    try:
        students, schedules, requirements, exclusions, busy_slots, push_in_slots = load_all(data_dir)
    except (FileNotFoundError, ValueError, KeyError) as e:
        print(f"Error loading data: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Loaded {len(students)} students.")

    from models import TimeSlot
    all_slots = {TimeSlot(day=day, period=p) for day in DAYS for p in range(1, 9)}
    all_slot_keys = {(day, p) for day in DAYS for p in range(1, 9)}

    best_result = None
    best_unscheduled_count = float("inf")
    winning_attempt = 0

    for attempt in range(1, args.max_attempts + 1):
        rng = None if attempt == 1 else random.Random(attempt)

        pull_out_groups = form_pull_out_groups(students, requirements, exclusions, busy_slots, all_slot_keys, rng=rng)
        push_in_groups = form_push_in_groups(students, requirements, exclusions, push_in_slots, rng=rng)

        sessions, unscheduled, lunch_slots, prep_slots = build_schedule(
            students, requirements, pull_out_groups, push_in_groups, busy_slots, push_in_slots, rng=rng
        )

        if len(unscheduled) < best_unscheduled_count:
            best_unscheduled_count = len(unscheduled)
            best_result = (sessions, unscheduled, lunch_slots, prep_slots, pull_out_groups, push_in_groups)
            winning_attempt = attempt

        if not unscheduled:
            break

    sessions, unscheduled, lunch_slots, prep_slots, pull_out_groups, push_in_groups = best_result

    if best_unscheduled_count == 0:
        if winning_attempt == 1:
            print(f"Scheduled all sessions on first attempt.")
        else:
            print(f"Scheduled all sessions on attempt {winning_attempt} of {attempt}.")
    else:
        print(f"Could not fully schedule after {attempt} attempt(s). Best result has {best_unscheduled_count} unschedulable session(s).")

    print(f"Pull-out groups: {len(pull_out_groups)}, Push-in groups: {len(push_in_groups)}")

    print_schedule(sessions)
    print_summary(sessions, requirements, unscheduled, lunch_slots, prep_slots)

    write_csv(sessions, output_csv)
    print(f"Schedule saved to {output_csv}")


if __name__ == "__main__":
    main()
