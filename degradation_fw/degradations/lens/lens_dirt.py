"""镜头脏污 (lens dirt: opaque stains + water drops) — 待实现。

做法：
  1. 把开源代码原样放到 third_party/<repo名>/，在 third_party/README.md 登记，单独提交。
  2. 照 degradations/_template.py 在本文件写适配器。
     不透明污渍和水滴共用一套代码的话，可以写成一个退化，用 Choice 参数选类型；
     差别大的话也可以拆成 lens_dirt.py + water_drop.py 两个文件。
  3. 在 degradations/__init__.py 里取消 `from .lens import lens_dirt` 的注释。
"""
