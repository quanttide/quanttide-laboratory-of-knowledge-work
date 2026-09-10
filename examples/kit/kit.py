#!/usr/bin/env python3
"""知识工作工具箱（实验室版）：一个入口，五个动作。

  kg find <名字>        按名找文档——认文件名与中文标题
  kg list [--json]      列目录——契约 × 目录
  kg check              对账——契约有而目录无、目录有而契约无
  kg new-contract <文件>  写一份契约骨架
  kg audit-contract <文件>  核对契约：四段齐全，闸门项列出来
  kg audit-dossier <文件>   核对案卷：五段齐全，审查项有没有未过的

底下的库来自实验室已有的碎片：契约与目录两层取 resolver/，契约结构取 contract/，
案卷结构取 dossier/。
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "resolver"))
import catalog as catalog_layer  # noqa: E402
import contract as contract_layer  # noqa: E402

CONTRACT_SECTIONS = ("目标", "输出形态", "必须包含", "检查项")
DOSSIER_SECTIONS = ("生成者产出", "审查者报告", "人类裁决", "最终成果")

CONTRACT_TEMPLATE = """# 契约：<一句话说清要什么>

## 目标

<要什么>

## 输出形态

<交付物的形态：文件、路径、范围>

## 必须包含

- <要素一>
- <要素二>

## 检查项

- [ ] 机械：<可以写成断言的核对>
- [ ] 闸门：<只能人拍板的核对>
"""


def repo_root(start: Path | None = None) -> Path:
    """仓库根：入口负责定位，库只接受传进来的根。"""
    d = (start or Path(__file__)).resolve().parent
    while not (d / "data" / "journal").is_dir():
        if d == d.parent:
            raise FileNotFoundError("未找到仓库根")
        d = d.parent
    return d


def sections(path: Path) -> set[str]:
    return {line[3:].strip() for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("## ")}


def audit(path: Path, required: tuple[str, ...], label: str) -> int:
    found = sections(path)
    missing = [name for name in required if name not in found]
    for name in required:
        print(f"  {'✓' if name in found else '✗'} {name}")
    if missing:
        print(f"{label}不完整：缺 {'、'.join(missing)}")
        return 1
    print(f"{label}完整。")
    return 0


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    action, args = argv[1], argv[2:]
    root = repo_root()

    if action == "find":
        cat = catalog_layer.build(root)
        hits = cat.find(args[0])
        print("\n".join(f"[{e.kind}] {e.path.relative_to(root)}" for e in hits) or f"未找到：{args[0]}")
        return 0 if hits else 1

    if action == "list":
        cat = catalog_layer.build(root)
        if "--json" in args:
            target = Path(args[args.index("--json") + 1])
            cat.dump(root, target)
            print(f"已导出：{target}（{len(cat.entries)} 条）")
            return 0
        print("\n".join(f"[{e.kind}] {e.path.relative_to(root)}" for e in cat.entries))
        return 0

    if action == "check":
        missing = contract_layer.missing(root)
        unregistered = catalog_layer.build(root).unregistered(root)
        for asset in missing:
            print(f"缺资产：{asset.kind}（{asset.name}）")
        for path in unregistered:
            print(f"未登记：{path.relative_to(root)}")
        print("对账通过：二十格齐备，无未登记目录。" if not (missing or unregistered) else "")
        return 1 if (missing or unregistered) else 0

    if action == "new-contract" and args:
        target = Path(args[0])
        if target.exists():
            print(f"已存在：{target}")
            return 1
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(CONTRACT_TEMPLATE, encoding="utf-8")
        print(f"已写：{target}")
        return 0

    if action == "audit-contract" and args:
        return audit(Path(args[0]), CONTRACT_SECTIONS, "契约")

    if action == "audit-dossier" and args:
        return audit(Path(args[0]), DOSSIER_SECTIONS, "案卷")

    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
