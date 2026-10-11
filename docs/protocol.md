# Frozen exploratory protocol: reconstruction-screen-v1

Frozen before any paid model calls. This protocol screens whether a more expensive mechanistic study is warranted. Its thresholds are practical continuation criteria, not validated hypothesis tests or power guarantees.

## Question and scope

Does mistaken approval of a flawed solution co-occur with falsely attributing a repair to the supplied solution, and does explicitly separating supplied from inferred steps improve grading beyond a generic checking reminder?

The proposed explanation is that the evaluator reconstructs a better solution and then confuses that reconstruction with the original. The behavioral pattern cannot establish this internal explanation: post-verdict rationalization, prompted source confusion, attention, and response strategy are alternative explanations. A positive screen must be followed by independent confirmation and causal internal-state experiments.

## Stimuli

Twenty-four sets: six templates, four parameterizations per template. Families are arithmetic (invoice and successive discount), algebra (one linear equation and a two-equation system), and code (Python range endpoints and branch state). Family labels summarize renderings; they are not a claim of broad generalization. Templates are the primary diversity units.

Every set has a deterministic numerical oracle and three proposed solutions. The good version contains a correct diagnostic step. The bad version replaces that step with an explicitly false statement or inference while retaining the correct final answer. The wrong-answer version retains the bad step but changes the final answer. All versions contain an unchanged, genuinely present anchor statement. A repair claim is present in the good solution and absent in both flawed solutions; an unrelated foil claim is absent everywhere.

No gold verdict, condition identifier, oracle metadata, or hypothesis label is sent to the provider. Numerical answers that naturally occur in the proposed solution are part of the experimental stimulus. No model-generated code is executed.

These tasks are a controlled extension, not a replication of VAIR. In particular, a missing explanation or reordered list is not automatically called invalid. There is no assumption that the published VAIR failure rate transfers to these short, explicit-error items. A null screen closes this implementation; it is not a reason to search indefinitely for prompts that cause mistakes.

## Cells and ordering

Eight independent first-turn calls per set:

| Cell | Task | Gold |
| --- | --- | --- |
| `solve` | Solve without a proposed solution | Exact integer oracle |
| `good_neutral` | Grade the good solution | valid |
| `bad_neutral` | Grade flawed reasoning with the correct answer | invalid |
| `wrong_neutral` | Grade flawed reasoning with a wrong answer | invalid |
| `bad_generic` | Grade bad reasoning with a generic checking reminder | invalid |
| `bad_source` | Grade bad reasoning with a supplied/inferred distinction | invalid |
| `good_generic` | Grade good reasoning with the generic reminder | valid |
| `good_source` | Grade good reasoning with the supplied/inferred distinction | valid |

Two follow-up calls, `probe_bad` and `probe_good`, continue the corresponding neutral grading transcript. Each includes the actual visible grading response and original stimulus, then asks whether three claims were explicitly present in the proposed solution. Hidden thinking blocks are not replayed. This is a textual conversational continuation, not measurement or preservation of the earlier internal state.

Each probe tests (i) repair, (ii) present anchor, (iii) absent foil. A/B/C assignment varies deterministically and is unchanged across a set's two probes. Quotes are recorded; a nonverbatim quote is an auxiliary diagnostic. A wrong source claim remains a behavioral observation rather than a formatting error. The first four requests exercise solving, grading, and attribution output schemas.

Task order and remaining condition order are seeded before collection. Grading branches do not share conversations. The generic and source reminders have 35 words each and share schemas and effort settings; token counts are recorded, not presumed identical. All verdicts precede the attribution probe, so it cannot alter their recorded values.

## Frozen continuation rule

All 240 cells must have valid complete responses, with no provider usage/model assumption breach. Incomplete, malformed, refused, truncated, failed, or interrupted responses do not count as incorrect reasoning. Missing cells cannot produce a scientific stop/continue conclusion.

The following controls must each be correct on at least **22 of 24** tasks:

- Independent solving.
- Each of the three good-solution grading conditions.
- Wrong-answer error detection.
- Each of the three source claims after the good solution.
- Present-anchor and absent-foil checks after the bad solution.

A task is **qualified** when independent solving, good-neutral grading, and wrong-answer detection are all correct. At least **20 of 24** must qualify.

Continue only when all of these additionally hold:

1. At least **5 of 24** bad-neutral solutions receive mistaken approval.
2. At least **3 qualified tasks**, across at least **2 families**, have the joint pattern: mistaken approval; a false claim that the repair was present, with a nonempty purported quotation; correct anchor/foil attribution; and correct attribution of all three claims in the paired good solution.
3. Across all bad probes, repair false-attribution count exceeds unrelated-foil false-attribution count by at least **3**.
4. Source separation yields at least **3 net additional correct rejections** relative to the generic reminder, with positive net gains in at least **2 families**. Benefits minus regressions are used, not benefits alone.
5. At least **2 joint-pattern tasks** are correctly rejected under source separation but accepted under the generic reminder. This links the intervention and attribution signals on the same cases.
6. Source separation causes at most **1 net additional rejection of valid work** relative to the generic reminder, while also meeting the 22/24 good-source control above.

Failure of controls gives `stop_controls_failed`. Otherwise gates are applied in order: baseline failure, specific attribution, then intervention specificity. A pass is `continue_to_independent_mechanistic_check`. This is not a finding of internal reconstruction.

The report contains raw paired benefit/harm counts and a descriptive exact sign/McNemar p-value. That p-value is not used for continuation, is not corrected for multiple exploratory contrasts, and treats numerical instances as independent despite shared templates. It must not be presented as confirmatory significance. Raw per-task results and template/family labels are retained.

## Collection and budget

One model: `claude-sonnet-5-5`, adaptive thinking at high effort, provider-default sampling. Native structured outputs apply to final visible text. Solving/grading can use 4,096 total output tokens; source probes can use 2,048. The latter is a shorter attribution task, not an attempt to suppress reasoning. Truncation at either limit makes that cell incomplete. No truncation is evidence for the hypothesis.

With 1,800 reserved input tokens, $2/M input and $10/M output, the maximum reserved first pass is:

- 192 solving/grading calls at $0.044560 each = $8.555520.
- 48 attribution calls at $0.024080 each = $1.155840.
- Total $9.711360; $0.288640 remains under the $10 cap for explicit retries.

Token counting precedes generation, includes the schema, and must leave 256 input tokens of headroom. The runner does not automatically retry generation. At most one explicit retry is permitted for unsuccessful cells; valid responses are never retried. Failed and interrupted requests retain their entire reservation because the true charge may be unknown. The analysis selects the first valid response per cell and also reports first-attempt coverage and every attempt's status. Quote/rationale content is never used to choose which valid response to retain.

The ledger is authoritative and is saved before each paid request. Concurrent processes are excluded with a file lock. Hashes bind the dataset, code, configuration, job order, and mode. Probe requests record the exact parent attempt ID and visible text used. Unexpected usage or model identity halts future collection across restarts. Pricing review expires October 25, 2026. This guard is per run directory and excludes taxes and other account activity.

## What a positive screen would justify

Confirm the conjunction on new templates and an independently selected model, then test whether a representation of the repaired step replaces the supplied step before the verdict. A causal intervention would need to target that distinction while holding answer correctness fixed, include matched control interventions, and preserve task competence. API explanations, post-verdict claims, prompt interventions, and successful classification probes alone are insufficient.

Do not describe the pilot as novel mechanistic evidence, a top-conference-ready result, or a reproduction of the published aggregate percentages. No paid human annotations are required by this screen. Quotes and rationales remain available for qualitative review, but changing the quantitative rule after inspecting them would be a new exploratory analysis.
