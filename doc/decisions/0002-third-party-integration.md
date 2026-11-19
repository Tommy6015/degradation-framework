# 0002：第三方代码的加载、依赖和模型权重约定

- 状态：已采纳
- 日期：2026-11-19
- 相关：`core/paths.py`、`core/weights.py`、`core/base.py`、`third_party/weights.yaml`、`pyproject.toml`、`degradations/_template.py`；
  提交 `8b22d21`、`b71c292`

## 背景

接入两个第三方仓库之后出现了几个问题：

- 两个仓库用了两套接入办法：在 `sys.modules` 里伪造一个叫 `src` 的包加上临时 `chdir`，以及往 `sys.path` 里加目录。
  `src`、`noise`、`utils` 这类模块名在整个进程里共享，仓库一多就会撞名。
- 所有依赖都在一个列表里，看不出哪个包属于哪个仓库。
- 模型权重有的在 git 里，有的要手动下载、放在第三方目录深处，没有统一记录。
- 任何一个适配器在导入时出错，`degfw list`、GUI 和全部测试都会跟着失败。

## 决定

- **加载**：只通过 `core/paths.py` 加载第三方代码。
  - `import_third_party_package(repo, package)`：用于模块之间相对导入的包，以私有名字 `_tp_<仓库名>` 加载，不运行包自己的 `__init__.py`。
  - `use_third_party(repo, modules)`：用于按顶层名字互相导入的代码，要求声明它带来的模块名，名字已被占用就报错。
  - `working_dir(path)`：用于按相对路径打开文件的代码，加锁执行。
- **懒加载**：适配器文件开头不加载第三方代码和重依赖，只在第一次用到时加载。
- **声明需要什么**：`requires_modules`、`requires_weights`。缺了的退化只标为不可用（`degfw list` 写明原因），测试自动跳过。
- **依赖**：每个第三方仓库在 `pyproject.toml` 里一个 dependency group，默认全部安装（`default-groups = "all"`）。
- **权重**：每个文件在 `third_party/weights.yaml` 登记路径、大小、SHA-256、下载地址；`degfw weights` 查看、校验、下载。

## 考虑过的方案

- **每个适配器自己处理**：这就是原来的状态，已经出现两套不同的办法。
- **用 optional-dependencies（extras）分组**：extras 会写进包的元数据，是给可安装的库用的；这里是工作区，用 dependency groups 更合适，而且可以设为默认全装。
- **权重下载做成 `scripts/` 里的脚本**：下载权重属于框架本身的功能，所以做成 `degfw weights` 命令。

## 影响

- 接入新仓库的步骤固定下来，写在 `degradations/_template.py`。
- 只装核心依赖（不装 torch 等）时，框架和快速测试照样能运行（已验证：31 个测试通过，fog 标为不可用）。
- 结果没有变：fog 在 float32 和 fp16 下、两种用法的输出都与改动前逐像素相同。
