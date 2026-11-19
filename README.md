# degradation-framework：图像退化生成框架

用统一接口封装各种图像退化（雾、镜头脏污、水滴……），可单张或批量处理，参数和随机种子全程可复现。
图形界面暂缓，等底层退化做好再接。

仓库名用全称 `degradation-framework`；代码里用简写：Python 包名 `degradation_fw`（`import degradation_fw`），命令行命令 `degfw`。

这是一个**工作区**：在仓库里用 `uv run` 运行，不是可以 `pip install` 到别处的库
（代码按源码位置找 `third_party/`，打成 wheel 单独安装后找不到）。

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
| 必须直接改开源代码本身 | 在 `third_party/` 里改，单独提交，写进它的 `LOCAL_CHANGES.md`；改动大的提交到 fork 后重新引入 |
| 自己写的、用开源代码的脚本或工具 | `scripts/`（不放进 `third_party/`） |
| 某次实验的参数组合 | `configs/xxx.yaml` |
| 测试用的小图、参考结果 | `tests/data/` |
| 输入图片 / 生成的数据集 | `data/`、`outputs/` |

## 加雾（Clear2Fog）

和 Clear2Fog 的 `c2f.py` 一样，只需要输入、输出和能见度（米，越小雾越浓）：

```bash
uv run degfw fog -i 输入图片或文件夹 -o 输出文件夹 -v 100
```

- `-v` 可以给多个值，例如 `-v 25 50 100 250 500`：每张图只估算一次景深，每个能见度各出一张。
- 输出文件名同 `c2f.py`：`foggy_<原文件名>_vis_<能见度>.png`，直接放在输出文件夹里；另有 `fog_run.json` 记录参数。
- 默认 float32，结果与原版 Clear2Fog **逐像素一致**（不带 EXIF 旋转标记的图片）。8 GB 显卡上 Depth Pro 显存不够，每张约 20 s；
  加 `--fp16` 后每张约 1 s，与原版每个像素最多差 2/255。
- 手机竖拍照片这类带 EXIF 旋转标记的图片，先按标记转正再加雾，输出也是转正的（原版 `c2f.py` 处理这类照片会失败或景深颠倒）。
- 第一次使用前下载 Depth Pro 权重（约 1.9 GB，不在 git 里）：`uv run degfw weights --download`。
- 和其他退化一样也可以用 `uv run degfw run fog -i 输入 -o 输出 -p visibility=50`，
  或在 YAML 流程里：`- name: fog` + `params: {visibility: 50, fp16: true}`。

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
uv run pytest                       # 全部测试（含需要 GPU 和模型的，约 1.5 分钟）
uv run pytest -m "not slow"         # 只跑不需要模型的，不到 1 秒
```

不想装某个仓库的依赖时，`uv sync` 和 `uv run` 都加 `--no-group <组名>`（组名见 `third_party/README.md`；
只给 `uv sync` 加的话，下一次 `uv run` 会按默认把它装回来）。它的退化会在 `degfw list` 里标为不可用，测试自动跳过。

每张输出图旁边都会生成一个同名 `.json`，记录所用的退化、参数和随机种子。

界面（可选）：`uv sync --extra gui`，然后 `uv run degfw gui`。

## 图像约定

框架内部统一使用 `numpy.float32`、形状 `H x W x 3`、RGB、取值 `[0, 1]`。
如果开源代码使用 BGR / uint8 / torch tensor，在适配器里做转换。
读图时按 EXIF 方向标记转正（`core/io.py`），输出文件不带方向标记。
