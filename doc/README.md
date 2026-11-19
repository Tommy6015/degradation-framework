# doc：开发过程文档

根目录的 `README.md` 只讲整个项目：是什么、目录怎么分、怎么装环境、怎么开发。
开发管理用的文档和各部分的细节放在这里。

| 文档 | 写什么 | 什么时候更新 |
|---|---|---|
| [roadmap.md](roadmap.md) | 目标、里程碑（已完成 / 进行中 / 计划）、下一步要做和要决定的事 | 里程碑完成、计划改变时 |
| [architecture.md](architecture.md) | 系统架构：模块依赖图、数据流图、贯穿各模块的约定 | 增删模块、模块之间的依赖或数据流改变时 |
| [decisions/](decisions/README.md) | 关键决策记录：一个决定一个文件，写清背景、决定、放弃了哪些方案、影响 | 做出（或推翻）一个关键决定时新建一份 |
| [status/](status/) | 每周状态：一周一个文件，如 `2026-W47.md` | 这一周里随时更新；每周一照 `status/template.md` 新建一份 |
| [degradations/](degradations/) | 每种退化的详细用法、方法和注意事项 | 改了它的参数、命令或行为时 |

约定：

- 图用 [Mermaid](https://mermaid.js.org/) 写在 Markdown 里（VS Code 装了 Mermaid 扩展可以预览，GitHub 上直接显示）。
- 周的编号用 ISO 周（周一开始）：`uv run python -c "import datetime; print(datetime.date.today().isocalendar())"`。
- 文档里提到代码、提交、决策时写上文件名、提交号或决策编号，方便查回去。
