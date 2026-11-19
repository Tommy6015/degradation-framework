# camera_contamination_simulation：引入范围与本地修改

来源：https://github.com/Tommy6015/camera_contamination_simulation （自己的 fork）@ `8f19968`，Apache-2.0。
登记表见 `third_party/README.md`；依赖组 `camera-contamination`（`pyproject.toml`）；模型权重见 `third_party/weights.yaml`。

## 引入范围

只引入了生成污染所需的文件：`contamination_simulation.py`、`gen_models/*.pth`（3 个模型，各约 34 MB）、
`LICENSE`、`README.md`、`usage_example.ipynb`。训练（`training/`、`preprocessing/`）、
UNet 检测实验（`unet_detection/`）和论文插图（`figs/`）没有引入，需要时去原仓库取。

## 对原代码的修改

- 支持任意图片尺寸（原版强制缩放到 960×960）：新增 `image_to_model_xy`、`render_mask`、`to_rgb`；水滴部分重写较多（`find_droplets`、`barrel_distortion` 等）。
- 新增 `noise.py`：纯 Python 实现的 `pnoise2`，替代在 Windows 上难以安装的 C 扩展包 `noise`。移植自 `noise` 1.2.2 的 C 源码（© 2008 Casey Duncan，MIT 许可证）。

这两处改动较大，计划提交到自己的 fork，再按新 commit 重新引入（见 `third_party/README.md` 规则 3）。

注意：模型权重是在 GPU 上保存的，按原样只能在有 CUDA 的机器上加载。

## 移出去的

运行脚本 `reproduce_examples.py` 是自己写的工具，不属于上游代码，已移到 `scripts/contamination_examples.py`，
选项说明见 `scripts/README.md`。移动前的历史：`git log --follow scripts/contamination_examples.py`。
