# doc：开发过程文档

根目录的 `README.md` 只讲整个项目：是什么、目录怎么分、怎么装环境、怎么开发。
开发管理用的文档和各部分的细节放在这里。

英文版在 [`doc_EN/`](../doc_EN/README.md)，目录结构和文件名一一对应。**以本目录（中文）为准**：
改了这里的文件，同步更新 `doc_EN/` 里同名的文件。

| 文档 | 写什么 | 什么时候更新 |
|---|---|---|
| [requirements.md](requirements.md) | 从论文任务书拆出的需求：编号、出自哪项子任务、怎么验收、现在的状态 | 需求变化、某条需求的状态改变时 |
| [roadmap.md](roadmap.md) | 论文主线、**论文项目总体架构图**（从数据来源到论文的 5 个阶段）、里程碑、要决定的事 | 里程碑完成、计划改变时 |
| [architecture.md](architecture.md) | **本仓库内部**的架构：分层包图、核心类图、运行时时序图、输入与输出、贯穿各模块的约定 | 增删模块、依赖关系、调用顺序或输出格式改变时 |
| [decisions/](decisions/README.md) | 关键决策记录：一个决定一个文件，写清背景、决定、放弃了哪些方案、影响 | 做出（或推翻）一个关键决定时新建一份 |
| [status/](status/) | 每周状态：一周一个文件，如 `2026-W47.md`；包括本周开发的功能的评判标准和核对结果 | 这一周里随时更新；每周一照 `status/template.md` 新建一份 |
| [degradations/](degradations/) | 每种退化的详细用法、方法和注意事项 | 改了它的参数、命令或行为时 |
| [commands.md](commands.md) | 在命令行里测试各功能用的命令（PowerShell，含运行时再输入的写法）和注意事项 | 增删命令、选项、默认值或输出文件改变时 |

约定：

- 图用 [Mermaid](https://mermaid.js.org/) 写在 Markdown 里（VS Code 装了 Mermaid 扩展可以预览，GitHub 上直接显示）。画图时：
  - 框里只写名字，一行几个字；详细说明写在图下面的表格里。中文长句放在框里，预览时会被截断或折行。
  - 文件名这类中间不能断开的长词，每段控制在 12 个字符以内，更长的在 `/` 或 `_` 处用 `<br/>` 手动换行，
    否则预览会在词的中间折开（如 `lens_dirt.p / y`）。
  - 流程图（`flowchart`）和类图（`classDiagram`）第一行照 `architecture.md` 里的写法加 `%%{init: ...}%%`，关掉 `htmlLabels`：
    文字由 Mermaid 自己排版，大小不受预览样式影响。
- 每个功能开发前，先在当周的 status 文件里列出评判标准；完成后在同一张表里逐条写上结果和依据。
  跨周的功能，表留在开始的那一周，之后几周的 status 里链接过去。
- 周的编号用 ISO 周（周一开始）：`uv run python -c "import datetime; print(datetime.date.today().isocalendar())"`。
- 文档里提到代码、提交、决策时写上文件名、提交号或决策编号，方便查回去。
