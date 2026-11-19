# camera_contamination_simulation：引入范围与本地修改

原作者仓库：https://github.com/timdietereberhardt/camera_contamination_simulation ，引入的版本 `8f19968`。
许可证 Apache-2.0；`noise.py` 为 MIT。本仓库里原样引入的提交是 `749d255`。
依赖组 `camera-contamination`（`pyproject.toml`）；模型权重见 `third_party/weights.yaml`。

## 引入范围

只引入了生成污染所需的文件：`contamination_simulation.py`、`gen_models/*.pth`（3 个模型，各约 34 MB）、
`LICENSE`、`README.md`、`usage_example.ipynb`；`noise.py` 是本地新增的。
训练（`training/`、`preprocessing/`）、UNet 检测实验（`unet_detection/`）和论文插图（`figs/`）没有引入，需要时去原作者仓库取。

## 本地修改

直接在这里修改，单独提交。在仓库根目录运行下面的命令查看：

```
git diff 749d255 -- third_party/camera_contamination_simulation ':!*LOCAL_CHANGES.md'   # 相对原版一共改了什么
git log --oneline -- third_party/camera_contamination_simulation                       # 每次改了什么
```

修改概要（写于 2026-11-19，之后的改动以 git log 为准）：

- 支持任意图片尺寸（原版强制缩放到 960×960）：新增 `image_to_model_xy`、`render_mask`、`to_rgb`。
- 水滴：一个 mask 里的多个水滴分别判断 ZoomIn / ZoomOut（`find_droplets`），被图像边缘截断的水滴按完整大小判断，
  桶形畸变从整张图取样、不再在水滴里留下暗斑，很小的区域不再出错。
- 新增 `noise.py`：纯 Python 实现的 `pnoise2`，替代在 Windows 上难以安装的 C 扩展包 `noise`；
  文件开头附有 `noise` 包（© 2008 Casey Duncan）的 MIT 许可声明原文。

注意：模型权重是在 GPU 上保存的，按原样只能在有 CUDA 的机器上加载。

这些修改也推到过 fork（https://github.com/Tommy6015/camera_contamination_simulation 的
`any-image-size-and-droplet-fixes` 分支，`04c5c2f`，文件和这里相同）。那个 fork 以后不再维护，只作存档。

## 移出去的

运行脚本 `reproduce_examples.py` 是自己写的工具，不属于上游代码，已移到 `scripts/contamination_examples.py`，
选项说明见 `scripts/README.md`。移动前的历史：`git log --follow scripts/contamination_examples.py`。
