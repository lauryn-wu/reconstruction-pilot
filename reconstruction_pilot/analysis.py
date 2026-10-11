"""Frozen exploratory gates; neither rationales nor probes are mechanistic evidence."""

from collections import Counter
import json
import math
from pathlib import Path

from .ledger import money, read_run
from .study import solution


def rate(correct, valid, total):
    return {"correct":correct,"valid":valid,"total":total,"rate":correct/valid if valid else None}


def paired(benefit, harm, total):
    n = benefit + harm
    # Exact two-sided sign/McNemar test on discordant task pairs; descriptive only.
    p = min(1.0, 2*sum(math.comb(n,k) for k in range(min(benefit,harm)+1))/2**n) if n else 1.0
    return {"benefits":benefit,"harms":harm,"net_count":benefit-harm,
            "total":total,"net_rate":(benefit-harm)/total if total else None,
            "descriptive_exact_p":p}


def compute(manifest, attempts, last_stop=None):
    tasks, planned = manifest["tasks"], manifest["jobs"]
    expected_ids = {j["id"] for j in planned}
    if any(a["job"] not in expected_ids for a in attempts):
        raise ValueError("Ledger has an unplanned job")
    selected = {}
    first = {}
    for row in attempts:
        first.setdefault(row["job"],row)
        if row["status"] == "valid":
            selected.setdefault(row["job"],row)
    data = {k:json.loads(v["parsed"]) for k,v in selected.items()}
    checks = Counter()
    rows = []
    neutral_false = 0
    joints = []
    joint_families = Counter()
    benefit_families = Counter()
    bad_benefits = bad_harms = good_benefits = good_harms = 0
    paired_bad_total = paired_good_total = 0
    repair_false = foil_false_bad = 0
    quote_inventions = 0
    joint_rescues = 0

    for task in tasks:
        t = task["id"]
        d = {c: data.get(f"{t}/{c}") for c in [j["condition"] for j in planned if j["task_id"]==t]}
        verdict = lambda c: d[c]["verdict"] if d.get(c) else None
        solved = bool(d.get("solve") and d["solve"]["answer"] == task["answer"])
        checks["solve"] += solved
        for c in ("good_neutral","good_generic","good_source"):
            checks[c] += verdict(c)=="valid"
        checks["wrong_neutral"] += verdict("wrong_neutral")=="invalid"
        qualified = solved and verdict("good_neutral")=="valid" and verdict("wrong_neutral")=="invalid"
        checks["qualified"] += qualified
        false_accept = verdict("bad_neutral")=="valid"
        neutral_false += false_accept
        source_records = {}
        for probe, variant in (("probe_bad","bad"),("probe_good","good")):
            if not d.get(probe):
                continue
            by_role = {role:d[probe][label] for label,role in task["claim_roles"].items()}
            source_records[probe] = by_role
            correct_roles = []
            for role,item in by_role.items():
                gold = role=="anchor" or (role=="repair" and variant=="good")
                checks[f"{probe}_{role}"] += item["present"]==gold
                correct_roles.append(item["present"]==gold)
            checks[f"{probe}_all"] += all(correct_roles)
            if variant=="bad":
                repair_false += by_role["repair"]["present"]
                foil_false_bad += by_role["foil"]["present"]
                quote = " ".join(by_role["repair"]["quote"].split())
                raw_source = " ".join(solution(task,"bad").split())
                quote_inventions += bool(by_role["repair"]["present"] and quote and quote not in raw_source)
        bad_probe, good_probe = source_records.get("probe_bad"), source_records.get("probe_good")
        joint = bool(qualified and false_accept and bad_probe and good_probe
                     and bad_probe["repair"]["present"] and bad_probe["repair"]["quote"].strip()
                     and bad_probe["anchor"]["present"] and not bad_probe["foil"]["present"]
                     and good_probe["repair"]["present"] and good_probe["anchor"]["present"]
                     and not good_probe["foil"]["present"])
        if joint:
            joints.append(t)
            joint_families[task["family"]] += 1
            joint_rescues += verdict("bad_source")=="invalid" and verdict("bad_generic")=="valid"
        if verdict("bad_source") is not None and verdict("bad_generic") is not None:
            paired_bad_total += 1
            benefit = verdict("bad_source")=="invalid" and verdict("bad_generic")=="valid"
            harm = verdict("bad_source")=="valid" and verdict("bad_generic")=="invalid"
            bad_benefits += benefit
            bad_harms += harm
            benefit_families[task["family"]] += int(benefit)-int(harm)
        if verdict("good_source") is not None and verdict("good_generic") is not None:
            paired_good_total += 1
            good_benefits += verdict("good_source")=="valid" and verdict("good_generic")=="invalid"
            good_harms += verdict("good_source")=="invalid" and verdict("good_generic")=="valid"
        rows.append({"task":t,"family":task["family"],"template":task["template"],
                     "complete":all(d.values()),"qualified":qualified,"joint_proxy":joint,
                     "baseline_false_accept":false_accept if d.get("bad_neutral") else None,
                     "verdicts":{c:verdict(c) for c in d if c not in ("solve","probe_bad","probe_good")},
                     "source_probes":source_records})

    thresholds = manifest["config"]["thresholds"]
    controls = ["solve","good_neutral","good_generic","good_source","wrong_neutral",
                "probe_good_repair","probe_good_anchor","probe_good_foil",
                "probe_bad_anchor","probe_bad_foil"]
    control_pass = all(checks[c]>=thresholds["minimum_control_correct"] for c in controls)
    criteria = {
        "all_cells_complete":len(selected)==len(planned),
        "no_usage_assumption_breach":not any(a["assumption_breach"] for a in attempts),
        "controls_pass":control_pass,
        "enough_qualified_tasks":checks["qualified"]>=thresholds["minimum_qualified_tasks"],
        "baseline_failure_present":neutral_false>=thresholds["minimum_baseline_false_accepts"],
        "enough_joint_cases":len(joints)>=thresholds["minimum_joint_cases"],
        "joint_in_multiple_families":len(joint_families)>=thresholds["minimum_joint_families"],
        "joint_cases_rescued":joint_rescues>=thresholds["minimum_joint_rescues"],
        "repair_specific_attribution":repair_false-foil_false_bad>=thresholds["minimum_repair_over_foil_count"],
        "source_beats_generic":bad_benefits-bad_harms>=thresholds["minimum_net_rejection_gain"],
        "intervention_in_multiple_families":sum(v>0 for v in benefit_families.values())>=thresholds["minimum_intervention_families"],
        "limited_extra_rejection_of_valid_work":good_harms-good_benefits<=thresholds["maximum_excess_valid_rejections"],
    }
    if not criteria["all_cells_complete"] or not criteria["no_usage_assumption_breach"]:
        decision = "incomplete"
    elif not criteria["controls_pass"] or not criteria["enough_qualified_tasks"]:
        decision = "stop_controls_failed"
    elif not criteria["baseline_failure_present"]:
        decision = "stop_no_clear_failure"
    elif not all(criteria[k] for k in ("enough_joint_cases","joint_in_multiple_families","repair_specific_attribution")):
        decision = "stop_no_reconstruction_specific_signal"
    elif not all(criteria[k] for k in ("source_beats_generic","intervention_in_multiple_families","limited_extra_rejection_of_valid_work","joint_cases_rescued")):
        decision = "stop_no_specific_intervention_gain"
    else:
        decision = "continue_to_independent_mechanistic_check"
    simulation = manifest["mode"] != "live"
    return {
        "mode":manifest["mode"],"model":manifest["config"]["model"],
        "decision":"simulation_only" if simulation else decision,
        "simulated_decision":decision if simulation else None,
        "valid_cells":len(selected),"total_cells":len(planned),
        "complete_tasks":sum(r["complete"] for r in rows),"total_tasks":len(tasks),
        "first_attempt_valid_cells":sum(r["status"]=="valid" for r in first.values()),
        "attempt_status_counts":dict(Counter(a["status"] for a in attempts)),
        "criteria":criteria,"thresholds":thresholds,
        "control_accuracy":{c:rate(checks[c],sum(
            f"{t['id']}/{'_'.join(c.split('_')[:2]) if c.startswith('probe_') else c}" in data
            for t in tasks),len(tasks)) for c in controls},
        "baseline_false_accepts":neutral_false,"qualified_tasks":checks["qualified"],
        "joint_cases":joints,"joint_by_family":dict(joint_families),"joint_rescues":joint_rescues,
        "bad_probe_repair_false_attributions":repair_false,"bad_probe_foil_false_attributions":foil_false_bad,
        "bad_probe_repair_nonverbatim_quotes":quote_inventions,
        "source_vs_generic_bad":paired(bad_benefits,bad_harms,paired_bad_total),
        "source_vs_generic_good":paired(good_benefits,good_harms,paired_good_total),
        "bad_intervention_net_by_family":dict(benefit_families),
        "cost":{"reserved_exposure_usd":money(sum(max(a["reserved"],a["actual"] or 0) for a in attempts)),
                "known_usage_cost_usd":money(sum(a["actual"] or 0 for a in attempts)),
                "unknown_cost_attempts":sum(a["actual"] is None for a in attempts),
                "budget_usd":manifest["config"]["budget_usd"]},
        "last_stop":last_stop,"tasks":rows,
        "interpretation":"Exploratory behavioral screen. Attribution after a verdict can reflect post-hoc rationalization; it does not establish internal reconstruction, causal mediation, or novelty. Six templates provide limited diversity."
    }


def analyze(directory):
    directory = Path(directory)
    meta, attempts = read_run(directory)
    report = compute(meta["manifest"],attempts,meta.get("last_stop"))
    (directory/"analysis.json").write_text(json.dumps(report,indent=2)+"\n")
    exported = []
    for a in attempts:
        a = dict(a)
        for key in ("request","parsed","raw"):
            a[key] = json.loads(a[key]) if a[key] is not None else None
        exported.append(a)
    (directory/"attempts.jsonl").write_text("".join(json.dumps(a,ensure_ascii=False)+"\n" for a in exported))
    failures = [a for a in exported if a["status"]!="valid"]
    (directory/"failures.jsonl").write_text("".join(json.dumps(a,ensure_ascii=False)+"\n" for a in failures))
    lines = ["# Reconstruction screen", "",f"Mode: **{report['mode']}**", "",
             f"Decision: **{report['decision']}**", "",
             f"Completed: {report['valid_cells']}/{report['total_cells']} cells; {report['complete_tasks']}/24 matched sets.",
             f"Reserved exposure: ${report['cost']['reserved_exposure_usd']}; known usage: ${report['cost']['known_usage_cost_usd']}.","",
             f"Baseline mistaken approvals: {report['baseline_false_accepts']}; joint proxy cases: {len(report['joint_cases'])}.",
             f"Source vs generic net correction gain: {report['source_vs_generic_bad']['net_count']}/24.","",
             "## Frozen criteria", "", "| Criterion | Passed |", "| --- | --- |"]
    lines += [f"| {k} | {v} |" for k,v in report["criteria"].items()]
    lines += ["",report["interpretation"],"", "Transport errors, invalid output, missing cells, and truncation are not reasoning failures.",
              "The exact paired p-values are descriptive; tasks share six templates and are not 24 independent problem families."]
    if report["last_stop"]:
        lines += ["",f"Last stop: {report['last_stop']['reason']}"]
    if report["mode"]!="live":
        lines += ["",f"SYNTHETIC FIXTURE ONLY. Simulated gate: {report['simulated_decision']}."]
    (directory/"report.md").write_text("\n".join(lines)+"\n")
    return report
