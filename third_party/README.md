# third_party

这里放引入的开源代码，一个仓库一个文件夹。第三方代码**只在这里维护**：要改就直接在这里改，不另外维护 fork。
自己写的脚本和工具不放这里，放 `scripts/` 或适配器里。

## 规则

1. **原样复制**，保留原项目的 `LICENSE` 文件，然后单独提交一次，例如：
   `vendor: add <名字>@<commit> (original)`。这次提交就是以后和原版对比的基准。
2. 尽量**不改**这里的代码，格式转换、参数换算等放在 `degradation_fw/degradations/` 的适配器里。
3. 必须修改时，直接在这里改，**单独提交**，提交说明以 `third_party/<仓库名>:` 开头。
   和原版相比改了什么用 git 查看（命令见各仓库的 `LOCAL_CHANGES.md`），不用另外手写记录。
4. 引入前确认许可证。GPL 类许可证对整个项目的发布方式有约束。
5. **依赖**：每个仓库在 `pyproject.toml` 里有一个 dependency group（组名见下表），删除或升级仓库时整组处理。
6. **模型权重**：每个文件在 [`weights.yaml`](weights.yaml) 里登记一条（路径、大小、SHA-256、下载地址）。
   查看状态 `uv run degfw weights`，校验 `--verify`，下载缺的 `--download`。
7. **加载**：适配器只通过 `degradation_fw/core/paths.py` 的函数加载这里的代码，并且只在用到时加载
   （写法见 `degradation_fw/degradations/_template.py`）。

## 来源登记

| 目录 | 用途 | 原作者仓库 | 引入的版本 | 原样引入的提交 | 许可证 | 依赖组 | 本地修改 |
|------|------|------------|------------|----------------|--------|--------|----------|
| `camera_contamination_simulation/` | 镜头污染：不透明污渍、半透明污渍、水滴 | https://github.com/timdietereberhardt/camera_contamination_simulation | `8f19968` | `749d255` | Apache-2.0；`noise.py` 为 MIT（Casey Duncan） | `camera-contamination` | 有：任意图片尺寸、水滴修正、纯 Python 的 `noise.py`，见 [LOCAL_CHANGES.md](camera_contamination_simulation/LOCAL_CHANGES.md) |
| `Clear2Fog/` | 雾：按能见度（米）给照片加雾，单目景深 Depth Pro + 大气散射模型 | https://github.com/mmohamed28/Clear2Fog | `9097f4a` | `d9ba087` | MIT；Depth Pro 见 `LICENSES/DEPTH_PRO` | `clear2fog` | 有：`__init__.py` 注释掉 3 行导入，见 [LOCAL_CHANGES.md](Clear2Fog/LOCAL_CHANGES.md) |

"引入的版本"是原作者仓库里的 commit；"原样引入的提交"是本仓库里那次原样复制的提交，和原版对比以它为准。
