# 0001：第三方代码只复制需要的文件到 `third_party/`，只在这里维护

- 状态：已采纳
- 日期：2026-11-12（引入方式）；2026-11-19 修订（不再维护 fork）
- 相关：`third_party/README.md`；原样引入的提交 `749d255`（camera_contamination_simulation）、`d9ba087`（Clear2Fog）；修订提交 `929270d`

## 背景

各种退化效果来自研究代码（Clear2Fog、camera_contamination_simulation 等）。这些仓库：

- 很大，包含训练代码、实验、论文插图，而生成退化只需要其中几个文件；
- 往往不能直接导入（引用了不存在的模块、连带导入 LiDAR 部分和 PyQt5）；
- 需要小改才能用（例如只支持 960×960、依赖在 Windows 上装不上的 C 扩展）；
- 原作者几乎不再更新（camera_contamination_simulation 总共两次提交）。

## 决定

- 只把需要的文件复制到 `third_party/<仓库名>/`，保留 LICENSE。第一次原样复制**单独提交**，作为以后和原版对比的基准。
- 要改第三方代码就直接在 `third_party/` 里改，单独提交，提交说明以 `third_party/<仓库名>:` 开头。
  和原版的差别用 `git diff <原样引入的提交> -- third_party/<仓库名>` 查看，不另外手写记录。
- 不维护 fork。在 `third_party/README.md` 登记原作者仓库、引入的版本和原样引入的提交。

## 考虑过的方案

- **git submodule / subtree**：会带进整个仓库（训练、实验、插图都进来）；submodule 还要求克隆时加 `--recursive`，日常操作更绕。
- **pip 安装原仓库**：这些研究代码大多不是可安装的包，而且需要修改。
- **直接引用本机已有的克隆**（不复制进来）：项目会依赖仓库外的文件夹，换电脑或给别人用就跑不起来，也不记录用的是哪个版本。
- **在 fork 里改、push，再复制回来**（2026-11-19 试过一次）：每次改动都要在两个仓库之间同步、更新登记的 commit 号。
  单人开发、代码只在本项目里用时，得不偿失。改动推到过 fork 的
  `any-image-size-and-droplet-fixes` 分支，作为存档保留。

## 影响

- degradation-framework 是自给自足的：克隆下来就有全部代码，不需要访问 fork 或原作者仓库。
- 原作者以后有更新时要手动合并：把新版本复制进来之前，先用原样引入的提交看清自己改了什么。
- 本机的 fork 克隆和 GitHub 上的 fork 不再需要，留作参考或删除都可以。
