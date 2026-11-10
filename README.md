# My-Framework：图像退化生成框架

用统一接口封装各种图像退化（雾、镜头脏污、水滴……），通过图形界面点选退化类型和强度，一键处理单张图片或整个文件夹。

## 环境

使用 [uv](https://docs.astral.sh/uv/) 管理环境：

```bash
uv sync
```

## 使用

图形界面（浏览器打开 http://127.0.0.1:7860）：

```bash
uv run degfw gui
```

命令行批量处理：

```bash
uv run degfw list
uv run degfw apply -c configs/example.yaml -i data/input -o outputs/run1
```

每张输出图旁边都会生成一个同名 `.json`，记录所用的退化、参数和随机种子，可完全复现。

## 目录结构

```
third_party/           原样引入的开源代码（各自保留 LICENSE，见 third_party/README.md）
degradation_fw/
  params.py            参数类型定义（Float / Int / Choice / Bool），GUI 据此自动生成控件
  base.py              Degradation 基类：所有退化的统一接口
  registry.py          注册表
  pipeline.py          多个退化串联 + 批量处理 + 保存元数据
  io.py                图片读写（支持中文路径）
  degradations/        每种退化一个适配器文件
  gui/app.py           Gradio 界面
  cli.py               命令行入口
configs/               参数预设
tests/
```

## 添加一种新的退化

1. 把开源代码原样复制到 `third_party/<名字>/`，在 `third_party/README.md` 登记来源，**单独提交一次**。
2. 复制 `degradation_fw/degradations/_template.py` 为新文件，实现 `apply()`。
3. 在 `degradation_fw/degradations/__init__.py` 里 import 它。

GUI 和命令行会自动出现这个新退化，不需要改其它地方。

## 图像约定

框架内部统一使用 `numpy.float32`、形状 `H x W x 3`、RGB、取值 `[0, 1]`。
如果开源代码使用 BGR / uint8 / torch tensor，在适配器里做转换。
