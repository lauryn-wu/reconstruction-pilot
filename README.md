# Reconstruction pilot

Does a model approve flawed reasoning and then attribute a repair to the original solution?

This is a **small exploratory screen**, with **no empirical model results yet**. It tests a behavioral prerequisite for a possible mechanistic study. A positive result would not establish an internal reconstruction mechanism or a novel paper contribution.

The frozen screen uses **24 matched problems, 10 requests per problem, one model, and a $10 reservation cap**. We reduced the approximate 30-problem plan to 24 to include valid-solution controls for both interventions within the cap. Problems cover six templates in arithmetic, algebra, and short Python traces. The four numerical variants of a template are not independent problem families.

## Run on your Mac

Python 3.11 or newer is required. No GPU, Gemini account, or third-party runtime package is needed.

```bash
git clone https://github.com/lauryn-wu/reconstruction-pilot.git
cd reconstruction-pilot
python3 -m venv .venv
source .venv/bin/activate
python3 -m unittest discover -s tests -v
python3 -m reconstruction_pilot plan
```

The tests and `plan` are entirely offline. The plan should report **240 generation requests**, **$9.711360 first-pass reserved exposure**, and **$10.00 budget**. This is a conservative upper reservation, not an expected invoice.

Use your existing Anthropic API key. If it is not already exported, the following **Mac zsh** commands accept it without displaying it or placing the secret in shell history:

```zsh
read -rs "ANTHROPIC_API_KEY?Paste your Anthropic API key: "
export ANTHROPIC_API_KEY
```

Press Return after pasting. Nothing appears while you paste. Keys are read from the environment; `.env` files are not loaded. Do not put your key in the code or upload it with results.

Run four requests to check access and all three output schemas:

```bash
caffeinate -i python3 -m reconstruction_pilot run --execute --limit 4
```

An `incomplete` result is expected after four calls. Those calls are part of the full screen, not extra trials. Continue the **same** run:

```bash
caffeinate -i python3 -m reconstruction_pilot run --execute
```

On Linux, omit `caffeinate -i`. The model uses adaptive thinking at high effort and provider-default sampling. We do not disable thinking or lower the budget to obtain failures. The 4,096-token solving/grading allowance and 2,048-token attribution allowance include thinking; any truncation is incomplete data.

## Inspect or share results

```bash
python3 -m reconstruction_pilot analyze
python3 -m reconstruction_pilot bundle
```

Upload **`runs/screen/results.zip`** for review. It contains the manifest, tasks, report, analysis, raw requests/responses, and error details. It does not include environment variables or the database. Keep **`runs/screen/ledger.sqlite3`** locally: that database is needed to resume and preserve the spending guard.

Possible decisions:

| Decision | Meaning |
| --- | --- |
| `incomplete` | Some cells are missing/invalid, or a usage assumption needs review. No scientific conclusion. |
| `stop_controls_failed` | Solving, valid-solution grading, ordinary error detection, or attribution controls failed. |
| `stop_no_clear_failure` | Too few mistaken approvals to investigate this mechanism here. |
| `stop_no_reconstruction_specific_signal` | Approval errors did not come with sufficiently specific false source attribution. |
| `stop_no_specific_intervention_gain` | Separating written from inferred steps did not pass the matched intervention checks. |
| `continue_to_independent_mechanistic_check` | The prespecified behavioral screen passed. Independent replication and causal tests are still required. |

## If something stops

```bash
python3 -m reconstruction_pilot errors
```

The output includes the provider's error message, not just an HTTP code. Raw diagnostics are also in `failures.jsonl` and `attempts.jsonl`.

- **401/403:** check the API key and model access. **Billing/credit error:** resolve it in the Anthropic console.
- **429 or 5xx:** wait until the service/limit recovers. There are no automatic paid retries.
- **`invalid_format` or `truncated`:** inspect the response before retrying. Do not treat it as a wrong model judgment. Repeated truncation means this allocation is inadequate.
- **Input guard, model mismatch, or unexpected usage:** stop for review. Do not raise limits or change models midway through the frozen run.

After resolving a transient failure, permit one additional attempt for unsuccessful cells:

```bash
caffeinate -i python3 -m reconstruction_pilot run --execute --retry-failed
```

A completed valid response is never resampled, including a wrong answer. Retries retain the same prompts/settings. Pending/interrupted and failed generations keep their full spending reservation. A normal resume skips unsuccessful attempts unless `--retry-failed` is supplied. There is only **$0.288640** of first-pass retry headroom, so repeated provider errors can leave the study incomplete within the cap.

## What is measured

Each problem has:

1. Independent solving.
2. A correct solution graded with neutral, generic-check, and source-separation instructions.
3. An explicitly flawed solution with the correct final answer, under the same three instructions.
4. The flawed solution with a wrong final answer, as an ordinary error-detection control.
5. Two source-attribution follow-ups, after the neutral correct-solution and flawed-solution grades.

The follow-up asks about a repair claim, a genuinely present claim, and an unrelated absent claim. Their A/B/C labels vary across tasks. These questions are asked **after** the verdict; they cannot change the recorded initial grade. The follow-up replays the original prompt and the model's actual **visible response**. It does not carry forward hidden activations or replay private thinking blocks.

The novel hypothesis concerns reconstruction, so reproducing generic answer-confirmation bias is insufficient to pass. We require mistaken approval and repair-specific false attribution on the same qualified problems, intervention benefit over an equal-word-count generic reminder, and preserved acceptance of valid solutions. Details and numeric thresholds are frozen in [docs/protocol.md](docs/protocol.md).

These are deliberately clear, automatically checkable errors, rather than shuffled exposition labeled invalid by convention. Strong models may catch all of them. The published failure rates from a different task distribution are **not predictions for this screen**. We will not adapt the tasks after seeing results to force an effect.

## Budget and reproducibility

The initial model is `claude-sonnet-5-5`. [Anthropic's official pricing](https://platform.claude.com/docs/en/about-claude/pricing), checked October 11, 2026, lists $2 per million input tokens and $10 per million output tokens. We use the standard global endpoint without tools, explicit caching, batch processing, or fast mode.

Before each generation, the free native token counter measures the full request, including the structured output schema. The measured input plus 256 tokens of headroom must fit the 1,800-token allowance. A durable reservation for the **entire** input/output allowance is recorded before sending the generation. Reservations are never refunded inside the pilot, even when actual usage is lower. Unknown costs are never assumed to be zero. Unexpected usage or model identity halts future calls, including across restarts.

This is a local software guard at the recorded rates, not an account-wide provider spending limit. It excludes taxes, unrelated applications, and other run directories. **Do not delete the ledger, rerun in another directory, or clone again to reset the cap.** The pricing snapshot expires October 25, 2026. Config, dataset, code hash, and live/simulation mode are fixed for each run; changing them blocks resume.

The repository is dependency-free at runtime. `pip install -e .` is optional if you want the `reconstruction-pilot` executable; the `python3 -m reconstruction_pilot` commands above work directly from the checkout.

## Offline simulations

```bash
python3 -m reconstruction_pilot simulate --profile clean
python3 -m reconstruction_pilot simulate --profile answer_bias
python3 -m reconstruction_pilot simulate --profile reconstruction
```

These are artificial fixtures for checking the software, stored in separate directories. Their decision is always `simulation_only`; the separately reported `simulated_decision` checks the gate logic. They are not observations from any model and cannot be resumed as live data.

## Files

| Path | Purpose |
| --- | --- |
| `reconstruction_pilot/data/tasks.jsonl` | Frozen problems, solution variants, claim labels, and exact gold values |
| `reconstruction_pilot/data/screen.json` | Frozen model settings, prices, allowances, and thresholds |
| `reconstruction_pilot/study.py` | Deterministic generator, independent numerical oracles, and prompt templates |
| `reconstruction_pilot/provider.py` | Native API adapter and strict response validation |
| `reconstruction_pilot/ledger.py` | Durable spending reservations and process lock |
| `reconstruction_pilot/runner.py` | Resumption, dependencies, and execution guards |
| `reconstruction_pilot/analysis.py` | Paired diagnostics and continuation rule |
| `docs/protocol.md` | Prespecified interpretation and limitations |
| `docs/related_work.md` | Established findings versus the untested hypothesis |

No paid run is launched by installation, import, tests, planning, simulation, analysis, or bundling. Only **`run --execute`** sends model API requests.
