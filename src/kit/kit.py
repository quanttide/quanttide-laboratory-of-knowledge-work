#!/usr/bin/env python3
"""知识工作工具箱（实验室版）：一个入口，七个动作。

  kg find <名字> [--show]      按名找文档——认文件名与中文标题
  kg list [--json 目录.json]   看全库 / 导出目录
  kg check [--json 报告.json]  对账——契约有而仓库无、仓库有而契约无
  kg new-contract <文件>       写契约骨架（目标 / 输出形态 / 必须包含 / 检查项）
  kg new-dossier <文件>        写案卷骨架（产出 / 审查 / 裁决 / 成果）
  kg audit-contract <文件>     核对契约：四段齐全，跑机械核对，列出闸门项
  kg audit-dossier <文件>      核对案卷：四段齐全

契约与目录两层取 resolver/ 的库，检查项判据取 checks.py——入口只做入口，
库不打印、不定位，都可以被别的程序复用。
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "resolver"))
import catalog as catalog_layer  # noqa: E402
import checks as checks_layer  # noqa: E402
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

- [ ] 机械：目标侧文件已就位 `path:data/journal/README.md`
- [ ] 机械：旧位置的副本已删除 `absent:data/journal/old.md`
- [ ] 闸门：落点与源位置同构
"""

DOSSIER_TEMPLATE = """# 案卷：<一句话说清这是哪一件事>

## 生成者产出

- <谁、按哪份契约、交了什么>

## 审查者报告

- ✓ <机械核对通过的项>
- ⧗ <留给闸门的项>

## 人类裁决

<谁拍的板、决定是什么>

## 最终成果

- <最后交出什么、落在哪>
"""


def sections(path: Path) -> set[str]:
    return {line[3:].strip() for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("## ")}


def audit_sections(path: Path, required: tuple[str, ...], label: str) -> bool:
    found = sections(path)
    for name in required:
        print(f"  {'✓' if name in found else '✗'} {name}")
    missing = [name for name in required if name not in found]
    print(f"{label}完整。" if not missing else f"{label}不完整：缺 {'、'.join(missing)}")
    return not missing


def command_check(root: Path, args: list[str]) -> int:
    missing = contract_layer.missing(root)
    unregistered = catalog_layer.build(root).unregistered(root)
    report = {
        "root": root.name,
        "result": "通过" if not (missing or unregistered) else "有问题",
        "missing": [{"kind": asset.kind, "name": asset.name} for asset in missing],
        "unregistered": [str(path.relative_to(root)) for path in unregistered],
    }
    if "--json" in args:
        target = Path(args[args.index("--json") + 1])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for asset in missing:
        print(f"缺资产：{asset.kind}（{asset.name}）")
    for path in unregistered:
        print(f"未登记：{path.relative_to(root)}")
    if not (missing or unregistered):
        print("对账通过：二十格齐备，无未登记目录。")
    return 1 if (missing or unregistered) else 0


def command_find(root: Path, args: list[str]) -> int:
    catalog = catalog_layer.build(root)
    matches = catalog.find(args[0])
    if not matches:
        print(f"未找到：{args[0]}")
        return 1
    for entry in matches:
        print(f"[{entry.kind}] {entry.path.relative_to(root)}")
        if "--show" in args[1:]:
            if entry.path.is_dir():
                print("  （目录）" + "、".join(sorted(p.name for p in entry.path.iterdir() if not p.name.startswith("."))))
            else:
                print(entry.path.read_text(encoding="utf-8").rstrip())
    return 0


def command_list(root: Path, args: list[str]) -> int:
    catalog = catalog_layer.build(root)
    if "--json" in args:
        target = Path(args[args.index("--json") + 1])
        catalog.dump(root, target)
        print(f"已导出：{target}（{len(catalog.entries)} 条）")
        return 0
    for entry in catalog.entries:
        print(f"[{entry.kind}] {entry.path.relative_to(root)}")
    return 0


def command_audit_contract(root: Path, target: Path) -> int:
    if not audit_sections(target, CONTRACT_SECTIONS, "契约"):
        return 1
    items = checks_layer.parse(target.read_text(encoding="utf-8"))
    results, gates = checks_layer.run(root, items)
    if results:
        print("机械核对：")
        for item, ok, detail in results:
            print(f"  {'✓' if ok else '✗'} {item.note}（{detail}）")
    if gates:
        print("闸门项（留给人拍板）：")
        for item in gates:
            print(f"  - {item.note}")
    return 1 if any(not ok for _, ok, _ in results) else 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    action, args = argv[1], argv[2:]
    root = contract_layer.repo_root()

    if action == "find" and args:
        return command_find(root, args)
    if action == "list":
        return command_list(root, args)
    if action == "check":
        return command_check(root, args)
    if action == "new-contract" and args:
        return write_new(Path(args[0]), CONTRACT_TEMPLATE)
    if action == "new-dossier" and args:
        return write_new(Path(args[0]), DOSSIER_TEMPLATE)
    if action == "audit-contract" and args:
        return command_audit_contract(root, Path(args[0]))
    if action == "audit-dossier" and args:
        return 0 if audit_sections(Path(args[0]), DOSSIER_SECTIONS, "案卷") else 1
    print(__doc__)
    return 2


def write_new(target: Path, template: str) -> int:
    if target.exists():
        print(f"已存在：{target}")
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(template, encoding="utf-8")
    print(f"已写：{target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
