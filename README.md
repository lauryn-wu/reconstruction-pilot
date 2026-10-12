# Reconstruction pilot

This pilot tests a possible grading error: accepting a flawed solution, then
attributing an unwritten repair to it. Sonnet rejected all 24 flawed solutions
under neutral grading and never falsely attributed a missing repair in the
corresponding source questions. The run finished with 240/240 valid responses
and stopped at the planned `stop_no_clear_failure` decision.

The experiment used `claude-sonnet-5-5` with adaptive thinking at high effort.
The 24 matched problems come from six templates in arithmetic, algebra, and
short Python traces. Results and raw responses are in
[the completed run](results/2026-10-11-reconstruction/).

## Experiment

Each problem has a correct solution and a version containing an explicitly false intermediate step but the correct final answer. The model independently solves the problem, grades the supplied solutions, and answers questions about which claims were present in the text.

The proposed failure requires both mistaken approval and false attribution on
the same problem. Two grading prompts add either a generic checking reminder or
an instruction to separate written steps from inferred repairs. Correct-solution
controls check whether those prompts simply increase rejection.

The source questions come after the verdict and replay the visible response,
so they cannot establish what happened internally during grading. The
[protocol](docs/protocol.md) gives the full design and stopping rules.

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

Both checking prompts also led to rejection of every flawed solution. With no
mistaken approvals in the baseline, the run cannot tell whether either prompt
would help when that failure occurs. The generic reminder led to one rejection
of a correct solution.

There were no invalid responses or transport failures. Recorded usage cost was
$0.616630, below the budget guard's conservative reservation of $9.711360 against
the $10 cap.

See the [run report](results/2026-10-11-reconstruction/report.md), [full analysis](results/2026-10-11-reconstruction/analysis.json), and [raw requests and responses](results/2026-10-11-reconstruction/attempts.jsonl).

The errors were short and explicit, and the grading instructions defined false
intermediate steps as invalid. Longer or subtler errors remain untested; the 24
problems cover only six templates. This design did not meet the criteria for a
follow-up, so no further runs are planned. See [related work](docs/related_work.md)
for the motivation behind the hypothesis.

## Inspect and reproduce the results

Python 3.11+ is required; there are no third-party runtime dependencies. The committed export includes the manifest, exact tasks, raw responses, and analysis. The [offline reproduction instructions](docs/REPRODUCING_RESULTS.md) recompute the analysis from those files without API calls or credentials.

For software checks and a preview of the frozen plan:

```bash
python3 -m unittest discover -s tests -v
python3 -m reconstruction_pilot plan
```

The [run instructions](docs/RUNNING.md) cover live execution, simulations,
resumption, and the spending guard. Only `run --execute` sends model API requests;
the simulations check the software.
