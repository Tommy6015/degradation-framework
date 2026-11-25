# 命令行用法与注意事项

这里收齐了在命令行里测试各功能用的命令，以及每个命令要注意的地方。
命令都是 Windows PowerShell（VS Code 的终端）的写法，在仓库根目录运行。
各退化的方法细节见 [degradations/](degradations/)；污染脚本的全部选项见 [scripts/README.md](../scripts/README.md)，或运行时加 `--help`。

> 镜头污染（水滴、不透明污渍、半透明污渍）还没接入框架，目前用 `scripts/contamination_examples.py` 单独运行。
> 等它接入框架（M4），第 5 节的命令会变。

## 1. 准备：进入仓库，设置路径

每次打开新的终端，先运行这一段。后面的命令都用这里的三个变量：

```powershell
cd "D:\Laptops\Documents\GitHub\degradation-framework"
$src = "D:\TUBS\Masterarbeit\Phase 2\Demo\Input"     # 输入图片文件夹
$out = "D:\TUBS\Masterarbeit\Phase 2\Demo\Output"    # 输出的总文件夹
$tag = "261123_01"                                   # 这次试验的编号，每次换一个，就不会覆盖上一次的结果
```

- **变量只在当前终端里有效：** 新开一个终端，要重新运行这一段。
- **路径里有空格要加引号：** 比如 `Phase 2`。设置变量时已经加了引号，后面直接写 `$src` 就行；
  拼出来的路径要整个放在双引号里，如 `"$out\Fog\$tag"`。
- **运行时再输入的写法：** 下面每种退化都给了"运行时再输入"的版本。`Read-Host` 会在终端里提示你输入，回车后才运行。

## 2. 命令一览

| 命令 | 做什么 |
|---|---|
| `uv run degfw list` | 列出所有退化和它们的参数，以及在这台机器上能不能运行；缺依赖或缺权重时显示 `UNAVAILABLE` 和原因 |
| `uv run degfw weights` | 查看模型权重在不在；`--verify` 校验 SHA-256，`--download` 下载缺的权重 |
| `uv run degfw run <名字>` | 运行单个退化，不用配置文件，参数用 `-p` 给 |
| `uv run degfw apply -c <配置>` | 按配置文件串联多个退化 |
| `uv run degfw fog` | 雾的专门命令，用法同原版 `c2f.py`；有 LiDAR 点云时可加 `--lidar` 校正景深 |
| `uv run degfw gui` | 图形界面（要先运行 `uv sync --extra gui`） |
| `uv run python scripts/contamination_examples.py` | 镜头污染：水滴、不透明污渍、半透明污渍 |
| `uv run pytest` | 运行测试 |

## 3. 通用命令

```powershell
uv run degfw list
uv run degfw weights                  # 加 --verify 校验 SHA-256，加 --download 下载缺的权重

# 单个退化（不用配置文件）；结果和 degfw fog 相同，输出按框架的格式（见下面的"输出"）
uv run degfw run fog -i $src -o "$out\Fog_run\$tag" -p visibility=50 fp16=true
uv run degfw run fog -i $src -o "$out\Fog_run\$tag" -p visibility=50 fp16=true "lidar=$src\a9_dataset_r02_s03_Demo"   # 加 LiDAR

# 按配置文件串联多个退化
uv run degfw apply -c configs/example.yaml -i $src -o "$out\Apply\$tag"

# 测试
uv run pytest -m "not slow"           # 只跑不需要模型的，不到 1 秒
uv run pytest                         # 全部，约 4 分钟，需要 GPU 和模型
```

注意：
- **参数：** `-p` 后面可以写多个 `键=值`。值按 YAML 解析，所以 `50`、`0.1`、`true` 会分别变成整数、小数和布尔值。
  每个退化有哪些参数，用 `degfw list` 查看。
- **种子：**
  - `degfw run` 用 `--seed N` 指定种子，默认是 0。
  - `degfw apply` 用配置文件里的种子，`--seed N` 可以临时覆盖它。
  - 处理文件夹时，每张图的种子由这个种子和图片的相对路径算出。所以文件夹里增删别的图片，不会改变这张图的结果。
- **子文件夹：** `run` 和 `apply` 会处理所有子文件夹里的图，输出时保留子文件夹的结构。
- **输出：**
  - 输出一律是 `.png`；
  - 每张图旁边有一个同名的 `.json`，记下来源、退化、参数和种子；
  - 输出文件夹里另有一份 `pipeline.yaml`。
- **同名图片：** 同一个文件夹里主名相同的图片（如 `a.jpg` 和 `a.png`），输出为 `a.png` 和 `a_2.png`，不会互相覆盖。
- **手机竖拍的照片：** 读图时按 EXIF 方向转正，输出的图片不带方向标记。
- **`degfw run fog` 和 `degfw fog` 用的是同一份雾的代码：** 同样的图、同样的能见度，结果逐像素相同，
  LiDAR、没有天空时的整批平均大气光也都一样（[决策 0010](decisions/0010-context-one-fog-code.md)）。区别只在用法和输出：
  `degfw fog` 一次可以给多个能见度，输出 `foggy_*.png` 和 `fog_run.json`；`degfw run fog` 一次一个能见度，
  输出和其他退化一样，雾的记录（景深、大气光从哪来）在每张图 `.json` 的 `info` 里。
  另外 `degfw run` 会进子文件夹，`degfw fog` 不进。
- **界面：** 没装 gradio 时，`degfw gui` 只会提示 `GUI not installed. Run: uv sync --extra gui`。

## 4. 雾：`degfw fog`

固定写法：

```powershell
# 一个能见度（米）
uv run degfw fog -i $src -o "$out\Fog\$tag" -v 100

# 多个能见度，每个各出一张图；加 --fp16 快很多
uv run degfw fog -i $src -o "$out\Fog\$tag" -v 50 200 --fp16
```

运行时再输入能见度（可以输入多个，用空格隔开）：

```powershell
$v = (Read-Host "能见度（米，可输入多个，空格分隔）") -split '\s+'
uv run degfw fog -i $src -o "$out\Fog\$tag" -v $v
```

有 LiDAR 点云时（TUMTraf 数据集），加 `--lidar`，用点云校正景深的尺度：

```powershell
# Demo：图片、点云、标注都在同一个文件夹
uv run degfw fog -i "$src\a9_dataset_r02_s03_Demo" -o "$out\Fog_lidar\$tag" -v 100 --fp16 --lidar "$src\a9_dataset_r02_s03_Demo"

# 完整数据集：-i 给一台相机的图片文件夹，--lidar 给数据集根目录
uv run degfw fog -i "$src\a9_dataset_r02_s03\images\s110_camera_basler_south2_8mm" -o "$out\Fog_lidar\$tag" -v 100 --fp16 --lidar "$src\a9_dataset_r02_s03"
```

注意：
- **强度：**
  - `-v` 是能见度，单位是米，只能是整数，数值越小雾越浓。不写 `-v` 时默认是 100。
  - 参考：25 很浓，50 浓，100 中等，250 较淡，500 很淡。
- **`--fp16`：** 让 Depth Pro（估算景深的模型）用半精度计算。
  - **为什么快：** 用 float32 时，Depth Pro 运行要占将近 8 GB 显存，8 GB 的显卡装不下，超出的部分放到内存里，每张图约 20 秒。
    用 float16 只占约 3.7 GB，全部放在显存里，每张图约 1 秒。
  - **代价：** 和原版相比，每个像素最多差 2/255，肉眼看不出来。只有不加 `--fp16`（float32）时，结果才和原版逐像素一致。
  - **建议：** 试验和预览时加 `--fp16`。正式生成数据集时定下一种精度，全程不要混用。
    用的是哪种精度，记在 `fog_run.json` 的 `depth_pro_precision` 里。
- **只读第一层：** 只处理输入文件夹本层的 `.png`、`.jpg`、`.jpeg`，不进子文件夹。`-i` 后面可以写多个文件或文件夹。
- **输出：**
  - 输出文件夹会自动创建；
  - 结果命名为 `foggy_<原文件名>_vis_<能见度>.png`，另有一个 `fog_run.json` 记下这次的参数；
  - 主名相同的图片会改名，如 `foggy_<名字>_2_vis_100.png`，终端里会打印出来。
- **没有天空（终端打印 `no sky`）：**
  - **为什么要天空：** 雾的颜色和亮度（大气光）是从天空估出来的：景深 ≥ 1000 米的像素算作天空。
    图里没有这样的像素，就没法从这张图自己估出大气光。
  - **现在怎么处理：** `degfw fog` 用同一批输入里有天空的图的平均大气光，最多抽 100 张来算；整批都没有天空时用 0.8，约等于 204/255 的灰。
    平均值，以及它是用几张图算出来的，记在 `fog_run.json` 里。
  - **要小心：** 同一张没有天空的图放进不同的批次，雾的颜色可能不同；序列里也可能逐帧跳变。
    正式生成数据集前要解决这个问题，见 [roadmap 的"要决定的事"第 3 条](roadmap.md#要决定的事)。
- **`--lidar`（用点云校正景深）：**
  - **为什么要用：** 只用 Depth Pro 时，路侧相机上的景深被估小约 8 倍，雾比标称能见度弱很多：标称 100 m，看起来约 800 m。
    有点云就加上，详见 [degradations/fog.md](degradations/fog.md) 和[决策 0008](decisions/0008-fog-lidar-depth-scale.md)。
  - **开头一行** `LiDAR: ... 5 of 5 input image(s) listed`：输入的图里有几张在标注里找到了对应的点云。
  - **每张图一行** `LiDAR: depth x 8.18 from 4829 points, error 2.3%`：景深乘了多少、用了多少个点、校正后的误差。
    显示 `LiDAR not used: 原因 -> Depth Pro only` 时，这张图只用了 Depth Pro。
  - **`degfw run fog`、配置文件也能用：** 参数 `lidar`，如 `-p "lidar=$src\a9_dataset_r02_s03_Demo"`；文件夹不存在时，开始处理前就报错。
  - **时间：** 每张图约 2 秒（加 `--fp16`）。完整数据集一台相机有 1033 张，全部跑完要半个多小时。
- 方法和参数的细节见 [degradations/fog.md](degradations/fog.md)。

## 5. 镜头污染：`scripts/contamination_examples.py`

### 5.1 三种污染共同的规则

- **一块污渍用 `X Y SIZE` 表示：**
  - **X：** 水平位置，0 是最左，1 是最右；
  - **Y：** 垂直位置，0 是最上，1 是最下；
  - **SIZE：** 大小，按图像长边的比例算，0.15 偏小，0.5 已经很大；
  - **范围：** X、Y 要在 0 到 1 之间，SIZE 要大于 0、不超过 1。超出范围时脚本会报错，说明哪里错了，不会生成图。
- **位置：水滴是精确的，另外两种只是参考：**
  - **水滴：** 网络只负责画形状，画好后把整团水滴平移，使它的质心正好落在 (X, Y)。
    裂成几块时几块一起平移，保持原来的形状（[决策 0009](decisions/0009-droplet-exact-placement.md)）。
    实测偏差不超过 1 像素；以前由网络决定位置时，平均偏离长边的 4% 到 20%。
  - **不透明和半透明污渍：** X、Y 仍只是交给网络的参考，实际位置会有偏差。
- **多块污渍：** 同一个选项重复写，比如 `--droplet 0.2 0.3 0.2 --droplet 0.7 0.6 0.15`，所有污渍都画在同一张结果图上。
  三种污染也可以写在同一条命令里。
- **给了哪种就只跑哪种：**
  - 只写选项、不带数字（如只写 `--droplet`）时，用这种污染的默认位置；
  - 一个选项都不写时，三种污染都按默认位置跑一遍。
  - 所以下面"运行时再输入"的命令里，`if (-not ...)` 那一行不要删：什么都没输入时，它保证只跑这一种污染。
- **SIZE 只是"大概的大小"：** 污渍的形状由生成网络画出来，网络并不保证画出的大小等于 SIZE。
  对水滴的实测（每个 SIZE 换 10 个种子）：
  - SIZE 在 0.1 到 0.3 之间最稳定，实际大小约为名义大小（SIZE × 长边）的 0.8 倍，但不同种子之间能差 2 到 3 倍；
  - SIZE ≤ 0.1 时，有的种子一个水滴都不生成；
  - SIZE ≥ 0.4 时，一个位置会裂成 2 到 4 个水滴；到 0.6 直接盖满整张图。
  - 不透明污渍和半透明污渍用的也是这类网络，同样有这种随机性。
  - 水滴的位置已经精确了（见上一条），大小还没有；下一步打算同样由我们精确指定。
- **种子：**
  - `--seed N` 固定形状，默认是 0，所有图都用同一个种子，所以形状相同；
  - `--seed random` 让每张图随机抽一个种子；
  - 实际用的种子都写进 `seed.json`，之后用 `--seed N` 就能复现；
  - 种子只改变形状（以及水滴裂成几块、变形等），位置和大小只由 `X Y SIZE` 决定。
    水滴的形状只取决于 SIZE 和随机数，不再随位置变化。
- **其他选项：**
  - `--recursive`：连子文件夹里的图一起处理；
  - `--save-input`：同时保存一份原图 `input.png`；
  - `--square`：回到以前的做法，先裁成正方形，再缩放到 960×960（水滴是 966×966）。
- **输入格式：** `.png`、`.jpg`、`.jpeg`、`.bmp`、`.tif`、`.tiff`、`.webp`。`--image` 后面可以写多个文件或文件夹。
- **输出：**
  - 只有一张输入图时，结果直接放在 `--out` 里；
  - 多张图时，每张图一个子文件夹 `--out\<图片名>\`，`--out` 里另有一份汇总的 `seeds.json`；
  - 每种污染一张结果图，加上对应的 `_mask.png`（污染区域），另有 `overview.png`（对比图）和 `seed.json`（种子和污渍位置）。
- **需要 NVIDIA 显卡：** 三个模型的权重是在 GPU 上保存的，只能在有 CUDA 的机器上加载。
- **参数是按约 960 像素的图调的：** 模糊程度、相机焦距（380 像素）这些像素参数，是按 960 像素左右的图定的。
  图像分辨率差很多时（比如 1920×1200），边缘会显得更清晰或更模糊，水滴"放大型 / 缩小型"的判断也会不同。

### 5.2 水滴：`--droplet`

固定写法：

```powershell
# 一个水滴
uv run python scripts/contamination_examples.py --droplet 0.3 0.4 0.3 --image $src --out "$out\Droplet_testing\$tag"

# 两个水滴，画在同一张图上
uv run python scripts/contamination_examples.py --droplet 0.2 0.3 0.2 --droplet 0.7 0.6 0.15 --image $src --out "$out\Droplet_testing\$tag"

# 原来的做法：位置只作网络的参考（对比用）
uv run python scripts/contamination_examples.py --droplet 0.3 0.4 0.3 --droplet-placement network --image $src --out "$out\Droplet_testing\$tag"
```

运行时再输入，写法一：一次输入，多个水滴用分号隔开。

```powershell
$line  = Read-Host "水滴 X Y SIZE，多个用分号隔开（如 0.3 0.4 0.2; 0.7 0.6 0.15）"
$drops = foreach ($d in ($line -split ';')) { if ($d.Trim()) { "--droplet"; $d.Trim() -split '\s+' } }
if (-not $drops) { $drops = @("--droplet") }
uv run python scripts/contamination_examples.py $drops --image $src --out "$out\Droplet_testing\$tag"
```

运行时再输入，写法二：一个一个输入，直接回车结束。

```powershell
$drops = @()
while ($true) {
    $d = Read-Host "水滴 X Y SIZE（直接回车结束）"
    if ([string]::IsNullOrWhiteSpace($d)) { break }
    $drops += "--droplet"; $drops += $d.Trim() -split '\s+'
}
if (-not $drops) { $drops = @("--droplet") }
uv run python scripts/contamination_examples.py $drops --image $src --out "$out\Droplet_testing\$tag"
```

- **默认位置：** 只写 `--droplet` 时是 `0.3 0.4 0.5`。按 5.1 的实测，SIZE 0.5 容易裂成几块；想要单个水滴，SIZE 用 0.1 到 0.3。
- **精确放置：** 水滴的质心正好落在 X Y。
  - **放在边缘：** X、Y 可以取 0 或 1，水滴放在图像边缘，超出的部分被裁掉；放大型 / 缩小型仍按水滴的完整大小判断。
  - **SIZE 很小时会重试：** 网络一个水滴都没画出来时（SIZE ≤ 0.1 时会出现），会再调用一次网络，最多 20 次，终端会提示用了第几次。
    随机数是接着往下取的，所以结果仍然可复现。20 次都没有就报错，这张图不生成。
  - **碰到网络画布的边缘：** SIZE 很大时，形状可能被网络的画布截断，终端会提示。
  - **原来的做法：** 加 `--droplet-placement network` 时，X Y 只作网络的参考，结果和改动前逐像素一致，可以用来对比。
- **输出：** `droplet.png`（结果）和 `droplet_mask.png`（所有水滴合在一起的区域）。
  `seed.json` 里的 `droplet_placement` 记下用的是哪种放置方式（`exact` / `network`）；
  `droplet_placements` 里每块水滴记下实际质心（像素）、平移量、网络调用的次数，以及是否碰到网络画布的边缘。

### 5.3 不透明污渍：`--opaque`

固定写法：

```powershell
uv run python scripts/contamination_examples.py --opaque 0.5 0.5 0.3 --image $src --out "$out\Opaque_testing\$tag"
```

运行时再输入，多块污渍用分号隔开：

```powershell
$line  = Read-Host "污渍 X Y SIZE [颜色]，多块用分号隔开（如 0.3 0.5 0.2; 0.7 0.4 0.15 90 70 50）"
$spots = foreach ($s in ($line -split ';')) { if ($s.Trim()) { "--opaque"; $s.Trim() -split '\s+' } }
if (-not $spots) { $spots = @("--opaque") }
uv run python scripts/contamination_examples.py $spots --image $src --out "$out\Opaque_testing\$tag"
```

每块污渍的写法：
- **`X Y SIZE`：** 用默认颜色（见下表）。只写 `--opaque` 时，用默认位置 `0.5 0.5 0.3`。
- **`X Y SIZE R G B`：** 这块污渍用指定的纯色，RGB 是 0 到 255 的整数。
- **`X Y SIZE R1 G1 B1 R2 G2 B2`：** 这块污渍用渐变色，从边缘色 R1 G1 B1 过渡到中心色 R2 G2 B2。

不想一块块写颜色，也可以统一指定颜色。下面这些选项加在命令末尾，每种颜色出一张图，形状都相同：
- **`--opaque-color 90 70 50`：** 纯色，可以重复写多个颜色；
- **`--opaque-gradient 139 90 43 0 0 0`：** 渐变色（边缘色 → 中心色），也可以重复写；
- **`--opaque-gamma 2`：** 调整渐变的分布。大于 1 时边缘色更多，小于 1 时中心色更多，默认是 0.5。
- 只写这几个选项、不写 `--opaque` 时，也会在默认位置生成不透明污渍。

颜色和输出文件的关系：

| 情况 | 输出 |
|---|---|
| 所有污渍都不带颜色，也没给 `--opaque-color` / `--opaque-gradient` | 两张：`opaque_black.png`（纯黑），`opaque_brown.png`（从棕色 139 90 43 渐变到黑）。两张形状相同，只有颜色不同 |
| 给了 `--opaque-color` / `--opaque-gradient` | 每种颜色一张，如 `opaque_90_70_50.png`、`opaque_139_90_43_to_0_0_0.png` |
| 每块污渍都带自己的颜色 | 只出一张 `opaque.png` |
| 有的带颜色、有的不带 | 带颜色的保持自己的颜色；不带的按默认颜色（或给定的颜色），每种颜色各出一张 |

### 5.4 半透明污渍：`--semi`

固定写法：

```powershell
uv run python scripts/contamination_examples.py --semi 0.5 0.6 0.4 --semi-scale 50 --image $src --out "$out\Semi_testing\$tag"
```

运行时再输入。会依次问三项：污渍（多块用分号隔开）、颜色、噪声尺度；后两项直接回车就用默认值。

```powershell
$line  = Read-Host "污渍 X Y SIZE [强度]，多块用分号隔开（如 0.5 0.6 0.4; 0.2 0.3 0.3 0.5）"
$color = Read-Host "颜色 R G B（直接回车 = 默认沙色 194 178 128）"
$scale = Read-Host "噪声尺度，可以多个（直接回车 = 默认 10 和 1000）"
$a = foreach ($s in ($line -split ';')) { if ($s.Trim()) { "--semi"; $s.Trim() -split '\s+' } }
if (-not $a) { $a = @("--semi") }
if ($color.Trim()) { $a += "--semi-color"; $a += $color.Trim() -split '\s+' }
if ($scale.Trim()) { $a += "--semi-scale"; $a += $scale.Trim() -split '\s+' }
uv run python scripts/contamination_examples.py $a --image $src --out "$out\Semi_testing\$tag"
```

各项设置：
- **每块污渍：** 写 `X Y SIZE`，或者 `X Y SIZE 强度`。
  - 位置和大小的含义见 5.1。
  - 第 4 个数是这块污渍自己的强度，0 到 1：1 是原版强度，0.5 是一半，0 是看不见。
  - 只写 `--semi` 时，用默认位置 `0.8 0.6 0.8`。只写下面这几个选项、不写 `--semi` 时，也会在默认位置生成半透明污渍。
- **`--semi-color R G B`：** 污渍的颜色，默认是沙色 194 178 128。
  原版脚本用的是灰色，想得到和原版一样的效果，用 `--semi-color 125 125 125`。
- **`--semi-opacity`：** 统一的强度，0 到 1，默认是 1。没写第 4 个数的污渍都按这个强度。
- **`--semi-scale`：** 噪声尺度，决定污渍是细碎的颗粒还是成片的斑块：数值小是细颗粒，数值大是大斑块。
  可以给多个，每个出一张图，文件名如 `semi_scale50.png`。不写时默认 10 和 1000 各一张。
- **怎么混合：** 每个像素的结果 = 原图 × (1 − a) + 颜色 × a，其中 a = 强度 × 形状 mask × 噪声纹理。

要注意三点：
- **很慢：** 噪声是逐个像素用纯 Python 算的，而且每块污渍、每个噪声尺度都要把整张图的噪声算一遍。
  所以图越大、污渍越多、尺度越多，就越慢；1920×1200 这类大图可能要等不少时间。建议先只给一个尺度试，比如 `--semi-scale 50`。
- **噪声纹理和种子无关：** 图像尺寸相同、尺度相同时，纹理完全一样。种子只改变污渍的外形。
- **浅色不明显：** 就算强度是 1，平均也只盖住约 30%（形状和噪声都小于 1）。在亮的画面上，浅色污渍不太看得出来，
  可以换深一点的颜色，或者让污渍大一些。

## 6. 出错时先看这里

| 现象 | 原因和处理 |
|---|---|
| `degfw list` 里某个退化显示 `UNAVAILABLE` | 后面写了原因：缺 Python 包就运行 `uv sync`；缺权重就运行 `uv run degfw weights --download` |
| 污染脚本提示 `no images found` | 图片格式不支持（支持的格式见 5.1），或者图在子文件夹里、忘了加 `--recursive` |
| 污染脚本提示 `x and y must be in 0..1, size in (0, 1]` 之类 | 数值超出范围，按提示改；这时不会生成任何图 |
| 污染脚本提示 `the network drew no droplet in 20 attempts` | 水滴的 SIZE 太小，网络画不出来；把 SIZE 调大。这张图不生成，其他图照常处理 |
| `degfw gui` 提示 `GUI not installed` | 先运行 `uv sync --extra gui` |
| 雾跑得很慢（每张约 20 秒） | 没加 `--fp16`，见第 4 节 |
| 加了 `--lidar`，提示 `No TUMTraf (OpenLABEL) label files with LiDAR frames found` | 给的文件夹里（包括子文件夹）没有 TUMTraf 的标注文件。检查路径，一般给数据集的根目录 |
