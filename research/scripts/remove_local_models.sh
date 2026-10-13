#!/usr/bin/env bash
# Remove the local models downloaded for the v2 benchmark.
# Dry run by default; pass --yes to actually delete.
#
#   bash research/scripts/remove_local_models.sh        # list what would be removed
#   bash research/scripts/remove_local_models.sh --yes  # remove
#
# GGUF models are matched by name in their model.yml, so the bundled
# sentence-transformer-mini embedder is left alone. Removed models are also
# dropped from the llama-server preset, and the server is restarted.
set -euo pipefail

GGUF_MODELS="${GGUF_MODELS:-$HOME/models/gguf}"
PRESET="${LLAMA_PRESET:-$HOME/models/llama-server.ini}"
LAUNCHD_LABEL="${LLAMA_LAUNCHD_LABEL:-com.senaoz.llama-server}"
HF_HUB="${HF_HUB_CACHE:-$HOME/.cache/huggingface/hub}"

GGUF_PATTERNS=("Llama-3.2-3B-Instruct" "Llama-3_2-3B-Instruct" "Qwen3-Embedding-8B" "embeddinggemma-300")
HF_REPOS=(
  "sentence-transformers/all-MiniLM-L6-v2"
  "allenai/specter2_base"
  "BAAI/bge-reranker-base"
)

# Model ids are paths relative to GGUF_MODELS (e.g. Qwen/Qwen3-Embedding-8B-Q4_K_M),
# matching the section names in the preset and the ids served under /v1/models.
targets=()
if [[ -d "$GGUF_MODELS" ]]; then
  while IFS= read -r yml; do
    dir="$(dirname "$yml")"
    for pat in "${GGUF_PATTERNS[@]}"; do
      if grep -qi -- "$pat" "$yml" || [[ "$dir" == *"$pat"* ]]; then
        targets+=("${dir#"$GGUF_MODELS"/}")
        break
      fi
    done
  done < <(find "$GGUF_MODELS" -name model.yml | sort)
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
  if [[ ${#targets[@]} -gt 0 ]]; then
    echo "GGUF models (and their sections in $PRESET):"
    for id in "${targets[@]}"; do du -sh "$GGUF_MODELS/$id"; done
  fi
  if [[ ${#hf_targets[@]} -gt 0 ]]; then
    echo "Hugging Face cache:"
    hf cache rm "${hf_targets[@]}" --dry-run
  fi
  echo
  echo "Dry run. Re-run with --yes to delete."
  exit 0
fi

for id in "${targets[@]}"; do
  rm -rf -- "${GGUF_MODELS:?}/$id"
  rmdir "$(dirname "$GGUF_MODELS/$id")" 2>/dev/null || true
  echo "Removed $GGUF_MODELS/$id"
  if [[ -f "$PRESET" ]]; then
    awk -v sec="[$id]" '
      /^\[/ { skip = ($0 == sec) }
      !skip
    ' "$PRESET" > "$PRESET.tmp" && mv "$PRESET.tmp" "$PRESET"
  fi
done
if [[ ${#hf_targets[@]} -gt 0 ]]; then
  hf cache rm "${hf_targets[@]}" -y
fi

if [[ ${#targets[@]} -gt 0 ]]; then
  if launchctl print "gui/$(id -u)/$LAUNCHD_LABEL" >/dev/null 2>&1; then
    launchctl kickstart -k "gui/$(id -u)/$LAUNCHD_LABEL"
    echo "Restarted llama-server so it drops the removed models."
  else
    echo "Restart llama-server so it drops the removed models."
  fi
fi
echo "Done."
