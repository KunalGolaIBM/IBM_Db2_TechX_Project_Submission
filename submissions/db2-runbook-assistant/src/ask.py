"""Ask the runbook assistant a question, scoped to one environment.

Examples:
    python ask.py "Deployment fails on S3 sync with AccessDenied" --env prod
    python ask.py "Deployment fails on S3 sync with AccessDenied" --env dev
    python ask.py "Pod is crash looping" --env uat --service payments-api --show-docs
"""
import argparse

from haystack import Pipeline
from haystack.components.builders import PromptBuilder
from haystack.document_stores.types import FilterPolicy
from haystack_integrations.components.embedders.ollama import OllamaTextEmbedder
from haystack_integrations.components.generators.ollama import OllamaGenerator
from haystack_integrations.components.retrievers.ibm_db import IBMDb2EmbeddingRetriever

from config import EMBED_MODEL, LLM_MODEL, OLLAMA_URL, QUERY_PREFIX, get_document_store

NO_MATCH = "No matching runbook for this environment. Escalate to the platform on-call."

TEMPLATE = """You are a DevOps incident assistant.
Answer ONLY from the runbooks below. Give numbered steps.
End your answer with: "Source: <runbook_id> - <title>".
If nothing below matches the question, reply exactly: "{{ no_match }}"

Runbooks:
{% for doc in documents %}
[{{ doc.meta.runbook_id }}] {{ doc.meta.title }}
(service: {{ doc.meta.service }}, environment: {{ doc.meta.environment }}, severity: {{ doc.meta.severity }})
{{ doc.content }}
---
{% endfor %}

Question: {{ question }}
Answer:"""


def build_pipeline() -> Pipeline:
    store = get_document_store()
    pipe = Pipeline()
    # Prefix only on the query side: Granite is asymmetric (documents are embedded without one).
    pipe.add_component("embedder", OllamaTextEmbedder(model=EMBED_MODEL, url=OLLAMA_URL, prefix=QUERY_PREFIX))
    pipe.add_component(
        "retriever",
        IBMDb2EmbeddingRetriever(
            document_store=store,
            # Init-time filter: deprecated runbooks must never be surfaced.
            filters={"field": "meta.status", "operator": "==", "value": "active"},
            # MERGE combines this with the run-time env/service filter (AND) instead of replacing it.
            filter_policy=FilterPolicy.MERGE,
            top_k=3,
        ),
    )
    pipe.add_component("prompt", PromptBuilder(template=TEMPLATE))
    pipe.add_component("llm", OllamaGenerator(model=LLM_MODEL, url=OLLAMA_URL))
    pipe.connect("embedder.embedding", "retriever.query_embedding")
    pipe.connect("retriever.documents", "prompt.documents")
    pipe.connect("prompt", "llm")
    return pipe


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("question")
    parser.add_argument("--env", required=True, choices=["dev", "uat", "prod"])
    parser.add_argument("--service", help="optionally narrow to one service")
    parser.add_argument("--show-docs", action="store_true", help="print retrieved chunks")
    args = parser.parse_args()

    conditions = [{"field": "meta.environment", "operator": "==", "value": args.env}]
    if args.service:
        conditions.append({"field": "meta.service", "operator": "==", "value": args.service})

    pipe = build_pipeline()
    result = pipe.run(
        {
            "embedder": {"text": args.question},
            "retriever": {"filters": {"operator": "AND", "conditions": conditions}},
            "prompt": {"question": args.question, "no_match": NO_MATCH},
        },
        include_outputs_from={"retriever"},
    )

    docs = result["retriever"]["documents"]
    print(result["llm"]["replies"][0].strip())
    print(f"\nChunks retrieved: {len(docs)}")
    if args.show_docs:
        for d in docs:
            snippet = d.content[:160].replace("\n", " ")
            print(f"  score={d.score:.4f} {d.meta['runbook_id']} | {d.meta['title']} | {snippet}")


if __name__ == "__main__":
    main()
