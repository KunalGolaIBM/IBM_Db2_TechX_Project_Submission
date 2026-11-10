"""The unseen-domain evaluation: SPR, a fictional railway's refund policy and 40 cases, written by GPT to make
AsOf release a wrong answer (PROVENANCE.md).

    pdfs.py      the three policy versions as text-layer PDFs, word for word
    onboard.py   SPR loaded through Policy intake and the editor's approval, replayable from the records
    accuracy.py  intake's proposals scored against the policy text, and the editor's rule
    run.py       the 40 cases through the full check, with the metrics fixed before the first run
    baseline.py  the plain-judge baseline (the same model, SPR's latest version, release or block)
    report.py    the generated tables in docs/eval/unseen-results.md
    docblocks.py generated blocks in hand-written documents; the tables in docs/eval/unseen-intake.md
"""
