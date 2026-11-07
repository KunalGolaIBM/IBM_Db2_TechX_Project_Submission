# Problem Statement

Large language models produce fluent research prose that can contain:

- unsupported empirical claims;
- incorrect or fabricated citations;
- numerical inconsistencies (percentages, sample sizes, costs, effect sizes);
- conclusions that exceed the evidence;
- confident statements in domains where no evidence was supplied.

Researchers need a practical way to inspect claims against source evidence before
relying on AI-generated text. General-purpose chat interfaces do not preserve a
claim-level evidence trail and rarely expose why a statement was accepted.

## Scope

AEGIS accepts AI-generated research text plus user-supplied evidence documents, then:

1. extracts atomic factual claims;
2. retrieves relevant passages from the supplied evidence;
3. classifies each claim as supported, contradicted, insufficient evidence, or a
   verification error;
4. links every definitive judgment to a retrieved passage;
5. persists the session for later inspection and reproducibility.

## Out of scope

- general chat or writing assistance;
- plagiarism detection;
- peer review automation;
- verifying citations external to the supplied corpus;
- claiming scientific truth or replacing domain experts.

## Core constraint

A relevant passage is not automatically supporting evidence. Missing evidence is not
contradiction. The system must expose uncertainty rather than manufacture confidence.
