import os

# el reads the session id the agent's harness exposes (acceptance: done in one session, accepted in another);
# the suite decides it per test and never inherits the session of the terminal that runs it
for _key in ("CLAUDE_CODE_SESSION_ID", "EL_SESSION"):
    os.environ.pop(_key, None)

# el writes its onboarding block into the agent's instruction file (CLAUDE.md / AGENTS.md) at `case new` and keeps it
# fresh on entry; the suite's temporary projects stay without it unless a test switches it on (tests/test_onboarding_0925.py)
os.environ["EL_ONBOARDING"] = "0"

# a new case carries the rule «two hands» from `case new` (feedback 2026-09-25); the suite's cases are written without it
# unless a test switches it on (tests/test_two_hands_default_0925.py) — hundreds of older tests close a phase by one hand
os.environ["EL_TWO_HANDS"] = "0"
