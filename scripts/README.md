# scripts

自己的试验 / 一次性脚本和工具放这里，不属于框架本身。例如：

- 单独跑通某个开源代码、对比修改前后的效果
- 批量生成某次实验用的数据集
- 画参数强度对比图

脚本里用框架：

```python
from degradation_fw import Pipeline, Step, get
from degradation_fw.core.io import load_image, save_image
```

用 third_party 里的代码时，和适配器一样通过 `degradation_fw.core.paths` 加载、按 `degradation_fw.core.weights.weight_path()` 找模型，
这样脚本在哪个目录下运行都可以。

运行（在仓库根目录）：`uv run python scripts/xxx.py`

## contamination_examples.py：镜头污染

用 `third_party/camera_contamination_simulation` 的三种生成器（不透明污渍、半透明污渍、水滴）处理一张或多张图片，
固定随机种子、批量处理，可作为参数参考。原来是 `third_party/camera_contamination_simulation/reproduce_examples.py`，
因为是自己写的工具而移到这里（结果和移动前完全相同）。所有选项和示例见脚本开头的说明，或 `--help`。

```bash
uv run python scripts/contamination_examples.py --image IMG.jpg --out OUT
```

功能演变（原记录在 third_party 登记表里）：

- 加了 `--seed random`：每张图随机抽种子，实际用的种子写进 `seed.json` / `seeds.json`，可用 `--seed N` 复现。
- 把写死的位置/大小改成命令行指定：`--opaque / --semi / --droplet X Y SIZE`，可重复多次，
  同类污渍全部叠加在一张结果图上；去掉了 `--only`（给了哪种就跑哪种）；位置也记进 `seed.json`。
  默认位置在脚本开头的 `DEFAULT_SPOTS`：只写 `--droplet` 不带数字用默认位置；一个都不写则三种都按默认跑。
- 原图副本 `input.png` 默认不再保存，需要时加 `--save-input`。
- 不透明污渍的颜色改为命令行指定：`--opaque-color R G B`（纯色）、`--opaque-gradient R1 G1 B1 R2 G2 B2`
  （边缘色→中心色）、`--opaque-gamma`，均可重复，每种颜色一张结果；不给则仍是原来的黑色 + 棕黑渐变。
  单块污渍也可以自带颜色：`--opaque X Y SIZE R G B` 或 `--opaque X Y SIZE R1 G1 B1 R2 G2 B2`，
  多块不同颜色叠在同一张图上；每块都带颜色时只出一张 `opaque.png`。
- 半透明污渍加了 `--semi-color R G B`（颜色，默认沙色 194 178 128；原脚本是灰色 125 125 125）、`--semi-opacity`（强度 0..1，默认 1 = 原样）、
  `--semi-scale`（噪声尺度，默认 10 和 1000 各一张）；单块可写 `--semi X Y SIZE OPACITY` 自带强度。
  透明度在脚本里按比例混合实现，没有改 `contamination_simulation.py`。默认颜色改成了沙色，想得到原来的灰色结果用 `--semi-color 125 125 125`。
- 移到 `scripts/`：第三方代码通过 `use_third_party()` 加载，模型按 `third_party/weights.yaml` 找，不再要求在第三方目录下运行。
- 水滴精确放置（[决策 0009](../doc/decisions/0009-droplet-exact-placement.md)）：网络只负责形状（总在正中央生成），再把整团水滴平移，使质心正好落在 `--droplet X Y`，裂成几块时一起平移；没画出水滴时重试，最多 20 次。
  用 `DropletGenerator` 的子类 `PlacedDropletGenerator` 实现，没有改 `third_party/`；平移的计算在 `degradation_fw/degradations/lens/placement.py`。
  `--droplet-placement network` 回到原来的做法（结果和改动前逐像素一致）；`seed.json` 记下每块水滴的实际质心、平移量和网络调用次数。
