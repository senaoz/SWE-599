from src.pipeline_v2 import RunConfig, method_name, run_path


def test_default_llm_keeps_existing_run_names():
    cfg = RunConfig(bench="random", stage1_k=10)
    assert [method_name(m, cfg) for m in ("llama", "llama-window", "qwen→llama", "llama+minilm")] == \
        ["llama", "llama-window", "qwen→llama_k10_shuffled", "llama+minilm"]


def test_other_llm_gets_its_own_run_files():
    base, big = RunConfig(bench="random"), RunConfig(bench="random", llm="llama8b")
    for m in ("llama", "llama-window", "llama-pointwise", "qwen→llama", "llama+minilm"):
        assert run_path(big, m, "shuffled", 0) != run_path(base, m, "shuffled", 0)
    assert method_name("qwen", big) == "qwen"


def test_check_jan_asks_only_for_the_chosen_llm(monkeypatch):
    from src import jan
    from src.pipeline_v2 import check_jan
    monkeypatch.setattr(jan, "list_models", lambda: [jan.JAN_MODEL_MAP["llama8b"]])
    assert check_jan(["llama", "llama-window"], "llama8b") == [jan.JAN_MODEL_MAP["llama8b"]]
