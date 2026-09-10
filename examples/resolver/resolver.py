"""文档解析器：按契约清点仓库，用命名找到一件文档。

契约层 contract.py 说「应该有什么、叫什么、落在哪」；
目录层 catalog.py 说「实际有什么、哪条名字指向哪件」；
本文件只做入口：查询、列目录、对账。

用法：
  python3 resolver.py 材料        按名查找（认文件名与篇内标题）
  python3 resolver.py 案例 --show 查找并打印内容
  python3 resolver.py --list      列出全部目录条目
  python3 resolver.py --check     对账：契约有而目录无、目录有而契约无
  python3 resolver.py 日志 --root <其他第二大脑>   换一个工作区扫描
"""

import sys
from pathlib import Path

import catalog as catalog_layer
import contract


def repo_root(start: Path | None = None) -> Path:
    d = (start or Path(__file__)).resolve().parent
    while not (d / "data" / "journal").is_dir():
        if d == d.parent:
            raise FileNotFoundError("未找到 quanttide-work 仓库根")
        d = d.parent
    return d


def check(root: Path) -> int:
    missing = contract.missing(root)
    unregistered = catalog_layer.build(root).unregistered(root)
    for asset in missing:
        print(f"缺资产：{asset.kind}（{asset.name}）")
    for path in unregistered:
        print(f"未登记：{path.relative_to(root)}")
    if not missing and not unregistered:
        print("对账通过：二十格齐备，无未登记目录。")
    return 1 if (missing or unregistered) else 0


def main(argv):
    if "--root" in argv:
        at = argv.index("--root")
        root = Path(argv[at + 1]).resolve()
        argv = argv[:at] + argv[at + 2 :]
    else:
        root = repo_root()
    if len(argv) > 1 and argv[1] == "--check":
        return check(root)

    catalog = catalog_layer.build(root)
    if len(argv) < 2 or argv[1] == "--list":
        for entry in catalog.entries:
            print(f"[{entry.kind}] {entry.path.relative_to(root)}  {'／'.join(sorted(entry.names))}")
        return 0

    query = argv[1]
    matches = catalog.find(query)
    if not matches:
        print(f"未找到：{query}")
        return 1
    for entry in matches:
        print(f"[{entry.kind}] {entry.path.relative_to(root)}")
        if "--show" in argv[2:]:
            if entry.path.is_dir():
                print("  （目录）" + "、".join(sorted(p.name for p in entry.path.iterdir() if not p.name.startswith("."))))
            else:
                print(entry.path.read_text(encoding="utf-8").rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
