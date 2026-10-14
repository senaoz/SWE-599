"""Check Qwen3-Reranker-4B before using it (Phase 5, notebook 11).

Compares, on up to 20 dev (query, candidate) pairs (17 in the 2026-10-13 run: one query has
only 2 cited papers in its top 100):
- the reference implementation from the model card (transformers, P(yes) from the
  "yes"/"no" logits at the last position), in float32 and float16 on MPS;
- the sentence-transformers CrossEncoder (sigmoid of the yes-no logit difference),
  which uses the model's own chat template.
Also times each path. Output: data/v2/logs/qwen3_reranker_check.json.

    .venv/bin/python scripts/check_qwen3_reranker.py
"""
from __future__ import annotations

import gc
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from scipy.stats import spearmanr

RESEARCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RESEARCH))

from src.retrieval import load_phase5  # noqa: E402

MODEL = "Qwen/Qwen3-Reranker-4B"
REVISION = "22e683669bc0f0bd69640a1354a6d0aebcfeede5"
TASK = "Given the title and abstract of a scientific paper, retrieve papers that it cites"
PREFIX = ("<|im_start|>system\nJudge whether the Document meets the requirements based on the Query "
          "and the Instruct provided. Note that the answer can only be \"yes\" or \"no\".<|im_end|>\n<|im_start|>user\n")
SUFFIX = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
BATCH = 4


def pairs_for_check(S) -> tuple[list[tuple[str, str]], list[int]]:
    """Up to 5 cited and 5 other candidates from Qwen3-Embedding's top 100, for the first two dev queries."""
    with (RESEARCH / "v2" / "runs_corpus" / "stage1" / "qwen.jsonl").open() as f:
        top = {r["pi_id"]: r["top100"] for r in map(json.loads, f)}
    qrow = {q: i for i, q in enumerate(S["qids"])}
    text = dict(zip(S["doc_ids"], S["doc_texts"]))
    pairs, labels = [], []
    for q in [q for q in S["qids"] if S["labels"][q]["split"] == "dev"][:2]:
        pos = set(S["labels"][q]["positives"])
        chosen = [d for d in top[q] if d in pos][:5] + [d for d in top[q] if d not in pos][:5]
        pairs += [(S["query_texts"][qrow[q]], text[d]) for d in chosen]
        labels += [int(d in pos) for d in chosen]
    return pairs, labels


def reference_scores(pairs, dtype) -> tuple[list[float], float]:
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MODEL, revision=REVISION, padding_side="left")
    model = AutoModelForCausalLM.from_pretrained(MODEL, revision=REVISION, dtype=dtype).to("mps").eval()
    yes, no = tok.convert_tokens_to_ids("yes"), tok.convert_tokens_to_ids("no")
    pre, suf = tok.encode(PREFIX, add_special_tokens=False), tok.encode(SUFFIX, add_special_tokens=False)
    texts = [f"<Instruct>: {TASK}\n<Query>: {q}\n<Document>: {d}" for q, d in pairs]
    out, t0 = [], time.time()
    with torch.no_grad():
        for i in range(0, len(texts), BATCH):
            enc = tok(texts[i:i + BATCH], padding=False, truncation="longest_first",
                      return_attention_mask=False, max_length=8192 - len(pre) - len(suf))
            enc["input_ids"] = [pre + ids + suf for ids in enc["input_ids"]]
            enc = tok.pad(enc, padding=True, return_tensors="pt").to("mps")
            logits = model(**enc).logits[:, -1, :].float()
            two = torch.log_softmax(torch.stack([logits[:, no], logits[:, yes]], dim=1), dim=1)
            out += two[:, 1].exp().tolist()
    torch.mps.synchronize()
    elapsed = time.time() - t0
    del model
    gc.collect()
    torch.mps.empty_cache()
    return out, elapsed / len(pairs)


def st_scores(pairs) -> tuple[list[float], float]:
    from sentence_transformers import CrossEncoder
    model = CrossEncoder(MODEL, revision=REVISION, device="mps", prompts={"cites": TASK}, default_prompt_name="cites")
    t0 = time.time()
    s = model.predict(pairs, batch_size=BATCH, activation_fn=torch.nn.Sigmoid())
    torch.mps.synchronize()
    elapsed = time.time() - t0
    del model
    gc.collect()
    torch.mps.empty_cache()
    return [float(x) for x in s], elapsed / len(pairs)


def main() -> None:
    S = load_phase5(RESEARCH)
    pairs, labels = pairs_for_check(S)
    ref32, t32 = reference_scores(pairs, torch.float32)
    ref16, t16 = reference_scores(pairs, torch.float16)
    st, tst = st_scores(pairs)
    a32, a16, ast = map(np.array, (ref32, ref16, st))
    lab = np.array(labels)
    report = {
        "model": MODEL, "revision": REVISION, "instruction": TASK, "pairs": len(pairs),
        "seconds_per_pair": {"reference_fp32": t32, "reference_fp16": t16, "sentence_transformers": tst},
        "nan": {"fp32": int(np.isnan(a32).sum()), "fp16": int(np.isnan(a16).sum()), "st": int(np.isnan(ast).sum())},
        "fp16_vs_fp32": {"max_abs_diff": float(np.nanmax(np.abs(a16 - a32))), "spearman": float(spearmanr(a16, a32)[0])},
        "st_vs_reference_fp32": {"max_abs_diff": float(np.nanmax(np.abs(ast - a32))), "spearman": float(spearmanr(ast, a32)[0])},
        "mean_score_cited_vs_other_fp32": [float(a32[lab == 1].mean()), float(a32[lab == 0].mean())],
        "scores": {"labels": labels, "fp32": ref32, "fp16": ref16, "st": st},
    }
    out = RESEARCH / "data" / "v2" / "logs" / "qwen3_reranker_check.json"
    out.write_text(json.dumps(report, indent=1))
    print(json.dumps({k: v for k, v in report.items() if k != "scores"}, indent=1))


if __name__ == "__main__":
    main()
