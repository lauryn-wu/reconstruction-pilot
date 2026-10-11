"""Small command-line interface; standard-library runtime only."""

import argparse
import json
from pathlib import Path
import sys
import zipfile

from .analysis import analyze
from .ledger import read_run, run_lock
from .runner import load_config, plan, run
from .study import DATA, load_tasks


def concise(report):
    if "decision" not in report:
        return report
    keys = ("mode","decision","simulated_decision","valid_cells","total_cells","complete_tasks",
            "first_attempt_valid_cells","attempt_status_counts","baseline_false_accepts","joint_cases",
            "source_vs_generic_bad","cost","last_stop")
    return {k:report[k] for k in keys}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Reconstruction pilot; offline unless run --execute is supplied.")
    sub = parser.add_subparsers(dest="command",required=True)
    for name in ("plan","run","simulate"):
        p = sub.add_parser(name)
        p.add_argument("--config",type=Path,default=DATA/"screen.json")
        if name!="plan":
            p.add_argument("--out",type=Path)
            p.add_argument("--limit",type=int)
        if name=="run":
            p.add_argument("--execute",action="store_true",help="Authorize paid API calls, subject to the run's $10 cap")
            p.add_argument("--retry-failed",action="store_true",help="Permit one additional attempt for unsuccessful cells")
        if name=="simulate":
            p.add_argument("--profile",choices=("clean","answer_bias","reconstruction"),default="clean")
    for name in ("analyze","errors","bundle"):
        p = sub.add_parser(name)
        p.add_argument("--out",type=Path,default=Path("runs/screen"))
    args = parser.parse_args(argv)
    try:
        if args.command in ("plan","run","simulate"):
            config,tasks = load_config(args.config),load_tasks()
            if args.command=="plan" or (args.command=="run" and not args.execute):
                result = plan(config,tasks)
                print(json.dumps(result,indent=2))
                return 0
            mode = args.profile if args.command=="simulate" else None
            directory = args.out or Path(f"runs/simulation-{mode}" if mode else "runs/screen")
            result = run(config,tasks,directory,execute=args.command=="run",simulation=mode,
                         limit=args.limit,retry=getattr(args,"retry_failed",False))
            print(json.dumps(concise(result),indent=2))
            print(f"Full report: {directory/'report.md'}")
            return 2 if result["decision"]=="incomplete" else 0
        if args.command=="errors":
            meta,attempts = read_run(args.out)
            errors = [{k:r[k] for k in ("id","job","status","detail","reserved")} for r in attempts if r["status"]!="valid"]
            print(json.dumps({"last_stop":meta.get("last_stop"),"unsuccessful_attempts":errors},indent=2))
            return 0
        with run_lock(args.out):
            report = analyze(args.out)
            if args.command=="bundle":
                target = args.out/"results.zip"
                # Explicit allowlist; never package .env, API keys, or arbitrary working files.
                with zipfile.ZipFile(target,"w",zipfile.ZIP_DEFLATED) as z:
                    for name in ("manifest.json","tasks.json","analysis.json","report.md","attempts.jsonl","failures.jsonl"):
                        z.write(args.out/name,arcname=name)
                print(target)
            else:
                print(json.dumps(concise(report),indent=2))
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print(f"Stopped: {exc}",file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
