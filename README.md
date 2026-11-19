# degradation-framework：图像退化生成框架

用统一接口封装各种图像退化（雾、镜头脏污、水滴……），可单张或批量处理，参数和随机种子全程可复现。
图形界面暂缓，等底层退化做好再接。

仓库名用全称 `degradation-framework`；代码里用简写：Python 包名 `degradation_fw`（`import degradation_fw`），命令行命令 `degfw`。

这是一个**工作区**：在仓库里用 `uv run` 运行，不是可以 `pip install` 到别处的库
（代码按源码位置找 `third_party/`，打成 wheel 单独安装后找不到）。

这个 README 只讲整个项目；路线图、系统架构图、关键决策记录、每周状态和各退化的详细用法在 [`doc/`](doc/README.md)。

## 目录结构：什么东西放哪里

```
degradation-framework/
├── third_party/                 ① 开源代码原样放这里，一个仓库一个文件夹
│   ├── README.md                   引入规则 + 来源登记表（每个仓库一行）
│   ├── weights.yaml                所有模型权重：路径、大小、SHA-256、下载地址
│   ├── Clear2Fog/                  雾（Depth Pro 权重不在 git 里，用 degfw weights --download 下载）
│   │   └── LOCAL_CHANGES.md          引入了哪些文件、改了什么
│   └── camera_contamination_simulation/   镜头污染
│       └── LOCAL_CHANGES.md
│
├── degradation_fw/              ② 你自己的框架代码
│   ├── core/                       框架核心，一般不用动
│   │   ├── base.py                   Degradation 基类（统一接口，声明需要的依赖和权重）
│   │   ├── params.py                 参数类型 Float / Int / Choice / Bool
│   │   ├── registry.py               注册表（退化 + 退化自带的命令）
│   │   ├── pipeline.py               多个退化串联、批量处理、保存元数据
│   │   ├── io.py                     图片读写、格式转换（支持中文路径）
│   │   ├── paths.py                  项目路径；加载 third_party 代码的唯一入口
│   │   └── weights.py                读 weights.yaml：查找、校验、下载权重
│   │
│   ├── degradations/               ③ 适配器：把开源代码包装成统一接口，按类别分
│   │   ├── _template.py              新退化照这个模板写
│   │   ├── weather/                  天气 / 大气
│   │   │   └── fog.py                  雾：Clear2Fog 适配器 + 它自己注册的 `degfw fog` 命令
│   │   ├── lens/                     镜头污染
│   │   │   └── lens_dirt.py            脏污：不透明 + 水滴（待实现）
│   │   └── sensor/                   传感器 / 成像
│   │       └── gaussian_noise.py       高斯噪声（示例，验证框架用）
│   │
│   ├── gui/                        界面（暂缓；已有一个能跑的 Gradio 初版）
│   └── cli.py                      命令行入口（不含任何具体退化的代码）
│
├── configs/                     ④ 参数预设（YAML），一次实验一个文件
├── scripts/                     ⑤ 自己的试验脚本和工具
│   └── contamination_examples.py   镜头污染的运行脚本（选项见 scripts/README.md）
├── doc/                         ⑥ 开发过程文档（入口 doc/README.md）
│   ├── roadmap.md                  目标、里程碑、下一步
│   ├── architecture.md             模块依赖图、数据流图
│   ├── decisions/                  关键决策记录，一个决定一个文件
│   ├── status/                     每周状态，一周一个文件
│   └── degradations/               各退化的详细用法
├── tests/                          测试
│   ├── test_*.py                     框架本身；test_contract.py 自动检查每个已注册的退化
│   ├── degradations/test_<名字>.py   每个退化自己的测试
│   └── data/                         回归测试用的小图
├── data/                           输入图片（不提交到 git）
└── outputs/                        输出结果（不提交到 git）
```

| 你手上的东西 | 放哪里 |
|---|---|
| 下载的开源代码 | `third_party/<仓库名>/`，原样放，保留 LICENSE，在 `third_party/README.md` 登记 |
| 开源代码需要的 Python 包 | `pyproject.toml` 里这个仓库的 dependency group |
| 开源代码的模型权重 | 文件跟着它留在 `third_party/<仓库名>/` 里，并在 `third_party/weights.yaml` 登记一条 |
| 对开源代码的调整（格式转换、参数换算） | `degradation_fw/degradations/<类别>/xxx.py` 适配器里 |
| 必须直接改开源代码本身 | 直接在 `third_party/` 里改，单独提交（提交说明以 `third_party/<仓库名>:` 开头）；和原版的差别用 git 查看，命令见它的 `LOCAL_CHANGES.md`。第三方代码只在这里维护，不另外维护 fork |
| 自己写的、用开源代码的脚本或工具 | `scripts/`（不放进 `third_party/`） |
| 某次实验的参数组合 | `configs/xxx.yaml` |
| 测试用的小图、参考结果 | `tests/data/` |
| 输入图片 / 生成的数据集 | `data/`、`outputs/` |
| 开发计划、每周进展 | `doc/roadmap.md`、`doc/status/<年>-W<周>.md` |
| 一个关键决定（为什么这样做、放弃了哪些方案） | `doc/decisions/NNNN-xxx.md`（写法见 `doc/decisions/README.md`） |
| 某种退化的详细用法、方法 | `doc/degradations/<名字>.md` |

## 已有的退化

| 退化 | 说明 | 详细用法 |
|---|---|---|
| `fog` | 雾：Clear2Fog（Depth Pro 景深 + 大气散射），有自己的命令 `uv run degfw fog -i 输入 -o 输出 -v 100` | [doc/degradations/fog.md](doc/degradations/fog.md) |
| `gaussian_noise` | 高斯噪声，示例，用来验证框架 | 参数见 `uv run degfw list` |
| 镜头污染 | 还没接入框架，目前用 `scripts/contamination_examples.py` 单独运行 | [scripts/README.md](scripts/README.md) |

## 添加一种退化

1. 把开源代码原样复制到 `third_party/<仓库名>/`，在 `third_party/README.md` 登记来源，**单独提交一次**。
2. 它需要的 Python 包：在 `pyproject.toml` 里加一个 dependency group，然后 `uv lock`。
   模型权重：在 `third_party/weights.yaml` 里每个文件登记一条，然后 `uv run degfw weights --download`。
3. 照 `degradations/_template.py` 写适配器，例如 `degradations/weather/rain.py`：
   用 `requires_modules` / `requires_weights` 声明需要什么，第三方代码只通过 `core/paths.py` 的函数、并且在用到时才加载。
4. 在 `degradations/__init__.py` 里加上 `from .weather import rain`。
   之后 `degfw list`、`degfw run rain`、配置文件和 GUI 都能直接用它，不用改别处。
5. 在 `tests/degradations/test_rain.py` 写它自己的测试；运行 `uv run pytest`，
   `test_contract.py` 还会自动检查它的输出格式和可复现性。

## 环境与使用

用 [uv](https://docs.astral.sh/uv/) 管理环境：

```bash
uv sync                             # 装好全部依赖（每个 third_party 仓库一组，默认全装）
uv run degfw weights --download     # 下载缺的模型权重；不加参数只查看状态，--verify 校验 SHA-256
uv run degfw list                   # 所有退化、参数，以及在这台机器上能不能运行
uv run degfw run gaussian_noise -i 输入 -o 输出 -p sigma=0.1          # 单个退化
uv run degfw apply -c configs/example.yaml -i data/input -o outputs/run1   # 按配置串联多个退化
uv run pytest                       # 全部测试（含需要 GPU 和模型的，约 2 分钟）
uv run pytest -m "not slow"         # 只跑不需要模型的，不到 1 秒
```

不想装某个仓库的依赖时，`uv sync` 和 `uv run` 都加 `--no-group <组名>`（组名见 `third_party/README.md`；
只给 `uv sync` 加的话，下一次 `uv run` 会按默认把它装回来）。它的退化会在 `degfw list` 里标为不可用，测试自动跳过。

每张输出图旁边都会生成一个同名 `.json`，记录所用的退化、参数和随机种子。
处理文件夹时，每张图的种子由配置里的种子和这张图的相对路径算出：文件夹里增删别的图片，不会改变它的结果。
输出一律是 `.png`；同一个文件夹里主名相同的图片（如 `a.jpg` 和 `a.png`）输出为 `a.png` 和 `a_2.png`，不会互相覆盖。

界面（可选）：`uv sync --extra gui`，然后 `uv run degfw gui`。

## 图像约定

框架内部统一使用 `numpy.float32`、形状 `H x W x 3`、RGB、取值 `[0, 1]`。
如果开源代码使用 BGR / uint8 / torch tensor，在适配器里做转换。
读图时按 EXIF 方向标记转正（`core/io.py`），输出文件不带方向标记。
