# Reproduce the saved reconstruction analysis

The committed export is sufficient to recompute the analysis without API access. Run the following from the repository root with Python 3.11+. It reads the saved manifest and responses, converts the exported parsed objects back to the analysis function's input format, and checks the entire report against the committed result. It does not write to the archive or create a spending ledger.

```bash
python3 - <<'PY'
import json
from pathlib import Path
from reconstruction_pilot.analysis import compute

root = Path("results/2026-10-11-reconstruction")
manifest = json.loads((root / "manifest.json").read_text())
saved = json.loads((root / "analysis.json").read_text())
attempts = [json.loads(line) for line in (root / "attempts.jsonl").read_text().splitlines()]
for attempt in attempts:
    for key in ("request", "parsed", "raw"):
        value = attempt[key]
        attempt[key] = json.dumps(value) if value is not None else None
recomputed = compute(manifest, attempts, saved["last_stop"])
if recomputed != saved:
    raise SystemExit("Saved and recomputed analyses differ.")
print("Saved analysis reproduced exactly.")
print(json.dumps({key: recomputed[key] for key in (
    "decision", "valid_cells", "total_cells", "baseline_false_accepts", "joint_cases"
)}, indent=2))
PY
```

Expected: `stop_no_clear_failure`, 240 valid cells out of 240, zero baseline mistaken approvals, and an empty joint-case list.

The export contains the frozen model settings, exact tasks, requests, raw responses, and analysis. `checkout-at-archive.txt` records the checkout used when committing the export; it is not a substitute for the run's source hash in `manifest.json`.

The operational `analyze` and `bundle` commands use the local SQLite run ledger. That ledger is intentionally absent from the committed export. Use the read-only command above for the committed results, and retain the original local ledger if you need to inspect or resume a live run.
