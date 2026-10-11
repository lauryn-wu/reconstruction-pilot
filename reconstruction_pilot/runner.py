"""Offline by default; live requests require an explicit --execute."""

from datetime import date
import hashlib
import json
from pathlib import Path

from .analysis import analyze
from .ledger import BudgetExhausted, Ledger, cost, dollars, money, run_lock
from .provider import Anthropic, ProviderError, Result
from .study import DATA, PROBES, canonical, digest, jobs, messages_for, output_limit, solution


def load_config(path=None):
    config = json.loads(Path(path or DATA/"screen.json").read_text())
    if not 0 < dollars(config["budget_usd"]) <= dollars("10"):
        raise ValueError("The pilot budget must be positive and at most $10")
    if config["model"]!="claude-sonnet-5-5" or config["effort"]!="high":
        raise ValueError("This reviewed protocol uses Sonnet 5.5 with high adaptive effort")
    if dollars(config["input_usd_per_million"]) < dollars("2") or dollars(config["output_usd_per_million"]) < dollars("10"):
        raise ValueError("Configured prices cannot undercut the reviewed list prices")
    for key in ("max_input_tokens","input_margin_tokens","max_output_tokens","probe_max_output_tokens",
                "max_attempts_per_cell","timeout_seconds","seed"):
        if type(config[key]) is not int or config[key] <= 0:
            raise ValueError(f"{key} must be a positive integer")
    if config["input_margin_tokens"] < 256 or config["max_input_tokens"] <= config["input_margin_tokens"]:
        raise ValueError("Keep at least 256 tokens of input headroom")
    if config["max_output_tokens"] < 4096 or config["probe_max_output_tokens"] < 2048:
        raise ValueError("Do not shrink output/thinking allowances to induce failures")
    if config["max_attempts_per_cell"] not in (1,2):
        raise ValueError("At most two explicitly requested attempts per cell")
    if not date.fromisoformat(config["pricing_checked"]) <= date.fromisoformat(config["pricing_valid_through"]):
        raise ValueError("Invalid pricing dates")
    frozen = json.loads((DATA/"screen.json").read_text())
    if config["thresholds"] != frozen["thresholds"] or config["seed"] != frozen["seed"]:
        raise ValueError("This pilot's sampling and continuation criteria are frozen")
    return config


def code_hash():
    h = hashlib.sha256()
    for p in sorted(Path(__file__).parent.glob("*.py")):
        h.update(p.name.encode()+b"\0"+p.read_bytes()+b"\0")
    return h.hexdigest()


def manifest_for(config, tasks, mode):
    return dict(version=1, mode=mode, config=config, tasks=tasks, jobs=jobs(tasks,config["seed"]),
                dataset_sha256=digest(tasks), code_sha256=code_hash())


def plan(config, tasks):
    scheduled = jobs(tasks,config["seed"])
    reservation = sum(cost(config,config["max_input_tokens"],output_limit(config,j)) for j in scheduled)
    return dict(model=config["model"], effort=config["effort"], matched_sets=len(tasks),
                templates=len({t["template"] for t in tasks}), generation_requests=len(scheduled),
                grading_and_solving_requests=sum(j["kind"]!="probe" for j in scheduled),
                source_probe_requests=sum(j["kind"]=="probe" for j in scheduled),
                first_pass_reserved_usd=money(reservation), budget_usd=config["budget_usd"],
                retry_headroom_usd=money(max(0,dollars(config["budget_usd"])-reservation)),
                first_pass_fits=reservation<=dollars(config["budget_usd"]),
                dataset_sha256=digest(tasks), pricing_valid_through=config["pricing_valid_through"],
                network_requests_made=0)


def simulated(task, job, profile):
    """Artificial fixtures for testing the analysis pipeline, never model observations."""
    c = job["condition"]
    if job["kind"]=="solve":
        parsed = {"reason":"SYNTHETIC FIXTURE", "answer":task["answer"]}
    elif job["kind"]=="grade":
        valid = c.startswith("good")
        if profile in ("answer_bias","reconstruction") and c.startswith("bad"):
            valid = not (profile=="reconstruction" and c=="bad_source")
        parsed = {"reason":"SYNTHETIC FIXTURE", "verdict":"valid" if valid else "invalid"}
    else:
        good = c=="probe_good"
        parsed = {}
        for label,role in task["claim_roles"].items():
            present = role=="anchor" or (role=="repair" and (good or profile=="reconstruction"))
            parsed[label] = {"present":present,"quote":task[role] if present else ""}
    return Result("valid",parsed,canonical(parsed),0,0,{"synthetic":True,"profile":profile},"SIMULATED")


def run(config, tasks, directory, *, execute=False, simulation=None, limit=None, retry=False,
        provider_factory=Anthropic, progress=print):
    if execute and simulation:
        raise ValueError("Live and simulated modes are mutually exclusive")
    if not execute and not simulation:
        return plan(config,tasks)
    if simulation not in (None,"clean","answer_bias","reconstruction"):
        raise ValueError("Unknown simulation")
    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError("Limit must be positive")
    if execute and not date.fromisoformat(config["pricing_checked"]) <= date.today() <= date.fromisoformat(config["pricing_valid_through"]):
        raise ValueError("Pricing snapshot is outside its validity window; verify pricing before starting/resuming")
    if not plan(config,tasks)["first_pass_fits"]:
        raise ValueError("The complete first pass does not fit the configured cap; no requests sent")
    mode = "live" if execute else f"simulation:{simulation}"
    manifest = manifest_for(config,tasks,mode)
    directory = Path(directory)
    with run_lock(directory):
        ledger = Ledger(directory,manifest)
        try:
            for filename,value in (("manifest.json",manifest),("tasks.json",tasks)):
                path = directory/filename
                if path.exists() and json.loads(path.read_text()) != value:
                    raise ValueError(f"Saved {filename} changed; refusing to resume")
                path.write_text(json.dumps(value,indent=2)+"\n")
            if any(r["assumption_breach"] for r in ledger.attempts()):
                raise ValueError("A usage/model assumption was violated previously; this run stays halted for review")
            provider = provider_factory(config) if execute else None
            task_map = {t["id"]:t for t in tasks}
            sent = 0
            stopped = False
            for job in manifest["jobs"]:
                history = ledger.attempts()
                previous = [r for r in history if r["job"]==job["id"]]
                if any(r["status"]=="valid" for r in previous):
                    continue
                if previous and (not retry or len(previous)>=config["max_attempts_per_cell"]):
                    continue
                parent = None
                if job["condition"] in PROBES:
                    parent_job = f"{job['task_id']}/{PROBES[job['condition']]}"
                    parent = next((r for r in history if r["job"]==parent_job and r["status"]=="valid"),None)
                    if parent is None:
                        continue
                if limit is not None and sent>=limit:
                    ledger.stop(f"Reached requested limit of {limit} new generation calls; resume the same directory.")
                    stopped = True
                    break
                task = task_map[job["task_id"]]
                messages = messages_for(task,job,parent["text"] if parent else None)
                max_tokens = output_limit(config,job)
                reservation = cost(config,config["max_input_tokens"],max_tokens) if execute else 0
                if ledger.exposure()+reservation > ledger.limit:
                    ledger.stop("Budget reached. Remaining cells are incomplete; do not delete the ledger to continue spending.")
                    stopped = True
                    break
                try:
                    counted = provider.count(messages,job["kind"]) if execute else 0
                except ProviderError as exc:
                    ledger.stop(f"Token count failed before generation for {job['id']}: {exc}")
                    stopped = True
                    break
                if counted+config["input_margin_tokens"] > config["max_input_tokens"]:
                    ledger.stop(f"Input guard for {job['id']}: counted {counted}, plus headroom exceeds {config['max_input_tokens']}. No generation sent.")
                    stopped = True
                    break
                request = provider.body(messages,job["kind"],max_tokens) if execute else {"messages":messages,"synthetic":True}
                attempt = ledger.reserve(job["id"],reservation,counted,request,
                                         parent_id=parent["id"] if parent else None,retry=retry)
                if attempt is None:
                    continue
                sent += 1
                progress(f"{job['id']} | reserved ${money(ledger.exposure())} / ${config['budget_usd']}")
                try:
                    result = provider.generate(messages,job["kind"],max_tokens) if execute else simulated(task,job,simulation)
                except ProviderError as exc:
                    ledger.finish(attempt,status="transport_error",detail=str(exc))
                    ledger.stop(f"{job['id']}: {exc}. No automatic retry. Resolve the error, then resume with --retry-failed.")
                    stopped = True
                    break
                # Unexpected caching is charged conservatively at twice base input and halts collection.
                actual = cost(config,result.input_tokens+2*result.cache_tokens,result.output_tokens) if (
                    execute and result.input_tokens is not None and result.output_tokens is not None) else (0 if not execute else None)
                reported_model = result.raw.get("model") if isinstance(result.raw,dict) else None
                breach = execute and (actual is None or actual>reservation or result.cache_tokens>0
                    or (result.input_tokens or 0)>config["max_input_tokens"]
                    or (result.output_tokens or 0)>max_tokens
                    or (reported_model is not None and reported_model!=config["model"]))
                ledger.finish(attempt,status=result.status,actual=actual,parsed=result.parsed,text=result.text,
                              raw=result.raw,detail=result.stop,input_tokens=result.input_tokens,
                              output_tokens=result.output_tokens,assumption_breach=breach)
                if breach or result.status!="valid":
                    ledger.stop(f"{job['id']}: {'usage/model assumption breach' if breach else result.status}. Inspect failures.jsonl and attempts.jsonl; no automatic retry.")
                    stopped = True
                    break
            if not stopped:
                ledger.stop("Collection pass finished. Failed/dependent cells, if any, remain incomplete.")
        except KeyboardInterrupt:
            ledger.stop("Interrupted. Any pending request keeps its full reservation; --retry-failed permits one explicit retry.")
            progress("Interrupted safely; saved requests retain their reservations.")
        finally:
            ledger.close()
            # Always make the completed portion and diagnostic errors inspectable.
            analyze(directory)
    return analyze(directory)
