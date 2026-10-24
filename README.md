# CareRoute — synthetic clinic intake prototype

A runnable, standalone community-clinic appointment intake and administrative-routing demonstration. **Newly invented synthetic records only. No diagnosis, treatment, real booking, real notification or clinical service.** This project has its own workspace and Git metadata and is unrelated to OCS.

## Submission contents

- [Main submission report](reports/submission-report.md) — problem, research, implementation, measured results and limitations.
- [Printable report](reports/submission-report.pdf) and [self-contained HTML report](reports/submission-report.html).
- [Five-minute demonstration guide](DEMO.md).
- [Test report and requirement coverage](reports/test-report.md), [executed evaluation](reports/generated/evaluation.md), and machine-readable run artifacts in `reports/generated/`.
- [Jev paper review](reports/research-update.md) and [workflow paper review](reports/research-workflow-update.md): methods, results and limitations of all seven main papers were read.
- [Implementation/API notes](reports/implementation.md), [safety note](reports/safety-note.md), and [44 invented fixtures](fixtures/synthetic-cases.json).
- Complete source in `clinic/` and `static/`, executable tests in `tests/`, reproduction/packaging tools in `tools/`.

The downloadable submission archive is generated as `dist/careroute-submission.zip`. It excludes databases, credentials, caches and Git metadata, and includes a SHA-256 manifest. The app starts with an empty database after extraction.

## Run

Requires Python **3.11 or later** with SQLite; there are no third-party runtime dependencies. From the extracted project directory:

```sh
python3 -m clinic.server --port 8080 --db var/demo.sqlite3
```

Open local address `127.0.0.1:8080` in your browser. This local demonstration intentionally binds only to loopback. Stop with Ctrl+C. SQLite requests/audit persist across restarts; live processes do not.

The **Staff workspace** tab uses public, synthetic-demo accounts:

| Account | Password | Purpose |
|---|---|---|
| `reviewer` | `demo-reviewer` | Claim, review, override and record synthetic bookings |
| `supervisor` | `demo-supervisor` | Second review of a proposed emergency downgrade |

These are deliberately public demonstration credentials, not production authentication. Real clinical use is unsupported by this prototype.

## Operating modes

| Mode | Behavior |
|---|---|
| No AI (default) | Immediate local emergency guards; ordinary narrative goes to staff review through H05. It never claims to have understood unassessed text. |
| Replay | Reuses an authored assessment only for the exact selected synthetic fixture. Clearly labelled; no live inference. Persistence and staffing use the current demonstration, not the fixture's simulated fault fields. |
| Jev direct | Implemented finite-choice route plus defer adapter; shared guards apply. Requires `TYPESAFE_API_KEY` (or `JEV_API_KEY`). |
| Jev decomposed | Implemented focused Choice assessments plus rules. Same credentials. |
| Structured LLM | Equivalent bounded assessments via a structured-output API; requires `CLINIC_LLM_API_KEY` and an explicit `CLINIC_LLM_MODEL`. |
| Degraded | Missing credentials, timeout or invalid response produces human-review fallback while preserving emergency guidance. |

Enter keys securely in environment settings; do not place them in source or chat. The default requested Jev version is `jev-1.13.0`, configurable with `CLINIC_JEV_MODEL`; availability and live behavior have not been verified here. API destinations are fixed to `api.typesafe.ai` and `api.openai.com`; no arbitrary endpoint URL is accepted. No live-model calls were made for the submitted results.

`python3 tools/evaluate_live.py` prints a paired experiment plan without making calls. After securely configuring keys, `--execute` explicitly starts billable requests and stores every attempt, guarded route, failure and model version. `--arms jev_direct jev_decomposed` limits the comparison to Jev; `--limit` selects the same visible development subset for each arm. The dry-run was checked; actual provider execution remains unverified. These fixtures must not be presented as a held-out benchmark.

## Reproduce verification

```sh
python3 tools/run_checks.py
python3 tools/evaluate.py
python3 tools/validate_spec.py
```

Browser checks use Playwright and Chromium (the app itself does not):

```sh
python3 -m pip install -r requirements-dev.txt
python3 -m playwright install chromium
python3 tools/browser_check.py
```

The browser checker uses an existing system Chromium when available, otherwise Playwright's installed Chromium. It creates isolated temporary databases. See the actual counts and limitations in [the test report](reports/test-report.md). `make run`, `make test`, `make evaluate`, `make browser` and `make package` are shortcuts where Make is installed.

## Important result and boundary

Final policy `demo-policy-0.3` conservatively sends unassessed ordinary narratives to humans. On the comparable authored examples it produced zero emergency-route misses out of 13 and zero incorrect routine suggestions out of 32 nonroutine references, **but escalated all six routine references**. This is a workload tradeoff on visible invented examples, not proof of clinical safety. Reviewer handling time, human comprehension and live-model accuracy were not measured.

The original seven [specification documents](docs/01-requirements.md) remain as labelled design snapshots. Original policy 0.1 fixtures and the failed initial policy 0.2 baseline are preserved; [implementation notes](reports/implementation.md) explain subsequent changes. Actual jurisdiction, clinical policy, staffing contacts, supported populations and error thresholds remain unapproved. None are inferred from the user's timezone.
