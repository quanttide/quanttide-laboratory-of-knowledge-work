"""入口：一个程序，八个动作。

  kg find <名字> [--show]        按名找文档——认文件名与中文标题
  kg list [--json 文件]          看全库 / 导出目录
  kg check [--json 文件]         对账——契约有而仓库无、仓库有而契约无
  kg material [路径…] [--json]   看材料——类型、内容、来源、时间、阶段
  kg new-contract <文件>         写契约骨架（目标 / 输出形态 / 必须包含 / 检查项）
  kg new-dossier <文件>          写案卷骨架（产出 / 审查 / 裁决 / 成果）
  kg audit-contract <文件>       核对契约——段位齐全、跑机械核对、列出闸门项
  kg audit-dossier <文件>        核对案卷——段位齐全

默认工作区从当前目录往上找（含 data/journal 的目录）；用 --root 指定别的第二大脑。
"""

import argparse
import json
from pathlib import Path

from . import assets as assets_layer
from . import catalog as catalog_layer
from . import checks as checks_layer
from . import material as material_layer
from . import records

HEAD = f"{'材料':52} 类型  阶段  时间        来源"


def cmd_find(root: Path, args) -> int:
    matches = catalog_layer.build(root).find(args.name)
    if not matches:
        print(f"未找到：{args.name}")
        return 1
    for entry in matches:
        print(f"[{entry.kind}] {entry.path.relative_to(root)}")
        if args.show:
            if entry.path.is_dir():
                print("  （目录）" + "、".join(sorted(p.name for p in entry.path.iterdir() if not p.name.startswith("."))))
            else:
                print(entry.path.read_text(encoding="utf-8").rstrip())
    return 0


def cmd_list(root: Path, args) -> int:
    catalog = catalog_layer.build(root)
    if args.json:
        catalog.dump(root, Path(args.json))
        print(f"已导出：{args.json}（{len(catalog.entries)} 条）")
        return 0
    for entry in catalog.entries:
        print(f"[{entry.kind}] {entry.path.relative_to(root)}")
    return 0


def cmd_check(root: Path, args) -> int:
    missing = assets_layer.missing(root)
    unregistered = catalog_layer.build(root).unregistered(root)
    report = {
        "root": root.name,
        "result": "通过" if not (missing or unregistered) else "有问题",
        "missing": [{"kind": asset.kind, "name": asset.name} for asset in missing],
        "unregistered": [str(path.relative_to(root)) for path in unregistered],
    }
    if args.json:
        catalog_layer.write_json(Path(args.json), report)
    for asset in missing:
        print(f"缺资产：{asset.kind}（{asset.name}）")
    for path in unregistered:
        print(f"未登记：{path.relative_to(root)}")
    if not (missing or unregistered):
        print("对账通过：二十格齐备，无未登记目录。")
    return 1 if (missing or unregistered) else 0


def cmd_material(root: Path, args) -> int:
    found = material_layer.materials(root, args.paths)
    if args.json:
        payload = {"count": len(found), "materials": [{"path": rel, **vars(mat)} for rel, mat in found]}
        catalog_layer.write_json(Path(args.json), payload)
        print(f"已导出：{args.json}（{len(found)} 条）")
        return 0
    print(HEAD)
    gaps = []
    for rel, mat in found:
        print(f"{rel:52} {mat.type:5} {mat.stage:5} {mat.created_at or '（缺）':11} {mat.source}")
        if mat.missing:
            gaps.append((rel, mat.missing))
    for rel, fields in gaps:
        print(f"缺字段：{rel}——{'、'.join(fields)}")
    print("阶段由资产位置承担：日志是原始，其余是材料。")
    return 1 if gaps else 0


def cmd_new(root: Path, args, template: str) -> int:
    target = Path(args.target)
    if target.exists():
        print(f"已存在：{target}")
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(template, encoding="utf-8")
    print(f"已写：{target}")
    return 0


def cmd_new_contract(root: Path, args) -> int:
    return cmd_new(root, args, records.CONTRACT_TEMPLATE)


def cmd_new_dossier(root: Path, args) -> int:
    return cmd_new(root, args, records.DOSSIER_TEMPLATE)


def cmd_audit_contract(root: Path, args) -> int:
    target = Path(args.target)
    missing = records.missing_sections(target, records.CONTRACT_SECTIONS)
    for name in records.CONTRACT_SECTIONS:
        print(f"  {'✓' if name not in missing else '✗'} {name}")
    if missing:
        print(f"契约不完整：缺 {'、'.join(missing)}")
        return 1
    print("契约完整。")
    results, gates = checks_layer.run(root, checks_layer.parse(target.read_text(encoding="utf-8")))
    if results:
        print("机械核对：")
        for item, ok, detail in results:
            print(f"  {'✓' if ok else '✗'} {item.note}（{detail}）")
    if gates:
        print("闸门项（留给人拍板）：")
        for item in gates:
            print(f"  - {item.note}")
    return 1 if any(not ok for _, ok, _ in results) else 0


def cmd_audit_dossier(root: Path, args) -> int:
    target = Path(args.target)
    missing = records.missing_sections(target, records.DOSSIER_SECTIONS)
    for name in records.DOSSIER_SECTIONS:
        print(f"  {'✓' if name not in missing else '✗'} {name}")
    if missing:
        print(f"案卷不完整：缺 {'、'.join(missing)}")
        return 1
    print("案卷完整。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kg", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", help="工作区根（默认从当前目录往上找）")
    sub = parser.add_subparsers(dest="action", required=True)

    find = sub.add_parser("find", help="按名找文档")
    find.add_argument("name", metavar="名字")
    find.add_argument("--show", action="store_true", help="连正文一起看")

    listing = sub.add_parser("list", help="列全库")
    listing.add_argument("--json", metavar="文件")

    check = sub.add_parser("check", help="对账")
    check.add_argument("--json", metavar="文件")

    material = sub.add_parser("material", help="看材料")
    material.add_argument("paths", nargs="*", metavar="路径")
    material.add_argument("--json", metavar="文件")

    for name, help_text in (("new-contract", "写契约骨架"), ("new-dossier", "写案卷骨架")):
        sub.add_parser(name, help=help_text).add_argument("target", metavar="文件")
    for name, help_text in (("audit-contract", "核对契约"), ("audit-dossier", "核对案卷")):
        sub.add_parser(name, help=help_text).add_argument("target", metavar="文件")
    return parser


HANDLERS = {
    "find": cmd_find,
    "list": cmd_list,
    "check": cmd_check,
    "material": cmd_material,
    "new-contract": cmd_new_contract,
    "new-dossier": cmd_new_dossier,
    "audit-contract": cmd_audit_contract,
    "audit-dossier": cmd_audit_dossier,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        root = Path(args.root).resolve() if args.root else assets_layer.repo_root()
    except FileNotFoundError as error:
        print(error)
        return 2
    return HANDLERS[args.action](root, args)
