# 0005: Taken output names get `_2`, `_3` instead of overwriting

- Status: accepted
- Date: 2026-11-19
- Related: `core/io.py` (`unique_stems`), `core/pipeline.py` (`run_folder`), `degradations/weather/fog.py` (`run_cli`); commit `b3f8e78`

## Context

- Folder runs save every result as `<stem>.png`, so `a.jpg` and `a.png` in the same folder were written to the same file (with the same `.json`), and the image processed later silently overwrote the earlier one.
- `degfw fog` puts all results into one folder, so images with the same name in different input folders overwrote each other, and so did their entries in `fog_run.json`.

## Decision

`core/io.unique_stems`: in the sorted input order, the first image keeps its name; later images whose stem is already taken (compared case-insensitively, as on Windows) get `_2`, `_3`, …

- `run_folder`: handled per output subfolder; the folder structure is kept.
- `degfw fog`: handled over all inputs together; renamed images are printed; `fog_run.json` is keyed by the output name and lists the output files of each input.

## Options considered

- **Stop with an error on a name collision**: one collision would stop the whole batch.
- **Keep the original extension in the output name** (e.g. `a.jpg.png`): every file name would change, and code that pairs originals with results by name would have to change.
- **`degfw fog` writes one output subfolder per input folder**: changes the output layout of `c2f.py`.

## Consequences

- Without collisions, file names are the same as before.
- With collisions, which image gets `_2` depends on the sort order (e.g. `a.jpg` sorts before `a.png`, so the image from `a.png` becomes `a_2.png`).
  The `source` in the `.json` next to each result always tells which original it came from.
