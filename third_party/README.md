# third_party

这里存放原样引入的开源代码。规则：

1. **原样复制**，保留原项目的 `LICENSE` 文件，然后单独提交一次，例如：
   `vendor: add <名字> from <URL>@<commit>`
2. 尽量**不改**这里的代码，格式转换、参数换算等放在 `degradation_fw/degradations/` 的适配器里。
3. 必须修改时，修改**单独提交**，并在下表"本地修改"一栏简要说明，方便日后对照上游。
4. 引入前确认许可证。GPL 类许可证对整个项目的发布方式有约束。

## 来源登记

| 目录 | 用途 | 来源 URL | Commit / 版本 | 许可证 | 本地修改 |
|------|------|----------|---------------|--------|----------|
| `camera_contamination_simulation/` | 镜头污染：不透明污渍、半透明污渍、水滴 | https://github.com/Tommy6015/camera_contamination_simulation （自己的 fork） | `8f19968` | Apache-2.0 | 见下 |

### camera_contamination_simulation

只引入了生成污染所需的文件：`contamination_simulation.py`、`gen_models/*.pth`（3 个模型，各约 34 MB）、
`LICENSE`、`README.md`、`usage_example.ipynb`。训练（`training/`、`preprocessing/`）、
UNet 检测实验（`unet_detection/`）和论文插图（`figs/`）没有引入，需要时去原仓库取。

本地修改：

- 支持任意图片尺寸（原版强制缩放到 960×960）：新增 `image_to_model_xy`、`render_mask`、`to_rgb`；水滴部分重写较多（`find_droplets`、`barrel_distortion` 等）。
- 新增 `noise.py`：纯 Python 实现的 `pnoise2`，替代在 Windows 上难以安装的 C 扩展包 `noise`。移植自 `noise` 1.2.2 的 C 源码（© 2008 Casey Duncan，MIT 许可证）。
- 新增 `reproduce_examples.py`：固定随机种子、批量处理的运行脚本，可作为参数参考。
- `torch.load` 加 `map_location`，没有 GPU 时也能加载模型。
