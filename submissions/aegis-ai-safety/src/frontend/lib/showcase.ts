import type { Verification } from "./types";

/**
 * Recorded verification session #741 (BERT smoke test, 2026-11-07).
 * Real Db2 evidence and page references. Used only for the clearly labelled
 * public interactive demonstration when the local API is unavailable.
 */
export const SHOWCASE_VERIFICATION: Verification = {
  "session_id": 741,
  "submitted_text": "BERT is pre-trained with masked language modeling. BERT uses a convolutional neural network architecture. BERT eliminates hallucinations in all scientific applications.",
  "model_provider": "ollama/qwen2.5:7b-instruct",
  "status": "COMPLETED",
  "error_message": null,
  "created_at": "2026-11-07T02:02:37.399217",
  "completed_at": "2026-11-07T02:07:13.412611",
  "duration_ms": 248127,
  "counts": {
    "total": 3,
    "supported": 1,
    "contradicted": 1,
    "insufficient_evidence": 1,
    "verification_error": 0
  },
  "claims": [
    {
      "claim_id": 621,
      "original_claim": "BERT is pre-trained with masked language modeling.",
      "normalized_claim": "BERT is pre-trained using masked language modeling.",
      "claim_type": "FACTUAL",
      "position_start": 0,
      "position_end": 50,
      "classification": "SUPPORTED",
      "explanation": "Passage ID 185 explicitly states that BERT uses masked language models for pre-training, which supports the claim.",
      "limitations": "Other passages discuss BERT's performance and training steps but do not directly address the pre-training method.",
      "numerical_analysis": null,
      "human_review_status": "PENDING",
      "verification_method": "langchain_llm+db2_lexical_retrieval",
      "result_created_at": "2026-11-07T02:07:11.848308",
      "evidence": [
        {
          "passage_id": 185,
          "passage_text": "word based only on its context. Unlike left-to-\nright language model pre-training, the MLM ob-\njective enables the representation to fuse the left\nand the right context, which allows us to pre-\ntrain a deep bidirectional Transformer. In addi-\ntion to the masked language model, we also use\na “next sentence prediction” task that jointly pre-\ntrains text-pair representations. The contributions\nof our paper are as follows:\n• We demonstrate the importance of bidirectional\npre-training for language representations. Un-\nlike Radford et al. (2018), which uses unidirec-\ntional language models for pre-training, BERT\nuses masked language models to enable pre-\ntrained deep bidirectional representations. This\nis also in contrast to Peters et al. (2018a), which\nuses a shallow concatenation of independently\ntrained left-to-right and right-to-left LMs. • We show that pre-trained representations reduce\nthe need for many heavily-engineered task-\nspeciﬁc architectures. BERT is the ﬁrst ﬁne-\ntuning based representation model that achieves\nstate-of-the-art performance on a large suite\nof sentence-level and token-level tasks, outper-\nforming many task-speciﬁc architectures.",
          "page_number": 2,
          "passage_index": 4,
          "document_id": 141,
          "document_title": "BERT: Pre-training of Deep Bidirectional Transformers (Devlin et al., 2019)",
          "filename": "bert-pre-training.pdf",
          "evidence_relationship": "SUPPORTS",
          "relevance_score": 4.104346
        }
      ]
    },
    {
      "claim_id": 622,
      "original_claim": "BERT uses a convolutional neural network architecture.",
      "normalized_claim": "BERT uses a convolutional neural network architecture.",
      "claim_type": "FACTUAL",
      "position_start": 51,
      "position_end": 105,
      "classification": "CONTRADICTED",
      "explanation": "Passage ID 236 states that BERT uses a bidirectional Transformer, not a convolutional neural network.",
      "limitations": "The claim is based on a specific architectural detail not directly addressed in the provided passages.",
      "numerical_analysis": null,
      "human_review_status": "PENDING",
      "verification_method": "langchain_llm+db2_lexical_retrieval",
      "result_created_at": "2026-11-07T02:07:13.030822",
      "evidence": [
        {
          "passage_id": 236,
          "passage_text": "BERT (Ours)\nTrm\nTrm\nTrm\nTrm\nTrm\nTrm\n... ... Trm\nTrm\nTrm\nTrm\nTrm\nTrm\n... ... OpenAI GPT\nLstm\nELMo\nLstm\nLstm\nLstm\nLstm\nLstm\nLstm\nLstm\nLstm\nLstm\nLstm\nLstm\nT1\nT2\nTN\n... ... ... ... ... E1\nE2\nEN\n... T1\nT2\nTN\n... E1\nE2\nEN\n... T1\nT2\nTN\n... E1\nE2\nEN\n... Figure 3: Differences in pre-training model architectures. BERT uses a bidirectional Transformer. OpenAI GPT\nuses a left-to-right Transformer. ELMo uses the concatenation of independently trained left-to-right and right-to-\nleft LSTMs to generate features for downstream tasks. Among the three, only BERT representations are jointly\nconditioned on both left and right context in all layers. In addition to the architecture differences, BERT and\nOpenAI GPT are ﬁne-tuning approaches, while ELMo is a feature-based approach. to converge. In Section C.1 we demonstrate that\nMLM does converge marginally slower than a left-\nto-right model (which predicts every token), but\nthe empirical improvements of the MLM model\nfar outweigh the increased training cost. Next Sentence Prediction\nThe next sentence\nprediction task can be illustrated in the following\nexamples.",
          "page_number": 13,
          "passage_index": 55,
          "document_id": 141,
          "document_title": "BERT: Pre-training of Deep Bidirectional Transformers (Devlin et al., 2019)",
          "filename": "bert-pre-training.pdf",
          "evidence_relationship": "CONTRADICTS",
          "relevance_score": 3.942634
        }
      ]
    },
    {
      "claim_id": 623,
      "original_claim": "BERT eliminates hallucinations in all scientific applications.",
      "normalized_claim": "BERT eliminates hallucinations in all scientific applications.",
      "claim_type": "FACTUAL",
      "position_start": 106,
      "position_end": 168,
      "classification": "INSUFFICIENT_EVIDENCE",
      "explanation": "None of the passages explicitly address BERT's performance in eliminating hallucinations in scientific applications.",
      "limitations": "The passages focus on BERT's architecture and pre-training tasks but do not discuss its performance in scientific applications.",
      "numerical_analysis": null,
      "human_review_status": "PENDING",
      "verification_method": "langchain_llm+db2_lexical_retrieval",
      "result_created_at": "2026-11-07T02:07:13.084587",
      "evidence": [
        {
          "passage_id": 200,
          "passage_text": "English Wikipedia (2,500M words). For Wikipedia we extract only the text passages\nand ignore lists, tables, and headers. It is criti-\ncal to use a document-level corpus rather than a\nshufﬂed sentence-level corpus such as the Billion\nWord Benchmark (Chelba et al., 2013) in order to\nextract long contiguous sequences. 3.2\nFine-tuning BERT\nFine-tuning is straightforward since the self-\nattention mechanism in the Transformer al-\nlows BERT to model many downstream tasks—\nwhether they involve single text or text pairs—by\nswapping out the appropriate inputs and outputs. For applications involving text pairs, a common\npattern is to independently encode text pairs be-\nfore applying bidirectional cross attention, such\nas Parikh et al. (2016); Seo et al. (2017). BERT\ninstead uses the self-attention mechanism to unify\nthese two stages, as encoding a concatenated text\npair with self-attention effectively includes bidi-\nrectional cross attention between two sentences. For each task, we simply plug in the task-\nspeciﬁc inputs and outputs into BERT and ﬁne-\ntune all the parameters end-to-end.",
          "page_number": 5,
          "passage_index": 19,
          "document_id": 141,
          "document_title": "BERT: Pre-training of Deep Bidirectional Transformers (Devlin et al., 2019)",
          "filename": "bert-pre-training.pdf",
          "evidence_relationship": "CONTEXT",
          "relevance_score": 4.941912
        },
        {
          "passage_id": 236,
          "passage_text": "BERT (Ours)\nTrm\nTrm\nTrm\nTrm\nTrm\nTrm\n... ... Trm\nTrm\nTrm\nTrm\nTrm\nTrm\n... ... OpenAI GPT\nLstm\nELMo\nLstm\nLstm\nLstm\nLstm\nLstm\nLstm\nLstm\nLstm\nLstm\nLstm\nLstm\nT1\nT2\nTN\n... ... ... ... ... E1\nE2\nEN\n... T1\nT2\nTN\n... E1\nE2\nEN\n... T1\nT2\nTN\n... E1\nE2\nEN\n... Figure 3: Differences in pre-training model architectures. BERT uses a bidirectional Transformer. OpenAI GPT\nuses a left-to-right Transformer. ELMo uses the concatenation of independently trained left-to-right and right-to-\nleft LSTMs to generate features for downstream tasks. Among the three, only BERT representations are jointly\nconditioned on both left and right context in all layers. In addition to the architecture differences, BERT and\nOpenAI GPT are ﬁne-tuning approaches, while ELMo is a feature-based approach. to converge. In Section C.1 we demonstrate that\nMLM does converge marginally slower than a left-\nto-right model (which predicts every token), but\nthe empirical improvements of the MLM model\nfar outweigh the increased training cost. Next Sentence Prediction\nThe next sentence\nprediction task can be illustrated in the following\nexamples.",
          "page_number": 13,
          "passage_index": 55,
          "document_id": 141,
          "document_title": "BERT: Pre-training of Deep Bidirectional Transformers (Devlin et al., 2019)",
          "filename": "bert-pre-training.pdf",
          "evidence_relationship": "CONTEXT",
          "relevance_score": 1.509514
        },
        {
          "passage_id": 234,
          "passage_text": "ails for BERT\nA.1\nIllustration of the Pre-training Tasks\nWe provide examples of the pre-training tasks in\nthe following. Masked LM and the Masking Procedure\nAs-\nsuming the unlabeled sentence is\nmy dog is\nhairy, and during the random masking procedure\nwe chose the 4-th token (which corresponding to\nhairy), our masking procedure can be further il-\nlustrated by\n• 80% of the time: Replace the word with the\n[MASK] token, e.g., my dog is hairy →\nmy dog is [MASK]\n• 10% of the time: Replace the word with a\nrandom word, e.g., my dog is hairy →my\ndog is apple\n• 10% of the time:\nKeep the word un-\nchanged, e.g., my dog is hairy →my dog\nis hairy. The purpose of this is to bias the\nrepresentation towards the actual observed\nword. The advantage of this procedure is that the\nTransformer encoder does not know which words\nit will be asked to predict or which have been re-\nplaced by random words, so it is forced to keep\na distributional contextual representation of ev-\nery input token. Additionally, because random\nreplacement only occurs for 1.5% of all tokens\n(i.e., 10% of 15%), this does not seem to harm\nthe model’s language understanding capability.",
          "page_number": 12,
          "passage_index": 53,
          "document_id": 141,
          "document_title": "BERT: Pre-training of Deep Bidirectional Transformers (Devlin et al., 2019)",
          "filename": "bert-pre-training.pdf",
          "evidence_relationship": "CONTEXT",
          "relevance_score": 1.491844
        }
      ]
    }
  ]
} as Verification;

export const SHOWCASE_CLAIMS = [
  "BERT is pre-trained with masked language modeling.",
  "BERT uses a convolutional neural network architecture.",
  "BERT eliminates hallucinations in all scientific applications.",
].join(" ");

export const SHOWCASE_TITLE = "BERT: Pre-training of Deep Bidirectional Transformers";
