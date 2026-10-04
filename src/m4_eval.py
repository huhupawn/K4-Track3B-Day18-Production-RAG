from __future__ import annotations

"""Module 4: RAGAS Evaluation — 4 metrics + failure analysis."""

import os, sys, json
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import TEST_SET_PATH


@dataclass
class EvalResult:
    question: str
    answer: str
    contexts: list[str]
    ground_truth: str
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float


def load_test_set(path: str = TEST_SET_PATH) -> list[dict]:
    """Load test set from JSON. (Đã implement sẵn)"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def evaluate_ragas(questions: list[str], answers: list[str],
                   contexts: list[list[str]], ground_truths: list[str]) -> dict:
    """Run RAGAS evaluation."""
    try:
        from ragas import evaluate
        from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
        from datasets import Dataset

        dataset = Dataset.from_dict({
            "question": questions,
            "answer": answers,
            "contexts": contexts,
            "ground_truth": ground_truths,
        })
        result = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall]
        )
        df = result.to_pandas()
        per_question = []
        for _, row in df.iterrows():
            ctx = row["contexts"]
            if not isinstance(ctx, list):
                ctx = list(ctx) if hasattr(ctx, "__iter__") else [str(ctx)]

            def _val(col):
                v = row.get(col, 0.0)
                try:
                    vf = float(v)
                    return 0.0 if vf != vf else vf
                except Exception:
                    return 0.0

            per_question.append(EvalResult(
                question=str(row["question"]),
                answer=str(row["answer"]),
                contexts=ctx,
                ground_truth=str(row["ground_truth"]),
                faithfulness=_val("faithfulness"),
                answer_relevancy=_val("answer_relevancy"),
                context_precision=_val("context_precision"),
                context_recall=_val("context_recall"),
            ))

        def _get_metric(m_name):
            val = result.get(m_name, 0.0)
            try:
                vf = float(val)
                return 0.0 if vf != vf else vf
            except Exception:
                return 0.0

        return {
            "faithfulness": _get_metric("faithfulness"),
            "answer_relevancy": _get_metric("answer_relevancy"),
            "context_precision": _get_metric("context_precision"),
            "context_recall": _get_metric("context_recall"),
            "per_question": per_question,
        }
    except Exception as e:
        print(f"  ⚠️  RAGAS evaluation failed: {e}")
        print("  → Sử dụng fallback heuristic evaluation để tính toán chỉ số chi tiết.")

        per_question = []
        stopwords = {'là', 'và', 'của', 'có', 'cho', 'các', 'những', 'được', 'trong', 'với', 'khi', 'để', 'này', 'đã', 'sẽ', 'thì', 'ở', 'tại'}

        import re
        def tokenize(text: str) -> set[str]:
            return set(re.findall(r'\b\w+\b', text.lower()))

        for q, a, ctxs, gt in zip(questions, answers, contexts, ground_truths):
            gt_tokens = tokenize(gt)
            gt_content = {t for t in gt_tokens if t not in stopwords and len(t) > 1}
            ctx_all = ' '.join(ctxs)
            ctx_tokens = tokenize(ctx_all)

            # context_recall
            recall = len(gt_content & ctx_tokens) / len(gt_content) if gt_content else 1.0

            # context_precision (MAP)
            relevant_counts = 0
            prec_sum = 0.0
            for rank, ctx in enumerate(ctxs, 1):
                c_toks = tokenize(ctx)
                overlap = len(gt_content & c_toks)
                if overlap >= min(3, max(1, int(len(gt_content) * 0.25))):
                    relevant_counts += 1
                    prec_sum += relevant_counts / rank
            precision = (prec_sum / relevant_counts) if relevant_counts > 0 else 0.0

            # faithfulness
            a_tokens = tokenize(a)
            a_content = {t for t in a_tokens if t not in stopwords and len(t) > 1}
            faith = min(1.0, len(a_content & ctx_tokens) / len(a_content)) if a_content else (1.0 if not a else 0.0)

            # answer_relevancy
            q_tokens = tokenize(q)
            q_content = {t for t in q_tokens if t not in stopwords and len(t) > 1}
            ans_rel = min(1.0, len(q_content & a_tokens) / len(q_content)) if q_content else 1.0

            per_question.append(EvalResult(
                question=q,
                answer=a,
                contexts=ctxs,
                ground_truth=gt,
                faithfulness=round(faith, 4),
                answer_relevancy=round(ans_rel, 4),
                context_precision=round(precision, 4),
                context_recall=round(recall, 4),
            ))

        n = len(per_question)
        if n > 0:
            avg_faith = sum(r.faithfulness for r in per_question) / n
            avg_rel = sum(r.answer_relevancy for r in per_question) / n
            avg_prec = sum(r.context_precision for r in per_question) / n
            avg_rec = sum(r.context_recall for r in per_question) / n
        else:
            avg_faith, avg_rel, avg_prec, avg_rec = 0.0, 0.0, 0.0, 0.0

        return {
            "faithfulness": round(avg_faith, 4),
            "answer_relevancy": round(avg_rel, 4),
            "context_precision": round(avg_prec, 4),
            "context_recall": round(avg_rec, 4),
            "per_question": per_question,
        }


def failure_analysis(eval_results: list[EvalResult], bottom_n: int = 10) -> list[dict]:
    """Analyze bottom-N worst questions using Diagnostic Tree."""
    diagnostic_tree = {
        "faithfulness": ("LLM hallucinating", "Tighten prompt, lower temperature"),
        "context_recall": ("Missing relevant chunks", "Improve chunking or add BM25"),
        "context_precision": ("Too many irrelevant chunks", "Add reranking or metadata filter"),
        "answer_relevancy": ("Answer doesn't match question", "Improve prompt template"),
    }
    if not eval_results:
        return []

    scored = []
    for er in eval_results:
        scores = {
            "faithfulness": er.faithfulness,
            "answer_relevancy": er.answer_relevancy,
            "context_precision": er.context_precision,
            "context_recall": er.context_recall,
        }
        avg_score = sum(scores.values()) / 4.0
        worst_metric = min(scores, key=scores.get)
        diag, fix = diagnostic_tree.get(worst_metric, ("Unknown issue", "Review query and contexts"))
        scored.append({
            "question": er.question,
            "answer": er.answer,
            "ground_truth": er.ground_truth,
            "worst_metric": worst_metric,
            "score": scores[worst_metric],
            "avg_score": avg_score,
            "diagnosis": diag,
            "suggested_fix": fix,
        })

    scored.sort(key=lambda x: x["avg_score"])
    return scored[:bottom_n]


def save_report(results: dict, failures: list[dict], path: str = "reports/ragas_report.json"):
    """Save evaluation report to JSON. (Đã implement sẵn)"""
    parent_dir = os.path.dirname(path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    report = {
        "aggregate": {k: v for k, v in results.items() if k != "per_question"},
        "num_questions": len(results.get("per_question", [])),
        "failures": failures,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Report saved to {path}")


if __name__ == "__main__":
    test_set = load_test_set()
    print(f"Loaded {len(test_set)} test questions")
    print("Run pipeline.py first to generate answers, then call evaluate_ragas().")
