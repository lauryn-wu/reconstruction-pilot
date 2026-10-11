# Evidence and contribution boundary

Checked October 11, 2026. This is a focused starting point, not an exhaustive novelty claim.

## Closest work

Mingzhong Sun, Teresa Yeo, Armando Solar-Lezama, and Tan Zhi-Xuan. **An Enigma of Artificial Reason: Investigating the Production-Evaluation Gap in Large Reasoning Models** (May 31, 2026). [Paper](https://arxiv.org/abs/2606.01462), [full text](https://arxiv.org/html/2606.01462v1).

The paper compares mathematical solution production with evaluation of solutions whose correct answers coexist with perturbed reasoning. It reports substantial evaluation failures, analyzes answer-confirmation bias, and patches answer-associated activations to change verdicts. It already connects independent solution generation with mistaken endorsement. Its strongest failures concern missing or shuffled reasoning, whose grading differs from our explicit false-statement criterion.

**Already covered:** finding that solving exceeds evaluation, showing that correct final answers bias evaluation, describing rationalization, or showing verdict changes after answer-token patching. Those alone would not distinguish this project.

**Proposed extension:** determine whether evaluators substitute a repaired intermediate argument for the supplied argument, lose the distinction between their own inference and source text, and therefore approve the original. The current pilot measures a possible behavioral signature and prompt-based specificity controls. It does not establish the proposed internal sequence or that it precedes the verdict.

## Related boundaries

- Lanham et al., **Measuring Faithfulness in Chain-of-Thought Reasoning** (2023), [paper](https://arxiv.org/abs/2307.13702): written reasoning is not automatically a faithful record of computation. A rationale that supplies a missing repair is not itself causal evidence.
- **The Future of Facts: Tracing the Factual Generation-Verification Gap** (2026), [paper](https://arxiv.org/abs/2605.27564): generation/verification asymmetries are studied outside mathematical process validity too. A generic gap is not the contribution here.

The strongest alternative explanations are post-hoc rationalization prompted by the attribution query, ordinary source-recall errors, generic increased attention, and a stricter rejection criterion. The foil, anchor, good-solution, and matched-reminder controls address some of these. They cannot eliminate all of them. Any serious paper claim would need independent generalization and a discriminating causal test.

## Provider implementation references

- [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- [Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Token counting](https://platform.claude.com/docs/en/build-with-claude/token-counting)

Prices and request formats were checked against primary documentation. Live access and actual response validity have not been tested by the implementation author; the four-call smoke run is part of the budgeted study.
