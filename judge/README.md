# judge

Grades saved runs against ground truth. No search or agent code lives here.

- `leaderboard.py` — Matches each returned company to the ground truth by domain or name, scores precision, recall, F1, and exact match per question, and builds the board across trials. Run it with `python -m judge.leaderboard`.
- `tests/` — Offline tests for matching and board math.
