# 雾 `fog`（Clear2Fog）

代码：`degradation_fw/degradations/weather/fog.py`；第三方代码：`third_party/Clear2Fog/`（Depth Pro + 相机加雾）。

## 用法

和 Clear2Fog 的 `c2f.py` 一样，只需要输入、输出和能见度（米，越小雾越浓）：

```bash
uv run degfw fog -i 输入图片或文件夹 -o 输出文件夹 -v 100
```

- `-v` 可以给多个值，例如 `-v 25 50 100 250 500`：每张图只估算一次景深，每个能见度各出一张。
- 输出文件名同 `c2f.py`：`foggy_<原文件名>_vis_<能见度>.png`，直接放在输出文件夹里；另有 `fog_run.json` 记录参数。
  不同文件夹里有同名图片（或 `a.jpg` 和 `a.png` 这种同名不同扩展名）时，后面的加 `_2`、`_3`，不会覆盖前面的结果。
- 默认 float32，结果与原版 Clear2Fog **逐像素一致**（不带 EXIF 旋转标记的图片）。8 GB 显卡上 Depth Pro 显存不够，每张约 20 s；
  加 `--fp16` 后每张约 1 s，与原版每个像素最多差 2/255。
- 手机竖拍照片这类带 EXIF 旋转标记的图片，先按标记转正再加雾，输出也是转正的（原版 `c2f.py` 处理这类照片会失败或景深颠倒）。
- 第一次使用前下载 Depth Pro 权重（约 1.9 GB，不在 git 里）：`uv run degfw weights --download`。
- 和其他退化一样也可以用 `uv run degfw run fog -i 输入 -o 输出 -p visibility=50`，
  或在配置文件里：`- name: fog` + `params: {visibility: 50, fp16: true}`。两种方式用的是同一份雾的代码，
  同样的图、同样的能见度，结果逐像素相同（[决策 0010](../decisions/0010-context-one-fog-code.md)），区别见最后一节。

## 用 LiDAR 校正景深（`--lidar`）

如果同时有 LiDAR 点云和标定，加上 `--lidar 文件夹`，景深的尺度就由点云校正（[决策 0008](../decisions/0008-fog-lidar-depth-scale.md)）。
不加时和上面完全一样。

```bash
uv run degfw fog -i a9_dataset_r02_s03/images/s110_camera_basler_south2_8mm -o 输出文件夹 -v 100 --lidar a9_dataset_r02_s03
```

- **为什么需要：** Depth Pro 在高处俯拍的路侧相机上会把距离严重估小。
  在 TUMTraf A9 上，它的景深只有 LiDAR 实测的约 1/8，所以标称能见度 100 m 的雾，看起来只相当于约 800 m。
  它的相对结构是对的，错的主要是整体尺度。
- **怎么做：** 把这张图对应的点云投影到图上，尺度 = 中位数(LiDAR 景深 ÷ Depth Pro 景深)，景深 = Depth Pro × 尺度；
  之后的大气光和加雾不变。Depth Pro 给结构，LiDAR 给真实尺度。
- **`--lidar` 给什么：** 一个文件夹，里面（包括子文件夹）有 TUMTraf 的 OpenLABEL 标注（`.json`）和点云（`.pcd`），
  一般给数据集的根目录。图片和点云、标定的对应关系，以及标定本身，都从标注里读：
  标注里的 `image_file_names` 列出了和这一帧点云一起拍的图片。同一张图有几台 LiDAR，就把几台的点都用上。
- **退回：** 找不到这张图的点云、图里的点少于 50 个，或者标定对应的图像尺寸和图片不同时，这张图只用 Depth Pro，终端会写明原因。
- **记录：** 每张图在 `fog_run.json` 的 `depth` 里记下景深来源、尺度、用到的点数、校正后的残差，以及用到的标注和点云文件。
- **`degfw run fog`、配置文件也能用：** 参数 `lidar`，例如 `-p lidar=D:\data\a9_dataset_r02_s03`，
  或配置文件里 `params: {visibility: 100, lidar: "D:/data/a9_dataset_r02_s03"}`。文件夹不存在时，开始处理前就报错。
- **目前只认 TUMTraf 的标注格式：** 接别的数据集，要在 `degradation_fw/datasets/` 里再写一个读取器。

## 参数

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `visibility` | Int，5–2000 | 100 | 能见度（气象光学视程），米；越小雾越浓 |
| `fp16` | Bool | false | Depth Pro 用半精度：快约 20 倍，景深相差约 0.1 %（中位数），结果略有不同 |
| `lidar` | Folder | 空 | LiDAR 文件夹，同 `degfw fog --lidar`；空 = 只用 Depth Pro |

## 方法（与 Clear2Fog 相同）

1. Depth Pro 从单张图估算以米为单位的景深。给了 `--lidar` 时，再乘以由点云算出的尺度（见上一节）。
2. 大气光 L：暗通道先验，只在 ≥ 1000 m 的像素（天空）里找；亮度限制在 [162, 220] / 255，取灰色。
   没有天空的图用整批输入图（最多 100 张）的平均大气光，都没有天空时用 0.8。
3. Koschmieder 定律：t = exp(-β · 景深)，β = -ln(0.05) / 能见度；有雾图 = 原图 · t + L · (1 - t)。

调用顺序见 [architecture.md](../architecture.md) 第 3.2 节，输出的文件和 `fog_run.json` 的字段见第 4.3 节。

## 和直接运行 `c2f.py` 的差别

对不带 EXIF 方向标记的图片，下面这些都不改变结果（float32 逐像素一致，有回归测试 `tests/degradations/test_fog.py`）：

- 带方向标记的照片先转正，RGB 和景深来自同一份像素（[决策 0004](../decisions/0004-exif-orientation.md)）。
- 平均大气光只在遇到没有天空的图时才计算，抽样用固定种子（`c2f.py`：总是在开始时计算，抽样不固定）；输入不超过 100 张时就是全部图片，和 `c2f.py` 相同。
- 一次给多个能见度时，每张图的景深只算一次。
- 不经过 Clear2Fog 的 `src/fog_pipeline/__init__.py`，所以不需要它的 LiDAR 部分和 PyQt5。那部分是给点云本身加雾，和上面用 LiDAR 校正相机景深是两回事。
- 同名输入的输出名加 `_2`、`_3`（[决策 0005](../decisions/0005-output-name-collisions.md)）；`c2f.py` 会覆盖。

## `degfw fog` 和 `degfw run fog` 的区别

两者调用的是同一份雾的代码（`fog.py` 里的 `FogRun`）：焦距、景深、LiDAR 校正、大气光、加雾的每一步都一样，
同样的图、同样的能见度，结果逐像素相同（[决策 0010](../decisions/0010-context-one-fog-code.md)）。
`degfw run fog` 通过框架交给退化的来源信息（这张图的文件、这次运行的全部图片），得到和 `degfw fog` 一样的信息。区别只在用法和输出：

| | `degfw fog` | `degfw run fog` / 配置文件 / GUI |
|---|---|---|
| 能见度 | 一次可以给多个，每张图的景深只算一次 | 一次一个 |
| 读哪些图 | 文件夹本层的 .png .jpg .jpeg | 连子文件夹，格式更多（见 [architecture.md](../architecture.md) 4.1） |
| 输出 | `foggy_*_vis_*.png` + 整次运行一份 `fog_run.json` | 和其他退化一样：同名 `.png` + `.json`，雾的记录在 `.json` 里这一步的 `info` 下 |

- **整批平均大气光按各自读到的图算：** 输入文件夹里有子文件夹或其他格式的图时，两者读到的图不同，没有天空的图结果就可能不同。
- **内存里的单张图**（比如界面的预览、`get("fog")(图像)`）：没有文件，就没有 EXIF 焦距、找不到 LiDAR 点云，也没有别的图可以平均；
  没有天空时用 0.8。
