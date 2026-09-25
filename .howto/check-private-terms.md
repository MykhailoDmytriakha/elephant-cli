when: before a commit · a real name, a client, a ticket number, an endpoint, a host from a live case in code, tests, docs or a commit message · «business data in files git carries»
summary: scan what goes to git for the local private-terms list, fix a hit with a neutral example of the same form

1. `python3 scripts/check_private_terms.py` — the working tree (tracked + new files git does not ignore) and the messages of unpushed commits; `--staged` — the index, what the next commit carries.
2. A hit prints `file:line: «term» — the line`. Rephrase with an invented example of the same form and, where a test counts length, the same length (`/v3/app/test/log-generator` for a real path). Never delete the term from the list to go green.
3. A new name from a live case → add it to `## Private terms` of the local CLAUDE.md (one per line; `<term>` for a short word that sits inside ordinary words). The list never goes to git — it would be the leak.
4. Exit 2 «nothing checked» means there is no list on this machine — not clean.
5. Once per clone, the hook: `ln -s ../../scripts/check_private_terms.py .git/hooks/pre-commit` — every commit checks its index; a hit stops it.
6. A term already pushed stays in the history: the current files are cleaned by a commit; the history only by a rewrite — the owner's decision (the 2026-09-22 rewrite kept a local bundle).
