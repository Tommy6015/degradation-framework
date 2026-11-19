# doc_EN: development documents (English)

This folder is the English version of [`doc/`](../doc/README.md). **The Chinese version in `doc/` is the master**:
when a file in `doc/` changes, the file with the same name here is updated accordingly.

The root `README.md` only covers the project as a whole: what it is, how the folders are organised, how to set up
the environment, how to develop. Documents for managing the development and the details of each part are here.

| Document | Contents | When to update |
|---|---|---|
| [requirements.md](requirements.md) | Requirements derived from the thesis task sheet: ID, subtask it comes from, acceptance method, current status | When requirements change, or the status of one changes |
| [roadmap.md](roadmap.md) | Thesis scope, the **overall architecture of the thesis project** (five stages from data sources to the thesis), milestones, open decisions | When a milestone is completed or the plan changes |
| [architecture.md](architecture.md) | Architecture **inside this repository**: layered package diagram, core class diagram, runtime sequence diagrams, inputs and outputs, cross-cutting conventions | When modules are added or removed, or dependencies, call order or output formats change |
| [decisions/](decisions/README.md) | Decision records: one file per decision, with context, decision, rejected options and consequences | A new file whenever a key decision is made (or reversed) |
| [status/](status/) | Weekly status, one file per week, e.g. `2026-W47.md`; includes the acceptance criteria and check results of the features developed that week | Updated during the week; a new file every Monday from `status/template.md` |
| [degradations/](degradations/) | Detailed usage, method and caveats of each degradation | When its parameters, command or behaviour change |

Conventions:

- Diagrams are written in [Mermaid](https://mermaid.js.org/) inside the Markdown (previewed in VS Code with a Mermaid extension, rendered directly on GitHub). When drawing:
  - Boxes only carry short names, a few words per line; descriptions go into a table below the diagram. Long text in a box gets cut off or wrapped in the preview.
  - Long words that must not be split, such as file names, are kept to at most 12 characters per part; longer ones are broken by hand with `<br/>` at `/` or `_`,
    otherwise the preview breaks them in the middle (e.g. `lens_dirt.p / y`).
  - Flowcharts (`flowchart`) and class diagrams (`classDiagram`) start with an `%%{init: ...}%%` line as in `architecture.md`, which turns off `htmlLabels`:
    Mermaid then lays out the text itself, unaffected by the preview's styles.
- Before a feature is developed, its acceptance criteria are listed in the current week's status file; when it is done, each criterion is checked in the same table, with result and evidence.
  A feature spanning several weeks keeps its table in the week it started; later weeks link to it.
- Weeks are numbered as ISO weeks (starting on Monday): `uv run python -c "import datetime; print(datetime.date.today().isocalendar())"`.
- When documents mention code, commits or decisions, they give the file name, commit hash or decision number, so they can be traced back.
