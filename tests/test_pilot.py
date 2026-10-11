import copy
from datetime import date, timedelta
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from reconstruction_pilot.analysis import analyze, compute
from reconstruction_pilot.cli import main
from reconstruction_pilot.ledger import BudgetExhausted, Ledger, cost, dollars, read_run, run_lock
from reconstruction_pilot.provider import Anthropic, ProviderError, decode, parse_output
from reconstruction_pilot.runner import load_config, manifest_for, plan, run, simulated
from reconstruction_pilot.study import (build_tasks, canonical, jobs, load_tasks, messages_for,
                                      oracle, schema_for, solution, validate_tasks)


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = load_config()
        self.config["pricing_checked"] = date.today().isoformat()
        self.config["pricing_valid_through"] = (date.today()+timedelta(days=1)).isoformat()
        self.tasks = load_tasks()
        self.network = patch("urllib.request.urlopen",side_effect=AssertionError("Tests must never access the network"))
        self.network.start()
        self.addCleanup(self.network.stop)

    def fixture(self, profile="clean"):
        manifest = manifest_for(self.config,self.tasks,"live")
        tasks = {t["id"]:t for t in self.tasks}
        attempts = []
        for n,job in enumerate(manifest["jobs"],1):
            r = simulated(tasks[job["task_id"]],job,profile)
            attempts.append(dict(id=n,job=job["id"],status="valid",parsed=canonical(r.parsed),
                                 reserved=0,actual=0,assumption_breach=0))
        return manifest,attempts

    def fake_factory(self, failure=None):
        owner = self
        self.sent = []
        class Fake:
            def __init__(self, config):
                self.config = config
            def count(self, messages, kind):
                return 100
            def body(self, messages, kind, max_tokens):
                return dict(messages=messages,kind=kind,max_tokens=max_tokens)
            def generate(self, messages, kind, max_tokens):
                owner.sent.append((messages,kind,max_tokens))
                if failure:
                    failure()
                # Find the exact frozen prompt, including continuation parent when present.
                for task in owner.tasks:
                    for job in jobs([task],owner.config["seed"]):
                        candidate = messages_for(task,job,"parent" if job["kind"]=="probe" else None)
                        if candidate[0]==messages[0] and job["kind"]==kind:
                            return simulated(task,job,"clean")
                raise AssertionError("Unplanned request")
        return Fake

    def test_frozen_tasks_and_oracles(self):
        self.assertEqual(self.tasks,build_tasks())
        validate_tasks(self.tasks)
        self.assertEqual(len({t["template"] for t in self.tasks}),6)
        for t in self.tasks:
            self.assertEqual(t["answer"],oracle(t))
            self.assertNotEqual(t["answer"],t["wrong_answer"])
            self.assertIn(t["repair"],solution(t,"good"))
            self.assertNotIn(t["repair"],solution(t,"bad"))
            self.assertIn(t["bad_step"],solution(t,"bad"))
            self.assertNotIn(t["foil"],solution(t,"good"))

    def test_gold_error_is_detected(self):
        changed = copy.deepcopy(self.tasks)
        changed[0]["answer"] += 1
        with self.assertRaises(ValueError):
            validate_tasks(changed)

    def test_conditions_and_dependencies(self):
        js = jobs(self.tasks,self.config["seed"])
        self.assertEqual(len(js),240)
        self.assertEqual(len({j["id"] for j in js}),240)
        for t in self.tasks:
            subset = [j for j in js if j["task_id"]==t["id"]]
            self.assertEqual(sum(j["kind"]=="probe" for j in subset),2)
            probe = next(j for j in subset if j["condition"]=="probe_bad")
            with self.assertRaises(ValueError):
                messages_for(t,probe)
            ms = messages_for(t,probe,'{"reason":"actual response","verdict":"valid"}')
            self.assertEqual(ms[1]["content"],'{"reason":"actual response","verdict":"valid"}')
            self.assertNotIn("wrong_answer",canonical(ms))

    def test_first_pass_budget(self):
        p = plan(self.config,self.tasks)
        self.assertEqual(p["first_pass_reserved_usd"],"9.711360")
        self.assertTrue(p["first_pass_fits"])
        self.assertEqual(p["network_requests_made"],0)

    def test_terminal_json_and_code_fence(self):
        for text in ('{"reason":"ok","verdict":"invalid"}',
                     'Explanation first.\n{"reason":"ok","verdict":"invalid"}',
                     'Explanation first.\n```json\n{"reason":"ok","verdict":"invalid"}\n```'):
            self.assertEqual(parse_output(text,"grade")["verdict"],"invalid")

    def test_ambiguous_duplicate_and_wrong_types_rejected(self):
        for text in ('{"reason":"x","verdict":"valid","verdict":"invalid"}',
                     '{"reason":"x","verdict":"valid"}\ntrailing text',
                     '{"verdict":"valid"}\n{"reason":"x","verdict":"invalid"}',
                     '{"reason":"x","verdict":"valid","extra":1}'):
            self.assertIsNone(parse_output(text,"grade"))
        self.assertIsNone(parse_output('{"reason":"x","answer":true}',"solve"))

    def test_probe_false_attribution_remains_behavior_not_format_error(self):
        data = {k:{"present":True,"quote":"invented sentence"} for k in "ABC"}
        self.assertEqual(parse_output(canonical(data),"probe"),data)

    def test_truncation_does_not_score_parseable_text(self):
        r = decode({"stop_reason":"max_tokens","content":[{"type":"text","text":'{"reason":"x","verdict":"valid"}'}],
                    "usage":{"input_tokens":10,"output_tokens":4096}},"grade")
        self.assertEqual(r.status,"truncated")
        self.assertIsNone(r.parsed)

    def test_hidden_thinking_usage_and_malformed_response(self):
        r = decode({"stop_reason":"end_turn","content":[{"type":"thinking","thinking":"private"},
                   {"type":"text","text":'{"reason":"x","verdict":"valid"}'}],
                   "usage":{"input_tokens":12,"output_tokens":1200}},"grade")
        self.assertEqual(r.output_tokens,1200)
        self.assertNotIn("private",r.text)
        self.assertEqual(decode({"content":None},"grade").status,"malformed_response")

    def test_native_request_format_and_count(self):
        observed = []
        def transport(url,body,headers,timeout):
            observed.append((url,body))
            return {"input_tokens":100}
        with patch.dict("os.environ",{"ANTHROPIC_API_KEY":"unit-test-placeholder"}):
            p = Anthropic(self.config,transport)
            self.assertEqual(p.count([{"role":"user","content":"test"}],"grade"),100)
            b = p.body([{"role":"user","content":"test"}],"grade",4096)
        self.assertEqual(b["output_config"]["format"]["schema"],schema_for("grade"))
        self.assertEqual(b["thinking"],{"type":"adaptive"})
        self.assertNotIn("temperature",b)
        self.assertNotIn("max_tokens",observed[0][1])
        self.assertNotIn("cache_control",b)

    def test_clean_and_answer_bias_do_not_pass(self):
        for profile,expected in (("clean","stop_no_clear_failure"),("answer_bias","stop_no_reconstruction_specific_signal")):
            m,a = self.fixture(profile)
            self.assertEqual(compute(m,a)["decision"],expected)

    def test_joint_synthetic_fixture_passes(self):
        m,a = self.fixture("reconstruction")
        r = compute(m,a)
        self.assertEqual(r["decision"],"continue_to_independent_mechanistic_check")
        self.assertEqual(len(r["joint_cases"]),24)
        self.assertEqual(r["joint_rescues"],24)

    def test_reject_everything_intervention_fails_valid_controls(self):
        m,a = self.fixture("reconstruction")
        for row in a:
            if row["job"].endswith("/good_source"):
                row["parsed"] = canonical({"reason":"reject all","verdict":"invalid"})
        self.assertEqual(compute(m,a)["decision"],"stop_controls_failed")

    def test_generic_hallucination_does_not_qualify_as_reconstruction(self):
        m,a = self.fixture("reconstruction")
        tasks = {t["id"]:t for t in self.tasks}
        for row in a:
            if row["job"].endswith("/probe_bad"):
                task = tasks[row["job"].split("/")[0]]
                label = next(k for k,v in task["claim_roles"].items() if v=="foil")
                d = json.loads(row["parsed"])
                d[label] = {"present":True,"quote":"invented"}
                row["parsed"] = canonical(d)
        r = compute(m,a)
        self.assertFalse(r["criteria"]["repair_specific_attribution"])
        self.assertEqual(r["joint_cases"],[])

    def test_missing_or_failed_cells_stay_incomplete(self):
        m,a = self.fixture("reconstruction")
        for status in ("transport_error","truncated","invalid_format","pending"):
            changed = copy.deepcopy(a)
            changed[0].update(status=status,parsed=None,actual=None)
            self.assertEqual(compute(m,changed)["decision"],"incomplete")
        empty = compute(m,[])
        self.assertIsNone(empty["control_accuracy"]["solve"]["rate"])
        self.assertEqual(empty["control_accuracy"]["solve"]["valid"],0)

    def test_first_valid_selected_without_resampling_correctness(self):
        m,a = self.fixture("clean")
        duplicate = dict(a[0],id=999,parsed=canonical({"reason":"later","answer":-999}))
        self.assertEqual(compute(m,a+[duplicate])["control_accuracy"]["solve"]["correct"],24)

    def test_simulation_label_cannot_be_mistaken_for_live_evidence(self):
        r = run(self.config,self.tasks,self.root,simulation="reconstruction",progress=lambda _:None)
        self.assertEqual(r["decision"],"simulation_only")
        self.assertEqual(r["simulated_decision"],"continue_to_independent_mechanistic_check")
        with self.assertRaisesRegex(ValueError,"manifest changed"):
            run(self.config,self.tasks,self.root,execute=True,provider_factory=self.fake_factory(),progress=lambda _:None)

    def test_dry_run_never_initializes_provider(self):
        def forbidden(_):
            self.fail("Dry run instantiated a provider")
        r = run(self.config,self.tasks,self.root,provider_factory=forbidden)
        self.assertEqual(r["network_requests_made"],0)
        self.assertFalse((self.root/"ledger.sqlite3").exists())

    def test_resume_skips_completed_and_links_real_parent(self):
        factory = self.fake_factory()
        run(self.config,self.tasks,self.root,execute=True,limit=2,provider_factory=factory,progress=lambda _:None)
        run(self.config,self.tasks,self.root,execute=True,limit=1,provider_factory=factory,progress=lambda _:None)
        _,a = read_run(self.root)
        self.assertEqual(len(a),3)
        self.assertEqual(a[2]["parent_id"],a[1]["id"])
        self.assertEqual(json.loads(a[2]["request"])["messages"][1]["content"],a[1]["text"])

    def test_http_error_is_visible_and_keeps_reservation(self):
        def fail():
            raise ProviderError("HTTP 503: temporarily overloaded",503)
        factory = self.fake_factory(fail)
        r = run(self.config,self.tasks,self.root,execute=True,provider_factory=factory,progress=lambda _:None)
        self.assertEqual(len(self.sent),1)
        self.assertEqual(r["cost"]["unknown_cost_attempts"],1)
        self.assertIn("503",(self.root/"failures.jsonl").read_text())
        reserved = r["cost"]["reserved_exposure_usd"]
        factory = self.fake_factory()
        r = run(self.config,self.tasks,self.root,execute=True,retry=True,limit=1,provider_factory=factory,progress=lambda _:None)
        self.assertGreater(float(r["cost"]["reserved_exposure_usd"]),float(reserved))
        self.assertEqual(len(read_run(self.root)[1]),2)

    def test_interrupted_request_remains_pending_and_can_resume_once(self):
        def interrupt():
            raise KeyboardInterrupt()
        run(self.config,self.tasks,self.root,execute=True,provider_factory=self.fake_factory(interrupt),progress=lambda _:None)
        _,a = read_run(self.root)
        self.assertEqual(a[0]["status"],"pending")
        run(self.config,self.tasks,self.root,execute=True,retry=True,limit=1,provider_factory=self.fake_factory(),progress=lambda _:None)
        self.assertEqual(len(read_run(self.root)[1]),2)

    def test_token_guard_prevents_generation(self):
        factory = self.fake_factory()
        factory.count = lambda *args: 1800
        r = run(self.config,self.tasks,self.root,execute=True,provider_factory=factory,progress=lambda _:None)
        self.assertEqual(self.sent,[])
        self.assertEqual(r["cost"]["reserved_exposure_usd"],"0.000000")
        self.assertIn("Input guard",r["last_stop"]["reason"])

    def test_manifest_change_blocks_resume_before_calls(self):
        factory = self.fake_factory()
        run(self.config,self.tasks,self.root,execute=True,limit=1,provider_factory=factory,progress=lambda _:None)
        changed = copy.deepcopy(self.config)
        changed["timeout_seconds"] += 1
        with self.assertRaisesRegex(ValueError,"manifest changed"):
            run(changed,self.tasks,self.root,execute=True,provider_factory=factory,progress=lambda _:None)
        self.assertEqual(len(self.sent),1)

    def test_usage_breach_blocks_future_requests_across_restarts(self):
        factory = self.fake_factory()
        original = factory.generate
        def exceed(instance,*args):
            r = original(instance,*args)
            r.output_tokens = 50000
            return r
        factory.generate = exceed
        r = run(self.config,self.tasks,self.root,execute=True,provider_factory=factory,progress=lambda _:None)
        self.assertEqual(r["decision"],"incomplete")
        self.assertFalse(r["criteria"]["no_usage_assumption_breach"])
        with self.assertRaisesRegex(ValueError,"stays halted"):
            run(self.config,self.tasks,self.root,execute=True,provider_factory=factory,progress=lambda _:None)
        self.assertEqual(len(self.sent),1)

    def test_atomic_cap_and_failed_reservations(self):
        m = manifest_for(self.config,self.tasks,"live")
        with run_lock(self.root):
            ledger = Ledger(self.root,m)
            self.addCleanup(ledger.close)
            attempt = ledger.reserve("first",dollars("9.98"),100,{})
            ledger.finish(attempt,status="transport_error")
            with self.assertRaises(BudgetExhausted):
                ledger.reserve("second",dollars("0.03"),100,{})
            self.assertEqual(ledger.exposure(),dollars("9.98"))

    def test_concurrent_run_lock(self):
        with run_lock(self.root):
            with self.assertRaisesRegex(ValueError,"Another process"):
                with run_lock(self.root):
                    pass

    def test_bundle_allowlist_excludes_secrets_and_ledger(self):
        run(self.config,self.tasks,self.root,simulation="clean",limit=1,progress=lambda _:None)
        (self.root/".env").write_text("secret-placeholder")
        with patch("sys.stdout",new=io.StringIO()):
            self.assertEqual(main(["bundle","--out",str(self.root)]),0)
        with zipfile.ZipFile(self.root/"results.zip") as z:
            self.assertNotIn(".env",z.namelist())
            self.assertNotIn("ledger.sqlite3",z.namelist())
            self.assertIn("attempts.jsonl",z.namelist())


if __name__=="__main__":
    unittest.main()
