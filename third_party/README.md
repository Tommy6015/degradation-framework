# third_party

这里只放原样引入的开源代码（加上必要的小补丁）。自己写的脚本和工具不放这里，放 `scripts/` 或适配器里。

## 规则

1. **原样复制**，保留原项目的 `LICENSE` 文件，然后单独提交一次，例如：
   `vendor: add <名字> from <URL>@<commit>`
2. 尽量**不改**这里的代码，格式转换、参数换算等放在 `degradation_fw/degradations/` 的适配器里。
3. 必须修改时，修改**单独提交**，并写进该仓库目录下的 `LOCAL_CHANGES.md`，方便日后对照上游。
   改动大的，先提交到自己的 fork，再按新 commit 重新引入。
4. 引入前确认许可证。GPL 类许可证对整个项目的发布方式有约束。
5. **依赖**：每个仓库在 `pyproject.toml` 里有一个 dependency group（组名见下表），删除或升级仓库时整组处理。
6. **模型权重**：每个文件在 [`weights.yaml`](weights.yaml) 里登记一条（路径、大小、SHA-256、下载地址）。
   查看状态 `uv run degfw weights`，校验 `--verify`，下载缺的 `--download`。
7. **加载**：适配器只通过 `degradation_fw/core/paths.py` 的函数加载这里的代码，并且只在用到时加载
   （写法见 `degradation_fw/degradations/_template.py`）。

## 来源登记

| 目录 | 用途 | 来源 URL | Commit / 版本 | 许可证 | 依赖组 | 本地修改 |
|------|------|----------|---------------|--------|--------|----------|
| `camera_contamination_simulation/` | 镜头污染：不透明污渍、半透明污渍、水滴 | https://github.com/Tommy6015/camera_contamination_simulation （自己的 fork，原作者 https://github.com/timdietereberhardt/camera_contamination_simulation） | `04c5c2f`（fork 分支 `any-image-size-and-droplet-fixes`，基于原作者的 `8f19968`） | Apache-2.0；`noise.py` 为 MIT（Casey Duncan） | `camera-contamination` | 无；对原作者代码的修改（任意图片尺寸、水滴修正、纯 Python 的 `noise.py`）都在 fork 里，见 [LOCAL_CHANGES.md](camera_contamination_simulation/LOCAL_CHANGES.md) |
| `Clear2Fog/` | 雾：按能见度（米）给照片加雾，单目景深 Depth Pro + 大气散射模型 | https://github.com/Tommy6015/Clear2Fog （自己的 fork，上游 https://github.com/mmohamed28/Clear2Fog） | `9097f4a` | MIT；Depth Pro 见 `LICENSES/DEPTH_PRO` | `clear2fog` | `__init__.py` 注释掉 3 行导入，见 [LOCAL_CHANGES.md](Clear2Fog/LOCAL_CHANGES.md) |
