import os

# el reads the session id the agent's harness exposes (acceptance: done in one session, accepted in another);
# the suite decides it per test and never inherits the session of the terminal that runs it
for _key in ("CLAUDE_CODE_SESSION_ID", "EL_SESSION"):
    os.environ.pop(_key, None)
