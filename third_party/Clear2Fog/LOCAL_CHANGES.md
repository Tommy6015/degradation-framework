# Clear2Fog：引入范围与本地修改

来源：https://github.com/Tommy6015/Clear2Fog （自己的 fork，上游 https://github.com/mmohamed28/Clear2Fog）@ `9097f4a`，
MIT；Depth Pro 见 `LICENSES/DEPTH_PRO`。登记表见 `third_party/README.md`；依赖组 `clear2fog`（`pyproject.toml`）。

## 引入范围

只引入了相机加雾所需的文件：`src/fog_pipeline/simulate_fog/camera/`（大气散射模型 + 大气光估计）、
`src/fog_pipeline/depth_map/`（Depth Pro 单目景深）、`src/fog_pipeline/__init__.py`、`c2f.py`（原始命令行入口，仅作参考，
缺少 LiDAR 部分不能直接运行）、`LICENSE`、`LICENSES/`、`README.md`。
LiDAR 加雾（`simulate_fog/lidar/`，依赖 PyQt5）、Waymo 工具（`src/utils/`、`src/waymo_protos/`、`extract_frames_waymo.py`）
和论文实验（`experimental_analysis/`）没有引入，需要时去原仓库取。

模型权重 `depth_pro.pt`（约 1.9 GB）**不在 git 里**，登记在 `third_party/weights.yaml`（`depth_pro`）。
`uv run degfw weights --download` 会下载并校验，放到代码要找的位置
`src/fog_pipeline/depth_map/depth_pro/checkpoints/depth_pro.pt`（原下载说明见同目录 `depth_pro.txt`）。

## 对原代码的修改

- `src/fog_pipeline/__init__.py`：注释掉三行导入（`ImageEnhancer`、`OCS`、`authenticity`），这些模块在上游仓库里不存在，原版无法导入。

框架的适配器 `degradation_fw/degradations/weather/fog.py` 不经过这个 `__init__.py`：它用
`import_third_party_package("Clear2Fog", "src/fog_pipeline")` 把这个包以私有名字 `_tp_clear2fog` 加载，
只导入相机加雾和 Depth Pro 模块（不连带导入 LiDAR 部分和 PyQt5，也不占用 `src` 这个通用包名）。
