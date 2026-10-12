# Reconstruction pilot

Does a language model approve flawed reasoning and then attribute a missing repair to the original solution?

**Status: completed null screen; no further experiments planned for this design.** All **240 evaluations** returned valid responses. The model mistakenly approved **0/24** flawed solutions in the neutral baseline and falsely attributed a missing repair in **0/24** corresponding source probes. The behavioral prerequisite for the proposed follow-up did not appear.

The experiment used `claude-sonnet-5-5` with adaptive thinking at high effort. The frozen dataset contains 24 matched problems from six templates in arithmetic, algebra, and short Python traces. Results and raw responses are in [the completed run](results/2026-10-11-reconstruction/).

## What the experiment tests

Each problem has a correct solution and a version containing an explicitly false intermediate step but the correct final answer. The model independently solves the problem, grades the supplied solutions, and answers questions about which claims were present in the text.

The key proposed failure requires both mistaken approval and false attribution of a missing repair on the same problem. Two grading interventions compare a generic checking reminder with an instruction to separate written steps from inferred repairs. Valid-solution controls check whether an intervention simply increases rejection.

Source questions come after the verdict and replay the visible response. They cannot establish what happened internally while the model made its initial judgment. The complete design and thresholds are in the [frozen protocol](docs/protocol.md).

## Results

| Measure | Result |
| --- | ---: |
| Completed, valid evaluations | 240/240 |
| Independent solutions correct | 24/24 |
| Valid solutions accepted under neutral grading | 24/24 |
| Flawed solutions mistakenly accepted under neutral grading | 0/24 |
| Ordinary wrong-answer controls rejected | 24/24 |
| Missing repairs falsely attributed to flawed source solutions | 0/24 |
| Problems showing both approval and false attribution | 0/24 |
| Valid solutions accepted with generic checking / source separation | 23/24 / 24/24 |

All flawed solutions were also rejected under both intervention prompts. With no baseline mistaken approvals to correct, this run cannot establish whether either intervention would help on a task where the failure occurs. The one generic-check error was rejection of a valid solution.

The frozen decision was **`stop_no_clear_failure`**. Collection had no invalid responses or transport failures. Recorded usage cost was **$0.616630**; the conservative reservation was **$9.711360** against the $10 cap. The reservation is not the observed bill.

See the [run report](results/2026-10-11-reconstruction/report.md), [full analysis](results/2026-10-11-reconstruction/analysis.json), and [raw requests and responses](results/2026-10-11-reconstruction/attempts.jsonl).

## What this result means

The tested model caught these short, explicit errors under prompts that defined false intermediate steps as invalid. This does not rule out reconstruction-like behavior on longer, subtler, or differently framed tasks. The 24 problems share six templates and do not represent 24 independent problem families.

The screen did not meet its prespecified continuation criteria, so this design is parked. Task difficulty and wording were not changed after collection to obtain the predicted effect. No mechanistic conclusion follows from the null result. See [related work](docs/related_work.md) for the distinction between established findings and the hypothesis tested here.

## Inspect and reproduce the results

Python 3.11+ is required; there are no third-party runtime dependencies. The committed export includes the manifest, exact tasks, raw responses, and analysis. The [offline reproduction instructions](docs/REPRODUCING_RESULTS.md) recompute the analysis from those files without API calls or credentials.

For software checks and a preview of the frozen plan:

```bash
python3 -m unittest discover -s tests -v
python3 -m reconstruction_pilot plan
```

The original [run instructions](docs/RUNNING.md) cover optional live execution, simulations, resumption, and the spending guard. Only `run --execute` sends model API requests. Synthetic simulations are labeled as software fixtures and are separate from the empirical results above.
