# System architecture

State: 2026-11-19. Update the diagrams and tables here when modules are added or removed, or dependencies or call order change.

Described in three views, each with the corresponding UML diagram:

| View | Question it answers | Diagram |
|---|---|---|
| 1. Layered structure | How many layers the code has, which layer depends on which | UML package diagram (layered) |
| 2. Core classes | The core abstractions and their inheritance, composition and dependencies | UML class diagram |
| 3. Runtime | In which order objects call each other during a command, how the data flows | UML sequence diagrams |

In addition, section 4 covers inputs and outputs (what goes in, which files come out, what the metadata contains), and section 5 the conventions that run through all modules.

## 1. Layered structure

```mermaid
%%{init: {"htmlLabels": false, "flowchart": {"htmlLabels": false, "wrappingWidth": 400}}}%%
flowchart TB
    subgraph L1["Entry layer"]
        cli["cli.py<br/>degfw command"]
        main["__main__.py<br/>python -m"]
        gui["gui/app.py<br/>(optional)"]
        scripts["scripts/<br/>experiments"]
    end

    subgraph L2["Framework core core/"]
        pipeline["pipeline.py<br/>chaining · batch"]
        registry["registry.py<br/>registry"]
        base["base.py<br/>base class"]
        params["params.py<br/>param types"]
        io["io.py<br/>image I/O"]
        weights["weights.py<br/>weights list"]
        paths["paths.py<br/>third-party<br/>loading"]
    end

    subgraph L3["Adapters degradations/"]
        fog["weather/<br/>fog.py"]
        noise["sensor/<br/>gaussian_<br/>noise.py"]
        lens["lens/<br/>lens_dirt.py<br/>(to do)"]
    end

    subgraph L4["Third-party code third_party/"]
        c2f["Clear2Fog/"]
        ccs["camera_<br/>contamination_<br/>simulation/"]
        wyaml["weights.yaml"]
    end

    L1 -->|"«use»"| L2
    L3 -->|"«use»"| L2
    L2 -.->|"«import» register"| L3
    L3 -.->|"«import» on demand"| L4
    L1 -.->|"«import» on demand"| L4

    classDef layer1 fill:#E3F2FD,stroke:#1E88E5,color:#0D2A4A
    classDef layer2 fill:#E8F5E9,stroke:#43A047,color:#12361A
    classDef layer3 fill:#FFF3E0,stroke:#FB8C00,color:#4A2B00
    classDef layer4 fill:#F3E5F5,stroke:#8E24AA,color:#3A0F45
    class cli,main,gui,scripts layer1
    class pipeline,registry,base,params,io,weights,paths layer2
    class fog,noise,lens layer3
    class c2f,ccs,wyaml layer4
```

Legend: solid = imported at start-up; dashed = imported at run time, when first needed.
Labels on the arrows: «use» = calls / inherits from the layer below; «import» register = the adapters are imported at the first lookup, which registers them; «import» on demand = third-party code is loaded through `core/paths.py` only when needed.

- The **core** depends on no specific degradation and not on `third_party/`: `registry.py` imports the `degradations` package only at the first lookup, to trigger registration.
  So with only the core dependencies installed (no torch etc.), the framework and the quick tests still run.
- **Adapters** depend only on the core. Third-party code is loaded only through `core/paths.py`, and only when needed: if a third-party repository lacks dependencies or weights,
  only its own degradation is marked unavailable (`degfw list` gives the reason); nothing else is affected.
- The **entry layer** contains no code for specific degradations: `degfw run <name>` works for every degradation; a degradation that needs its own command registers it itself (e.g. `degfw fog`).
- Lens contamination can currently only be run through `scripts/contamination_examples.py`; it is not integrated into the framework yet.

### Dependencies of each module

"When needed" means imported inside a function, not at start-up.

| Module | Project modules it depends on | Notes |
|---|---|---|
| `degradation_fw/__init__.py` | core.base, core.params, core.pipeline, core.registry | Public interface |
| `__main__.py` | cli | |
| `cli.py` | core.registry, core.pipeline; when needed: core.weights, gui.app | |
| `gui/app.py` | core.registry, core.io, core.params, core.pipeline | Needs gradio |
| `core/pipeline.py` | core.registry, core.io | |
| `core/registry.py` | core.base; at the first lookup: degradations | |
| `core/base.py` | core.params; when needed: core.weights | |
| `core/weights.py` | core.paths | Reads `third_party/weights.yaml` |
| `core/io.py`, `core/params.py`, `core/paths.py` | none | |
| `degradations/__init__.py` | weather.fog, sensor.gaussian_noise | Importing registers them |
| `degradations/weather/fog.py` | core.base, core.params, core.registry, core.io, core.paths, core.weights; when needed: Clear2Fog | |
| `degradations/sensor/gaussian_noise.py` | core.base, core.params, core.registry | |
| `scripts/contamination_examples.py` | core.paths, core.weights; camera_contamination_simulation | |

To check: `grep -rnE "^\s*from (\.|degradation_fw)" degradation_fw scripts`

## 2. Core classes

```mermaid
%%{init: {"htmlLabels": false, "class": {"htmlLabels": false}}}%%
classDiagram
    direction TB

    class Degradation {
        <<abstract>>
        +name: str
        +label: str
        +params: dict
        +requires_modules: tuple
        +requires_weights: tuple
        +unavailable_reason() str
        +resolve_params(overrides) dict
        +apply(image, rng, params) ndarray
    }
    class Fog {
        «param» visibility: Int
        «param» fp16: Bool
    }
    class GaussianNoise {
        «param» sigma: Float
        «param» per_channel: Bool
    }
    Degradation <|-- Fog
    Degradation <|-- GaussianNoise

    class Param {
        <<dataclass>>
        +default
        +label: str
        +validate(value)
    }
    Param <|-- Float
    Param <|-- Int
    Param <|-- Choice
    Param <|-- Bool
    Degradation "1" o-- "*" Param : params

    class Pipeline {
        +steps: list
        +seed: int
        +from_file(path) Pipeline
        +run(image, seed) tuple
        +run_file(src, dst, seed) dict
        +run_folder(src_dir, dst_dir) list
    }
    class Step {
        <<dataclass>>
        +name: str
        +params: dict
    }
    Pipeline "1" *-- "*" Step
    Pipeline ..> Degradation : by name

    class registry {
        <<module>>
        +register(cls)
        +get(name) Degradation
        +available() list
        +register_command(name)
        +commands() list
    }
    registry o-- Degradation : registered

    class Clear2Fog {
        +load(path) tuple
        +depth_from_array(rgb, f_px) ndarray
        +sky_light(rgb, depth)
        +set_average_light(paths)
        +simulate(rgb, depth, visibility) ndarray
    }
    Fog ..> Clear2Fog : engine()

    class Weight {
        <<dataclass>>
        +id: str
        +path: Path
        +size: int
        +sha256: str
        +url: str
        +present() bool
    }
    Degradation ..> Weight : requires_weights
```

- `Degradation` is the abstract base class; subclasses implement `apply()` and may only use the `rng` passed in for randomness.
  `Degradation.__call__(image, rng, **params)` first fills in defaults and validates the parameters (`resolve_params`), then calls the subclass's `apply`, and finally clips the result to `[0, 1]`.
- `Pipeline` gets each step's degradation from the registry by name (`registry.get`); `registry` holds all registered subclasses.
- `Clear2Fog` is the wrapper of the third-party code in `weather/fog.py` (Depth Pro model + `FogCamera`), created only once by `engine()` and shared by `Fog` and `degfw fog`.

## 3. Runtime

### 3.1 `degfw run` / `degfw apply` (the GUI's batch processing works the same way)

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant CLI as cli.py
    participant R as registry
    participant P as Pipeline
    participant IO as io.py
    participant D as Degradation subclass

    U->>CLI: degfw run name -i input -o output -p params
    CLI->>R: get(name)
    R-->>CLI: Degradation instance
    CLI->>D: unavailable_reason(), resolve_params(params)
    D-->>CLI: can run, params valid
    CLI->>P: Pipeline(steps, seed).run_folder(input, output)
    loop each image (sorted by path)
        P->>P: image_seed(seed, relative path)
        P->>IO: load_image(path)
        IO-->>P: float32 RGB, upright by EXIF
        loop each step (own random stream each)
            P->>R: get(step name)
            R-->>P: Degradation instance
            P->>D: deg(image, rng, params)
            D-->>P: degraded image
        end
        P->>IO: save_image(result .png, _2 if the name is taken)
        P->>P: write .json of the same name (source, seed, full params of each step)
    end
    P-->>CLI: list of output files
    CLI-->>U: Done
```

- `degfw apply` differs only at the start: steps and seed come from a YAML configuration (`Pipeline.from_file`), so several degradations can be chained.
- A single input file goes through `run_file` (no outer loop; the seed is the configured seed); for an input folder, the output folder also gets the `pipeline.yaml` used for the run.

### 3.2 `degfw fog` (the fog's own command)

```mermaid
sequenceDiagram
    autonumber
    actor UF as User
    participant F as fog.run_cli
    participant E as Clear2Fog wrapper
    participant DP as Depth Pro
    participant FC as FogCamera

    UF->>F: degfw fog -i input -o output -v visibility
    F->>F: collect_inputs, unique_stems (_2 if the name is taken)
    F->>E: engine(fp16)
    Note over E,DP: Depth Pro is loaded at the first call (about 10 s)
    loop each image
        F->>E: load(path)
        E->>DP: infer(upright RGB, EXIF focal length)
        DP-->>E: depth (metres)
        E-->>F: RGB, depth
        F->>E: sky_light(RGB, depth)
        E->>FC: estimate_atmospheric_light (only pixels ≥ 1000 m)
        FC-->>E: atmospheric light, None without sky
        E-->>F: atmospheric light or None
        opt no sky, and the average not computed yet
            F->>E: set_average_light(all inputs)
            E-->>F: average atmospheric light (0.8 if no image has sky)
        end
        loop each visibility
            F->>E: simulate(RGB, depth, visibility)
            E->>FC: simulate (Koschmieder's law)
            FC-->>E: foggy image
            E-->>F: foggy image
            F->>F: save foggy_name_vis_visibility.png
        end
    end
    F->>F: write fog_run.json
```

Details of the method and parameters: [degradations/fog.md](degradations/fog.md).

## 4. Inputs and outputs

In one sentence: **the input data is images; how they are processed is determined by the configuration; things needed to run, such as model weights, are resources;
the output is the degraded images, plus one metadata file per image that is enough to reproduce it**.
There are several entry points but only two processing paths: the general `Pipeline` path, and the fog's own command `degfw fog`.

### 4.1 Input data, configuration, resources and output location

The system's actual input is only the data to be processed; everything else either determines how it is processed (configuration) or is part of the runtime environment (resources).

| Category | What | Changes between runs? | Given by |
|---|---|---|---|
| **Input data** | Images: a single file or a folder (including subfolders), .png .jpg .jpeg .bmp .tif .tiff .webp. Later, sequences and annotations of various datasets, read through dataset adapters (M6; first example TUMTraf A9) | Yes | `-i` |
| **Configuration** | Which degradations, their parameters, the seed | Yes | Configuration file `configs/*.yaml` (`degfw apply -c`). `degfw run name -p param=value --seed N` and the GUI controls are shorthands for the same thing |
| **Resources** | Model weights (`third_party/weights.yaml`), code version and dependencies (git commit, `uv.lock`) | No, part of the runtime environment | `uv sync`, `uv run degfw weights --download` |
| **Output location** | Where the results are written | Yes | `-o` |

How each category is handled:

- **Input data**: turned upright by its EXIF orientation when read, converted to float32 RGB `[0, 1]`.
- **Configuration**: every parameter is checked against the range the degradation declares, missing ones get their defaults; in a folder run each image's seed is derived from (seed, relative path) ([decision 0003](decisions/0003-folder-seeds.md)).
  The configuration used is recorded in the output: a `pipeline.yaml` for folder runs, and the seed and full parameters of each step in every image's `.json`.
- **Resources**: a degradation whose resources are missing is marked unavailable (`degfw list` gives the reason), and its tests are skipped.
  The per-image metadata currently records only source and configuration, not code and weight versions: reproducing a result needs the same git commit and the same weights (`weights.yaml` holds their SHA-256 for checking).

### 4.2 Output: `degfw run` / `degfw apply` / GUI batch processing

```
degfw apply -c configs/fog50.yaml -i data/input -o outputs/run1

data/input/                     outputs/run1/
├── cam1/0001.jpg       →       ├── pipeline.yaml       configuration of this run
├── cam1/0002.jpg               ├── cam1/0001.png       result, always .png
└── cam2/0001.png               ├── cam1/0001.json      metadata of this image
                                ├── cam1/0002.png  + .json
                                └── cam2/0001.png  + .json
```

- The output keeps the input's subfolder structure; images with the same stem in one folder (`a.jpg` and `a.png`) become `a.png` and `a_2.png` ([decision 0005](decisions/0005-output-name-collisions.md)).
- The `.json` next to each image holds everything needed to redo it. With seed 0 in the configuration, the seed of `cam1/0001.jpg` is this value:

```json
{
  "source": "data\\input\\cam1\\0001.jpg",
  "seed": 6542102234274946371,
  "steps": [
    {"name": "fog", "params": {"visibility": 50, "fp16": false}}
  ]
}
```

- Redo a single image: `Pipeline.from_file("outputs/run1/pipeline.yaml").run_file(original, output, seed=seed from the json)`.
- For a single input file, `-o` is the output file name (e.g. `out.png`); an `out.json` is written next to it, no `pipeline.yaml`.
- The GUI's single-image mode shows result and metadata in the UI without saving files. In scripts, `Pipeline.run(image)` returns (result image, metadata) directly.

### 4.3 Output: `degfw fog` (the fog's own command, used like the original `c2f.py`)

```
degfw fog -i data/input/cam1 data/input/cam2 -o outputs/fog -v 50 200

outputs/fog/
├── foggy_0001_vis_50.png        cam1/0001.jpg, visibility 50 m
├── foggy_0001_vis_200.png
├── foggy_0001_2_vis_50.png      cam2/0001.png is also called 0001, hence _2
├── foggy_0001_2_vis_200.png
└── fog_run.json                 one per run
```

Differences to 4.2: only the .png .jpg .jpeg files directly in each folder are read (no subfolders); all results go into one folder; one image per visibility, with the depth computed only once;
the EXIF focal length is used if present; images without sky use the average atmospheric light of the whole input set.

Fields of `fog_run.json`:

| Field | Contents |
|---|---|
| `method` | `"Clear2Fog"` |
| `visibility_m` | The visibilities of the run (metres) |
| `depth_pro_precision` | `"float32"` or `"float16"` |
| `average_light` | Only if an image without sky occurred: value of the average atmospheric light and the number of images with sky it was computed from |
| `images` | One entry per input, keyed by the name used for its outputs (e.g. `0001`, `0001_2`): `source` (path of the original), `outputs` (its output files), `atmospheric_light` (`sky` or `average of input set`), `depth_m` (minimum and median depth) |

### 4.4 Not possible yet

- **Only images: no annotations, no sequences**: how sequences and annotations of various datasets are read through dataset adapters and exported together with the degraded images
  is part of M6 (first example TUMTraf A9);
  keeping degradations consistent across the frames of a sequence is part of M3 (see [roadmap.md](roadmap.md), F1, F6, F8 in [requirements.md](requirements.md)).
- **A degradation can only output one image**: masks of lens contamination cannot be output yet; this is the interface question M3 has to decide first.

## 5. Conventions across all modules

| Aspect | Convention | Where |
|---|---|---|
| Images | `float32`, `H x W x 3`, RGB, `[0, 1]`; turned upright by EXIF when read, output carries no orientation tag | `core/io.py`, [decision 0004](decisions/0004-exif-orientation.md) |
| Randomness | Degradations use only the `rng` passed in; one independent random stream per step; in folder runs each image's seed is derived from (seed, relative path) | `core/pipeline.py`, [decision 0003](decisions/0003-folder-seeds.md) |
| Metadata | A `.json` of the same name next to each result: source, seed, full parameters of each step; `_2` for taken output names | `core/pipeline.py`, [decision 0005](decisions/0005-output-name-collisions.md) |
| Registration | Importing `degradations/__init__.py` registers the adapters; adapter modules load no heavy dependencies at the top | `core/registry.py`, `degradations/_template.py` |
| Third-party code | Only the needed files are copied into `third_party/` and maintained only there; conventions for loading, dependency groups and the weights list | [decision 0001](decisions/0001-third-party-vendoring.md), [decision 0002](decisions/0002-third-party-integration.md) |
