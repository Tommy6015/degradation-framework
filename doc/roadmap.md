# 路线图

**目标**：用统一接口封装各种图像退化（雾、镜头污染……），可单张或批量处理，参数和随机种子全程可复现，用来生成退化数据集。
图形界面放在最后。

系统现在怎么搭的见 [architecture.md](architecture.md)，做过的关键决定见 [decisions/](decisions/README.md)，每周进展见 [status/](status/)。

## 里程碑

| | 里程碑 | 内容 | 状态 |
|---|---|---|---|
| M0 | 框架骨架 | `core/`（基类、参数、注册表、流程、读写）、命令行、通用测试、Gradio 初版 | ✅ 2026-11-12 |
| M1 | 雾 | Clear2Fog 适配器和 `degfw fog`；float32 与原版逐像素一致，`--fp16` 快约 20 倍 | ✅ 2026-11-19 |
| M2 | 工程结构 | 第三方代码约定（加载、依赖组、权重清单）、`degfw run` / `degfw weights`、测试拆分和回归测试；修复 EXIF 方向、批量种子、同名覆盖 | ✅ 2026-11-19 |
| M3 | 镜头污染 | `lens/lens_dirt.py`：不透明污渍、半透明污渍、水滴接入框架 | ⏳ 下一步 |
| M4 | 更多退化 | 见下面的候选 | 计划中 |
| M5 | 图形界面 | 在 Gradio 初版上完善 | 暂缓 |

## M3 镜头污染：开始前要决定的事

污染代码已经引入（`third_party/camera_contamination_simulation`），可以用 `scripts/contamination_examples.py` 单独运行，
但还没有接入框架。现在的退化接口满足不了它的两个需求，要先定方案，写成决策记录：

1. **输出 mask**：污染需要同时输出 mask，而 `Degradation.apply` 只能返回一张图。
2. **非数值参数**：污渍的位置（可能有好几处，每处 x、y、大小）和 RGB 颜色不是单个数值，而现有参数类型只有 Float、Int、Choice、Bool。

## M4 候选（尚未评估）

本机 GitHub 文件夹里还有这几个和退化相关的仓库，要不要引入待评估：

- `Rain-Generation-Python`（从名字看是雨）
- `fog_simulation-SFSU_synthetic`（另一种合成雾的方法）
- `physical_lens_soiling`（镜头脏污的物理模型）

## 可选的工程改进

- **CI**：快速测试不需要 GPU 和第三方依赖，可以在 GitHub Actions 上只装核心依赖来跑。
- **拆分 `weather/fog.py`**：它现在约 280 行，再加功能时拆成子包（模型封装 / 注册的退化 / 命令行）。
- **雾的示例配置**：`configs/` 里加一个。
