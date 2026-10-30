# Running the tests

    .\.venv\Scripts\python.exe -m unittest discover -s tests

That is the whole suite. On 30 Oct 2026 at `95891cd` it collects **291 tests, 18 skipped, 0 failures** (about 60 s). No
`PYTHONPATH` is needed: `unittest discover -s tests` puts `tests/` on the path itself. (`tests.test_x` imports use the repo
root, which is the working directory.)

Skipped (18): 15 need the optional ML dependency group (`uv sync --group ml`), 1 needs `lxml` for the Milestone XSD, 1 needs
`numpy`, 1 needs private saved sources.

## Why one report said 142 and an earlier one said 275

The 142 was not a full run. It came from naming about ten modules on the command line
(`unittest tests.test_ortru tests.test_ortru_server tests.test_ortru_history tests.test_assessment_job ...`), which runs only
those modules. The 275 was a full discovery run before Gate 1's additions; 275 + 16 new tests (13 in `test_ortru_history.py`,
3 in `test_ortru_server.py`) = 291. Earlier notes that `test_native_actions` needs `PYTHONPATH=tests` were wrong: it runs, with
its 5 tests, under plain discovery.

Quote the "Ran N tests" line of the discovery command above, not of a module list.
