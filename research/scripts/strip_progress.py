"""Remove progress-bar noise (stderr streams) from executed notebooks.

Progress bars stay in the papermill log (data/v2/logs/); the notebook keeps only
tables, prints and figures, so it reads cleanly in the paper workflow.

    .venv/bin/python scripts/strip_progress.py v2/03_dev_tuning.ipynb [...]
"""
import sys

import nbformat

for path in sys.argv[1:]:
    nb = nbformat.read(path, as_version=4)
    removed = 0
    for cell in nb.cells:
        if cell.cell_type != "code":
            continue
        kept = [o for o in cell.get("outputs", []) if not (o.get("output_type") == "stream" and o.get("name") == "stderr")]
        removed += len(cell.get("outputs", [])) - len(kept)
        cell["outputs"] = kept
    nbformat.write(nb, path)
    print(f"{path}: removed {removed} stderr outputs")
