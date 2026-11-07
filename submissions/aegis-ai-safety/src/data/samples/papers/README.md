# Demo paper evidence

The paper demo uses two public arXiv papers as evidence:

1. **Attention Is All You Need** — Vaswani et al., 2017.
   - arXiv: https://arxiv.org/abs/1706.03762
   - PDF: https://arxiv.org/pdf/1706.03762v7
2. **BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding**
   — Devlin et al., 2019.
   - arXiv: https://arxiv.org/abs/1810.04805
   - PDF: https://arxiv.org/pdf/1810.04805v2

The PDFs are **not redistributed in this repository**. Run:

```bash
make demo-papers
```

or:

```bash
bash scripts/fetch_demo_papers.sh
```

The script downloads the public arXiv PDFs into this directory and ingests them into
Db2. The AEGIS pipeline then uses the real PDF text and page numbers.

Please review the arXiv license/terms for each paper before redistributing the PDFs.
