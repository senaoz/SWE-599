"""Phase 5 second stage: pointwise scores for first-stage lists (task 5.8).

Two pointwise scorers: Llama 3.2 3B with the v2 prompt (0–10 rating from logprobs), and
Qwen3-Reranker-4B with the model card's reference implementation (P(yes)). Each sees
one (query, candidate) pair at a time, so a score does not depend on list order or on
which list the candidate came from. Scores are cached per (query, doc) in a JSONL file,
so overlapping lists are scored once and an interrupted run resumes.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from src.rankers_v2 import pointwise_score


QWEN3_RERANKER = "Qwen/Qwen3-Reranker-4B"
QWEN3_RERANKER_REVISION = "22e683669bc0f0bd69640a1354a6d0aebcfeede5"
CITATION_TASK = "Given the title and abstract of a scientific paper, retrieve papers that it cites"


class Qwen3Reranker:
    """Model-card reference implementation of Qwen3-Reranker, in float16 on MPS.

    scripts/check_qwen3_reranker.py found float16 within 0.006 of float32 (Spearman 1.0)
    and no NaNs on 17 dev pairs.
    """

    PREFIX = ("<|im_start|>system\nJudge whether the Document meets the requirements based on the Query "
              "and the Instruct provided. Note that the answer can only be \"yes\" or \"no\".<|im_end|>\n<|im_start|>user\n")
    SUFFIX = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"

    def __init__(self, instruction: str = CITATION_TASK, batch_size: int = 8, device: str = "mps"):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.torch, self.device, self.batch_size, self.instruction = torch, device, batch_size, instruction
        self.tok = AutoTokenizer.from_pretrained(QWEN3_RERANKER, revision=QWEN3_RERANKER_REVISION, padding_side="left")
        self.model = AutoModelForCausalLM.from_pretrained(
            QWEN3_RERANKER, revision=QWEN3_RERANKER_REVISION, dtype=torch.float16).to(device).eval()
        self.yes, self.no = self.tok.convert_tokens_to_ids("yes"), self.tok.convert_tokens_to_ids("no")
        self.pre = self.tok.encode(self.PREFIX, add_special_tokens=False)
        self.suf = self.tok.encode(self.SUFFIX, add_special_tokens=False)

    def __call__(self, query: str, texts: list[str]) -> list[dict]:
        torch = self.torch
        out = []
        with torch.no_grad():
            for i in range(0, len(texts), self.batch_size):
                batch = [f"<Instruct>: {self.instruction}\n<Query>: {query}\n<Document>: {d}"
                         for d in texts[i:i + self.batch_size]]
                enc = self.tok(batch, padding=False, truncation="longest_first", return_attention_mask=False,
                               max_length=8192 - len(self.pre) - len(self.suf))
                enc["input_ids"] = [self.pre + ids + self.suf for ids in enc["input_ids"]]
                enc = self.tok.pad(enc, padding=True, return_tensors="pt").to(self.device)
                logits = self.model(**enc).logits[:, -1, :].float()
                p_yes = torch.log_softmax(torch.stack([logits[:, self.no], logits[:, self.yes]], 1), 1)[:, 1].exp()
                for p in p_yes.tolist():
                    ok = p == p  # NaN check
                    out.append({"score": p if ok else None, "status": "ok" if ok else "nan", "scoring": "p_yes"})
        return out


def llama_pointwise(query: str, texts: list[str], model: str | None = None, **kw) -> list[dict]:
    return [pointwise_score(query, t, model=model, **kw) for t in texts]


class PointwiseCache:
    def __init__(self, path: Path, model: str | None = None, scorer=None):
        """scorer(query, texts) -> [{"score", "status", "scoring"}]; default: Llama 3.2 3B pointwise."""
        self.path, self.model = Path(path), model
        self.scorer = scorer or (lambda q, texts: llama_pointwise(q, texts, model=model))
        self.scores: dict[tuple[str, str], dict] = {}
        if self.path.exists():
            with self.path.open() as f:
                for r in map(json.loads, f):
                    self.scores[(r["pi_id"], r["doc"])] = r

    def ensure(self, qid: str, query_text: str, docs: list[str], doc_text) -> int:
        """Score every doc not yet cached for this query; returns the number of new calls."""
        todo = [d for d in docs if (qid, d) not in self.scores]
        if not todo:
            return 0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        step = getattr(self.scorer, "batch_size", 1)
        with self.path.open("a") as f:
            for i in range(0, len(todo), step):
                chunk = todo[i:i + step]
                for d, out in zip(chunk, self.scorer(query_text, [doc_text(d) for d in chunk])):
                    rec = {"pi_id": qid, "doc": d, "score": out["score"], "status": out["status"],
                           "scoring": out.get("scoring")}
                    self.scores[(qid, d)] = rec
                    f.write(json.dumps(rec) + "\n")
                f.flush()
        return len(todo)

    def get(self, qid: str, docs: list[str]) -> np.ndarray:
        """Scores in `docs` order; a failed call scores -1, below every valid score (0–10 or 0–1)."""
        return np.array([s if (s := self.scores[(qid, d)]["score"]) is not None else -1.0 for d in docs])


def minmax(x: np.ndarray) -> np.ndarray:
    lo, hi = x.min(), x.max()
    return (x - lo) / (hi - lo) if hi > lo else np.zeros_like(x, dtype=float)


def fuse_order(order: np.ndarray, llm: np.ndarray, first: np.ndarray, alpha: float) -> np.ndarray:
    """Rerank one list by alpha * llm + (1 - alpha) * first-stage score, both min-max
    normalized within the list; ties keep the first-stage order."""
    s = alpha * minmax(llm) + (1 - alpha) * minmax(first)
    return order[np.lexsort((np.arange(len(order)), -s))]
