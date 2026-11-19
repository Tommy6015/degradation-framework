# 系统架构

当前状态：2026-11-19。增删模块、改变依赖关系或调用顺序时，更新这里的图和表。

按三个视图描述，每个视图用对应的 UML 图：

| 视图 | 回答什么问题 | 图 |
|---|---|---|
| 1. 分层结构 | 代码分几层，层与层之间谁依赖谁 | UML 包图（分层） |
| 2. 核心类 | 有哪些核心抽象，它们的继承、组合、依赖关系 | UML 类图 |
| 3. 运行时流程 | 一次命令里各对象按什么顺序调用，数据怎么流动 | UML 时序图 |

## 1. 分层结构

```mermaid
flowchart TB
    subgraph L1["入口层"]
        cli["cli.py<br/>degfw 命令"]
        main["__main__.py<br/>python -m"]
        gui["gui/app.py<br/>Gradio，可选"]
        scripts["scripts/<br/>试验脚本"]
    end

    subgraph L2["框架核心 core/"]
        pipeline["pipeline.py<br/>串联、批量、元数据"]
        registry["registry.py<br/>注册表"]
        base["base.py<br/>Degradation 基类"]
        params["params.py<br/>参数类型"]
        io["io.py<br/>图片读写"]
        weights["weights.py<br/>权重清单"]
        paths["paths.py<br/>第三方加载入口"]
    end

    subgraph L3["适配器 degradations/"]
        fog["weather/fog.py"]
        noise["sensor/gaussian_noise.py"]
        lens["lens/lens_dirt.py<br/>待实现"]
    end

    subgraph L4["第三方代码 third_party/"]
        c2f["Clear2Fog/"]
        ccs["camera_contamination_simulation/"]
        wyaml["weights.yaml"]
    end

    L1 -->|"«use»"| L2
    L3 -->|"«use» 继承基类、注册"| L2
    L2 -.->|"«import» 第一次查询时，触发注册"| L3
    L3 -.->|"«import» 用到时才加载，经 core/paths.py"| L4
    L1 -.->|"«import» 脚本直接使用，经 core/paths.py"| L4

    classDef layer1 fill:#E3F2FD,stroke:#1E88E5,color:#0D2A4A
    classDef layer2 fill:#E8F5E9,stroke:#43A047,color:#12361A
    classDef layer3 fill:#FFF3E0,stroke:#FB8C00,color:#4A2B00
    classDef layer4 fill:#F3E5F5,stroke:#8E24AA,color:#3A0F45
    class cli,main,gui,scripts layer1
    class pipeline,registry,base,params,io,weights,paths layer2
    class fog,noise,lens layer3
    class c2f,ccs,wyaml layer4
```

图例：实线 = 启动时就导入；虚线 = 运行时第一次用到才导入。

- **核心层**不依赖任何具体退化，也不依赖 `third_party/`：`registry.py` 只在第一次查询时导入 `degradations` 包来触发注册。
  所以只装核心依赖（不装 torch 等）时，框架和快速测试照样能运行。
- **适配器**只依赖核心层。第三方代码只通过 `core/paths.py` 加载，而且只在用到时加载：一个第三方仓库缺依赖或缺权重，
  只会让它自己的退化标为不可用（`degfw list` 写明原因），不影响其他部分。
- **入口层**里没有具体退化的代码：`degfw run <名字>` 对所有退化通用；个别退化需要专门命令时自己注册（如 `degfw fog`）。
- 镜头污染目前只能通过 `scripts/contamination_examples.py` 运行，还没有接入框架。

### 各模块的依赖明细

"用到时"表示在函数里导入，不在启动时导入。

| 模块 | 依赖的项目内模块 | 备注 |
|---|---|---|
| `degradation_fw/__init__.py` | core.base、core.params、core.pipeline、core.registry | 对外接口 |
| `__main__.py` | cli | |
| `cli.py` | core.registry、core.pipeline；用到时：core.weights、gui.app | |
| `gui/app.py` | core.registry、core.io、core.params、core.pipeline | 需要 gradio |
| `core/pipeline.py` | core.registry、core.io | |
| `core/registry.py` | core.base；第一次查询时：degradations | |
| `core/base.py` | core.params；用到时：core.weights | |
| `core/weights.py` | core.paths | 读 `third_party/weights.yaml` |
| `core/io.py`、`core/params.py`、`core/paths.py` | 无 | |
| `degradations/__init__.py` | weather.fog、sensor.gaussian_noise | 导入即注册 |
| `degradations/weather/fog.py` | core.base、core.params、core.registry、core.io、core.paths、core.weights；用到时：Clear2Fog | |
| `degradations/sensor/gaussian_noise.py` | core.base、core.params、core.registry | |
| `scripts/contamination_examples.py` | core.paths、core.weights；camera_contamination_simulation | |

核对时用：`grep -rnE "^\s*from (\.|degradation_fw)" degradation_fw scripts`

## 2. 核心类

```mermaid
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
    note for Degradation "子类实现 apply()；只能用传入的 rng"

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
    Pipeline ..> Degradation : 按名字从注册表取

    class registry {
        <<module>>
        +register(cls)
        +get(name) Degradation
        +available() list
        +register_command(name)
        +commands() list
    }
    registry o-- Degradation : 已注册的子类

    class Clear2Fog {
        +load(path) tuple
        +depth_from_array(rgb, f_px) ndarray
        +sky_light(rgb, depth)
        +set_average_light(paths)
        +simulate(rgb, depth, visibility) ndarray
    }
    Fog ..> Clear2Fog : engine()，只加载一次

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

- `Degradation.__call__(image, rng, **params)` 先补默认值、校验参数（`resolve_params`），再调用子类的 `apply`，最后把结果限制在 `[0, 1]`。
- `Clear2Fog` 是 `weather/fog.py` 里对第三方代码的封装（Depth Pro 模型 + `FogCamera`），由 `engine()` 只创建一次，供 `Fog` 和 `degfw fog` 共用。

## 3. 运行时流程

### 3.1 `degfw run` / `degfw apply`（GUI 的批量处理同理）

```mermaid
sequenceDiagram
    autonumber
    actor U as 用户
    participant CLI as cli.py
    participant R as registry
    participant P as Pipeline
    participant IO as io.py
    participant D as Degradation 子类

    U->>CLI: degfw run 名字 -i 输入 -o 输出 -p 参数
    CLI->>R: get(名字)
    R-->>CLI: Degradation 实例
    CLI->>D: unavailable_reason()、resolve_params(参数)
    D-->>CLI: 能运行，参数有效
    CLI->>P: Pipeline(步骤, 种子).run_folder(输入, 输出)
    loop 每张图片（按路径排序）
        P->>P: image_seed(种子, 相对路径)
        P->>IO: load_image(路径)
        IO-->>P: float32 RGB，已按 EXIF 转正
        loop 每个步骤（各用一个独立随机流）
            P->>R: get(步骤名)
            R-->>P: Degradation 实例
            P->>D: deg(图, rng, 参数)
            D-->>P: 退化后的图
        end
        P->>IO: save_image(结果 .png，同名加 _2)
        P->>P: 写同名 .json（来源、种子、每步完整参数）
    end
    P-->>CLI: 输出文件列表
    CLI-->>U: Done
```

- `degfw apply` 的区别只在开头：步骤和种子来自 YAML 配置（`Pipeline.from_file`），可以串联多个退化。
- 输入是单个文件时走 `run_file`（没有外层循环，种子直接用配置的种子）；输入是文件夹时，输出文件夹里还会存一份这次用的 `pipeline.yaml`。

### 3.2 `degfw fog`（雾的专门命令）

```mermaid
sequenceDiagram
    autonumber
    actor U as 用户
    participant F as fog.run_cli
    participant E as Clear2Fog 封装
    participant DP as Depth Pro
    participant FC as FogCamera

    U->>F: degfw fog -i 输入 -o 输出 -v 能见度
    F->>F: collect_inputs、unique_stems（同名加 _2）
    F->>E: engine(fp16)
    Note over E,DP: 第一次调用时加载 Depth Pro（约 10 s）
    loop 每张图片
        F->>E: load(路径)
        E->>DP: infer(转正后的 RGB, EXIF 焦距)
        DP-->>E: 景深（米）
        E-->>F: RGB、景深
        F->>E: sky_light(RGB, 景深)
        E->>FC: estimate_atmospheric_light（只看 ≥ 1000 m 的像素）
        FC-->>E: 大气光，没有天空时为 None
        E-->>F: 大气光或 None
        opt 没有天空，且还没算过平均值
            F->>E: set_average_light(全部输入)
            E-->>F: 平均大气光（都没有天空时为 0.8）
        end
        loop 每个能见度
            F->>E: simulate(RGB, 景深, 能见度)
            E->>FC: simulate（Koschmieder 公式）
            FC-->>E: 有雾图
            E-->>F: 有雾图
            F->>F: 保存 foggy_名字_vis_能见度.png
        end
    end
    F->>F: 写 fog_run.json
```

方法和参数的细节见 [degradations/fog.md](degradations/fog.md)。

## 4. 贯穿各模块的约定

| 方面 | 约定 | 在哪里 |
|---|---|---|
| 图像 | `float32`、`H x W x 3`、RGB、`[0, 1]`；读图时按 EXIF 转正，输出不带方向标记 | `core/io.py`、[决策 0004](decisions/0004-exif-orientation.md) |
| 随机数 | 退化只能用传入的 `rng`；每个步骤一个独立随机流；批量时每张图的种子由（种子, 相对路径）算出 | `core/pipeline.py`、[决策 0003](decisions/0003-folder-seeds.md) |
| 元数据 | 每张结果旁一个同名 `.json`：来源、种子、每步的完整参数；同名输出加 `_2` | `core/pipeline.py`、[决策 0005](decisions/0005-output-name-collisions.md) |
| 注册 | `degradations/__init__.py` 导入即注册；适配器文件开头不加载重依赖 | `core/registry.py`、`degradations/_template.py` |
| 第三方代码 | 只复制需要的文件到 `third_party/`，只在这里维护；加载、依赖组、权重清单的约定 | [决策 0001](decisions/0001-third-party-vendoring.md)、[决策 0002](decisions/0002-third-party-integration.md) |
