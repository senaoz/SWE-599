#!/usr/bin/env bash
# Remove the local models downloaded for the v2 benchmark.
# Dry run by default; pass --yes to actually delete.
#
#   bash research/scripts/remove_local_models.sh        # list what would be removed
#   bash research/scripts/remove_local_models.sh --yes  # remove
#
# Jan models are matched by name in their model.yml, so Jan's bundled
# sentence-transformer-mini embedder is left alone. Quit Jan before removing.
set -euo pipefail

JAN_MODELS="${JAN_MODELS:-$HOME/Library/Application Support/Jan/data/llamacpp/models}"
HF_HUB="${HF_HUB_CACHE:-$HOME/.cache/huggingface/hub}"

JAN_PATTERNS=("Llama-3.2-3B-Instruct" "Qwen3-Embedding-8B" "embeddinggemma-300")
HF_REPOS=(
  "sentence-transformers/all-MiniLM-L6-v2"
  "allenai/specter2_base"
  "BAAI/bge-reranker-base"
)

targets=()

if [[ -d "$JAN_MODELS" ]]; then
  for dir in "$JAN_MODELS"/*/; do
    yml="$dir/model.yml"
    [[ -f "$yml" ]] || continue
    for pat in "${JAN_PATTERNS[@]}"; do
      if grep -qi -- "$pat" "$yml" || [[ "$(basename "$dir")" == *"$pat"* ]]; then
        targets+=("${dir%/}")
        break
      fi
    done
  done
fi

# Hugging Face keeps weights in a shared blobs/ store, so go through `hf cache rm`
# rather than deleting the models--* folders (which only hold symlinks).
hf_targets=()
for repo in "${HF_REPOS[@]}"; do
  [[ -d "$HF_HUB/models--${repo//\//--}" ]] && hf_targets+=("model/$repo")
done

if [[ ${#targets[@]} -eq 0 && ${#hf_targets[@]} -eq 0 ]]; then
  echo "Nothing to remove."
  exit 0
fi

if [[ "${1:-}" != "--yes" ]]; then
  echo "Jan models:"
  for t in "${targets[@]}"; do du -sh "$t"; done
  if [[ ${#hf_targets[@]} -gt 0 ]]; then
    echo "Hugging Face cache:"
    hf cache rm "${hf_targets[@]}" --dry-run
  fi
  echo
  echo "Dry run. Re-run with --yes to delete."
  exit 0
fi

for t in "${targets[@]}"; do
  rm -rf -- "$t"
  echo "Removed $t"
done
if [[ ${#hf_targets[@]} -gt 0 ]]; then
  hf cache rm "${hf_targets[@]}" -y
fi
echo "Done. Restart Jan so it drops the removed models from its list."
