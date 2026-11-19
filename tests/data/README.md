# tests/data

小的固定测试图片（输入 + 参考结果），回归测试用。

| 文件 | 内容 |
|---|---|
| `fog_scene.png` | 合成的 128×96 小场景（天空、楼房、地面） |
| `fog_scene_vis100.png` | 上图经 Clear2Fog（float32，能见度 100 m）的结果，由 `tests/degradations/test_fog.py` 对照 |

结果有意改变后重新生成参考图：`uv run python tests/degradations/test_fog.py`
