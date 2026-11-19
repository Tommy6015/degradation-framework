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
  或在 YAML 流程里：`- name: fog` + `params: {visibility: 50, fp16: true}`。

## 参数

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `visibility` | Int，5–2000 | 100 | 能见度（气象光学视程），米；越小雾越浓 |
| `fp16` | Bool | false | Depth Pro 用半精度：快约 20 倍，景深相差约 0.1 %（中位数），结果略有不同 |

## 方法（与 Clear2Fog 相同）

1. Depth Pro 从单张图估算以米为单位的景深。
2. 大气光 L：暗通道先验，只在 ≥ 1000 m 的像素（天空）里找；亮度限制在 [162, 220] / 255，取灰色。
   没有天空的图用整批输入图（最多 100 张）的平均大气光，都没有天空时用 0.8。
3. Koschmieder 定律：t = exp(-β · 景深)，β = -ln(0.05) / 能见度；有雾图 = 原图 · t + L · (1 - t)。

数据流图见 [architecture.md](../architecture.md) 第 3 节。

## 和直接运行 `c2f.py` 的差别

对不带 EXIF 方向标记的图片，下面这些都不改变结果（float32 逐像素一致，有回归测试 `tests/degradations/test_fog.py`）：

- 带方向标记的照片先转正，RGB 和景深来自同一份像素（[决策 0004](../decisions/0004-exif-orientation.md)）。
- 平均大气光只在遇到没有天空的图时才计算，抽样用固定种子（`c2f.py`：总是在开始时计算，抽样不固定）；输入不超过 100 张时就是全部图片，和 `c2f.py` 相同。
- 一次给多个能见度时，每张图的景深只算一次。
- 不经过 Clear2Fog 的 `src/fog_pipeline/__init__.py`，所以不需要它的 LiDAR 部分和 PyQt5。
- 同名输入的输出名加 `_2`、`_3`（[决策 0005](../decisions/0005-output-name-collisions.md)）；`c2f.py` 会覆盖。

## `degfw fog` 和 `degfw run fog` 的区别

| | `degfw fog` | `degfw run fog` / 配置文件 / GUI |
|---|---|---|
| 焦距 | 用文件 EXIF 里的焦距（有的话） | 由 Depth Pro 估算（框架的退化接口只拿到像素） |
| 没有天空的图 | 整批输入图的平均大气光 | 固定用 0.8 |
| 输出 | `foggy_*_vis_*.png` + `fog_run.json` | 和其他退化一样：同名 `.png` + `.json` |

所以带 EXIF 焦距的照片、或者没有天空的图，两种方式的结果可能不同。
