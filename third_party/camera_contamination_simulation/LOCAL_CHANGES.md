# camera_contamination_simulation：引入范围与本地修改

来源：自己的 fork https://github.com/Tommy6015/camera_contamination_simulation ，分支 `any-image-size-and-droplet-fixes` @ `04c5c2f`，
基于原作者仓库 https://github.com/timdietereberhardt/camera_contamination_simulation 的 `8f19968`。Apache-2.0；`noise.py` 为 MIT。
登记表见 `third_party/README.md`；依赖组 `camera-contamination`（`pyproject.toml`）；模型权重见 `third_party/weights.yaml`。

## 引入范围

只引入了生成污染所需的文件：`contamination_simulation.py`、`noise.py`、`gen_models/*.pth`（3 个模型，各约 34 MB）、
`LICENSE`、`README.md`、`usage_example.ipynb`，与 fork 的 `04c5c2f` 逐字节相同。
训练（`training/`、`preprocessing/`）、UNet 检测实验（`unet_detection/`）、论文插图（`figs/`），以及 fork 的
`.gitignore`、`requirements.txt` 没有引入，需要时去 fork 取。

## 本地修改

**无**：这里的文件是 fork `04c5c2f` 的原样拷贝。

对原作者代码的修改都在 fork 里（相对原作者的 `8f19968`）。在 fork 的克隆里查看：
`git log 8f19968..04c5c2f`、`git diff 8f19968 04c5c2f`。

- `8ac2e7e` 新增 `noise.py`：纯 Python 实现的 `pnoise2`，替代在 Windows 上难以安装的 C 扩展包 `noise`；`requirements.txt` 不再列出 `noise`。
- `93906b4` 支持任意图片尺寸（原版强制缩放到 960×960）：新增 `image_to_model_xy`、`render_mask`、`to_rgb`。
  水滴部分的修正：一个 mask 里的多个水滴分别判断 ZoomIn / ZoomOut（`find_droplets`），被图像边缘截断的水滴按完整大小判断，
  桶形畸变从整张图取样、不再在水滴里留下暗斑，很小的区域不再出错。
- `04c5c2f` `noise.py` 开头附上 `noise` 包（© 2008 Casey Duncan）的 MIT 许可声明原文。
- `c048632` fork 的 `.gitignore` 忽略 `__pycache__/`（这个文件没有引入）。

以后要改这部分代码：在 fork 里改、提交、push，再按新 commit 重新引入，并更新这里和登记表里的 commit 号。

注意：模型权重是在 GPU 上保存的，按原样只能在有 CUDA 的机器上加载。

## 移出去的

运行脚本 `reproduce_examples.py` 是自己写的工具，不属于上游代码，已移到 `scripts/contamination_examples.py`，
选项说明见 `scripts/README.md`。移动前的历史：`git log --follow scripts/contamination_examples.py`。
