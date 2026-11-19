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
| `Clear2Fog/` | 雾：按能见度（米）给照片加雾，单目景深 Depth Pro + 大气散射模型 | https://github.com/Tommy6015/Clear2Fog （自己的 fork，上游 https://github.com/mmohamed28/Clear2Fog） | `9097f4a` | MIT；Depth Pro 见 `LICENSES/DEPTH_PRO` | 见下 |

### camera_contamination_simulation

只引入了生成污染所需的文件：`contamination_simulation.py`、`gen_models/*.pth`（3 个模型，各约 34 MB）、
`LICENSE`、`README.md`、`usage_example.ipynb`。训练（`training/`、`preprocessing/`）、
UNet 检测实验（`unet_detection/`）和论文插图（`figs/`）没有引入，需要时去原仓库取。

本地修改：

- 支持任意图片尺寸（原版强制缩放到 960×960）：新增 `image_to_model_xy`、`render_mask`、`to_rgb`；水滴部分重写较多（`find_droplets`、`barrel_distortion` 等）。
- 新增 `noise.py`：纯 Python 实现的 `pnoise2`，替代在 Windows 上难以安装的 C 扩展包 `noise`。移植自 `noise` 1.2.2 的 C 源码（© 2008 Casey Duncan，MIT 许可证）。
- 新增 `reproduce_examples.py`：固定随机种子、批量处理的运行脚本，可作为参数参考。
  之后加了 `--seed random`：每张图随机抽种子，实际用的种子写进 `seed.json` / `seeds.json`，可用 `--seed N` 复现。
  又把写死的位置/大小改成命令行指定：`--opaque / --semi / --droplet X Y SIZE`，可重复多次，
  同类污渍全部叠加在一张结果图上；去掉了 `--only`（给了哪种就跑哪种）；位置也记进 `seed.json`。
  默认位置在脚本开头的 `DEFAULT_SPOTS`：只写 `--droplet` 不带数字用默认位置；一个都不写则三种都按默认跑。
  原图副本 `input.png` 默认不再保存，需要时加 `--save-input`。
  不透明污渍的颜色改为命令行指定：`--opaque-color R G B`（纯色）、`--opaque-gradient R1 G1 B1 R2 G2 B2`
  （边缘色→中心色）、`--opaque-gamma`，均可重复，每种颜色一张结果；不给则仍是原来的黑色 + 棕黑渐变。
  单块污渍也可以自带颜色：`--opaque X Y SIZE R G B` 或 `--opaque X Y SIZE R1 G1 B1 R2 G2 B2`，
  多块不同颜色叠在同一张图上；每块都带颜色时只出一张 `opaque.png`。
  半透明污渍加了 `--semi-color R G B`（颜色，默认沙色 194 178 128；原脚本是灰色 125 125 125）、`--semi-opacity`（强度 0..1，默认 1 = 原样）、
  `--semi-scale`（噪声尺度，默认 10 和 1000 各一张）；单块可写 `--semi X Y SIZE OPACITY` 自带强度。
  透明度在脚本里按比例混合实现，没有改 `contamination_simulation.py`。默认颜色改成了沙色，想得到原来的灰色结果用 `--semi-color 125 125 125`。

注意：模型权重是在 GPU 上保存的，按原样只能在有 CUDA 的机器上加载。

### Clear2Fog

只引入了相机加雾所需的文件：`src/fog_pipeline/simulate_fog/camera/`（大气散射模型 + 大气光估计）、
`src/fog_pipeline/depth_map/`（Depth Pro 单目景深）、`src/fog_pipeline/__init__.py`、`c2f.py`（原始命令行入口，仅作参考，
缺少 LiDAR 部分不能直接运行）、`LICENSE`、`LICENSES/`、`README.md`。
LiDAR 加雾（`simulate_fog/lidar/`，依赖 PyQt5）、Waymo 工具（`src/utils/`、`src/waymo_protos/`、`extract_frames_waymo.py`）
和论文实验（`experimental_analysis/`）没有引入，需要时去原仓库取。

模型权重 `depth_pro.pt`（约 1.9 GB）**不在 git 里**（`.gitignore` 忽略 `*.pt`），需手动放到
`Clear2Fog/src/fog_pipeline/depth_map/depth_pro/checkpoints/depth_pro.pt`，下载地址见同目录 `depth_pro.txt`：
https://ml-site.cdn-apple.com/models/depth-pro/depth_pro.pt

本地修改：

- `src/fog_pipeline/__init__.py`：注释掉三行导入（`ImageEnhancer`、`OCS`、`authenticity`），这些模块在上游仓库里不存在，原版无法导入。
  框架的适配器不经过这个 `__init__.py`，只直接导入相机加雾和 Depth Pro 模块（避免连带导入 LiDAR 部分和 PyQt5）。
