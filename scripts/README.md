# scripts

自己的试验 / 一次性脚本放这里，不属于框架本身。例如：

- 单独跑通某个开源代码、对比修改前后的效果
- 批量生成某次实验用的数据集
- 画参数强度对比图

脚本里用框架：

```python
from degradation_fw import Pipeline, Step, get
from degradation_fw.core.io import load_image, save_image
```

运行：`uv run python scripts/xxx.py`
