# My-Framework：图像退化生成框架

用统一接口封装各种图像退化（雾、镜头脏污、水滴……），可单张或批量处理，参数和随机种子全程可复现。
图形界面暂缓，等底层退化做好再接。

## 目录结构：什么东西放哪里

```
My-Framework/
├── third_party/                 ① 开源代码原样放这里，一个仓库一个文件夹
│   ├── README.md                   来源登记表 + 引入规则
│   ├── <雾的仓库名>/
│   └── <镜头脏污的仓库名>/
│
├── degradation_fw/              ② 你自己的框架代码
│   ├── core/                       框架核心，一般不用动
│   │   ├── base.py                   Degradation 基类（统一接口）
│   │   ├── params.py                 参数类型 Float / Int / Choice / Bool
│   │   ├── registry.py               注册表
│   │   ├── pipeline.py               多个退化串联、批量处理、保存元数据
│   │   ├── io.py                     图片读写、格式转换（支持中文路径）
│   │   └── paths.py                  项目路径；use_third_party() 导入开源代码
│   │
│   ├── degradations/               ③ 适配器：把开源代码包装成统一接口，按类别分
│   │   ├── _template.py              新退化照这个模板写
│   │   ├── weather/                  天气 / 大气
│   │   │   └── fog.py                  雾（待实现）
│   │   ├── lens/                     镜头污染
│   │   │   └── lens_dirt.py            脏污：不透明 + 水滴（待实现）
│   │   └── sensor/                   传感器 / 成像
│   │       └── gaussian_noise.py       高斯噪声（示例，验证框架用）
│   │
│   ├── gui/                        界面（暂缓；已有一个能跑的 Gradio 初版）
│   └── cli.py                      命令行入口
│
├── configs/                     ④ 参数预设（YAML），一次实验一个文件
├── scripts/                     ⑤ 自己的试验 / 一次性脚本
├── tests/                          测试：自动检查每个已注册的退化
├── data/                           输入图片（不提交到 git）
└── outputs/                        输出结果（不提交到 git）
```

| 你手上的东西 | 放哪里 |
|---|---|
| 下载的开源代码 | `third_party/<仓库名>/`，原样放，保留 LICENSE |
| 开源代码自带的纹理、mask、模型权重 | 跟着它留在 `third_party/<仓库名>/` 里 |
| 对开源代码的调整（格式转换、参数换算） | `degradation_fw/degradations/<类别>/xxx.py` 适配器里 |
| 必须直接改开源代码本身 | 在 `third_party/` 里改，单独提交，并在登记表里注明 |
| 跑实验、出对比图的脚本 | `scripts/` |
| 某次实验的参数组合 | `configs/xxx.yaml` |
| 测试图片 / 生成的数据集 | `data/`、`outputs/` |

## 添加一种退化（以雾为例）

1. 把开源代码原样复制到 `third_party/<仓库名>/`，在 `third_party/README.md` 登记来源，**单独提交一次**。
2. 照 `degradations/_template.py` 写 `degradations/weather/fog.py`。
3. 在 `degradations/__init__.py` 里取消 `from .weather import fog` 的注释。
4. 运行 `uv run pytest`，测试会自动检查它的输出格式和可复现性。

## 环境与使用

用 [uv](https://docs.astral.sh/uv/) 管理环境：

```bash
uv sync
uv run pytest
uv run degfw list
uv run degfw apply -c configs/example.yaml -i data/input -o outputs/run1
```

每张输出图旁边都会生成一个同名 `.json`，记录所用的退化、参数和随机种子。

界面（可选）：`uv sync --extra gui`，然后 `uv run degfw gui`。

## 图像约定

框架内部统一使用 `numpy.float32`、形状 `H x W x 3`、RGB、取值 `[0, 1]`。
如果开源代码使用 BGR / uint8 / torch tensor，在适配器里做转换。
