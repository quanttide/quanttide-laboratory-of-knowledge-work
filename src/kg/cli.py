"""入口：一个程序，九个动作（含开图形界面）。

  kg find <名字> [--show]        按名找文档——认文件名与中文标题
  kg list [--json 文件]          看全库 / 导出目录
  kg audit [--json 文件]         审计——契约有而工作区无、工作区有而契约无
  kg material [路径…] [--json]   看材料——类型、内容、来源、时间、阶段
  kg new-contract <文件>         写契约骨架（目标 / 输出形态 / 必须包含 / 检查项）
  kg new-dossier <文件>          写案卷骨架（产出 / 审查 / 裁决 / 成果）
  kg audit-contract <文件>       核对契约——段位齐全、跑机械核对、列出闸门项
  kg audit-dossier <文件>        核对案卷——段位齐全
  kg gui                         开图形界面（同一个程序的窗口版）

默认工作区从当前目录往上找（含 data/journal 的目录）；用 --root 指定别的第二大脑。
"""

import argparse
import sys
from pathlib import Path

from . import assets as assets_layer
from . import catalog as catalog_layer
from . import records
from . import report


def emit(result: report.Result) -> int:
    print("\n".join(result.lines))
    return 0 if result.ok else 1


def cmd_find(root: Path, args) -> int:
    return emit(report.find(root, args.name, args.show))


def cmd_list(root: Path, args) -> int:
    result = report.list_all(root)
    if args.json:
        payload = report.list_payload(root)
        catalog_layer.write_json(Path(args.json), payload)
        print(f"已导出：{args.json}（{payload['count']} 条）")
        return 0
    return emit(result)


def cmd_audit(root: Path, args) -> int:
    if args.json:
        catalog_layer.write_json(Path(args.json), report.audit_payload(root))
    return emit(report.audit(root))


def cmd_material(root: Path, args) -> int:
    if args.json:
        payload = report.material_payload(root, args.paths)
        catalog_layer.write_json(Path(args.json), payload)
        print(f"已导出：{args.json}（{payload['count']} 条）")
        return 0
    return emit(report.material(root, args.paths))


def cmd_new_contract(root: Path, args) -> int:
    return emit(report.new_record(Path(args.target), records.CONTRACT_TEMPLATE))


def cmd_new_dossier(root: Path, args) -> int:
    return emit(report.new_record(Path(args.target), records.DOSSIER_TEMPLATE))


def cmd_audit_contract(root: Path, args) -> int:
    return emit(report.audit_contract(root, Path(args.target)))


def cmd_audit_dossier(root: Path, args) -> int:
    return emit(report.audit_dossier(Path(args.target)))


def cmd_gui(root: Path, args) -> int:
    try:
        from . import gui
    except ImportError:
        print(
            "界面开不起来——当前 Python 缺 PySide6 的窗口模块。两种补法：\n"
            "  1. 实验室内建虚拟环境（推荐，不动系统）：uv venv .venv && uv pip install -e '.[gui]'，然后用 .venv/bin/kg-gui\n"
            "  2. 用发行版的包：sudo apt install python3-pyside6.qtwidgets"
        )
        return 2
    return gui.main(["--root", str(root)])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kg", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", help="工作区根（默认从当前目录往上找）")
    sub = parser.add_subparsers(dest="action", required=True)

    find = sub.add_parser("find", help="按名找文档")
    find.add_argument("name", metavar="名字")
    find.add_argument("--show", action="store_true", help="连正文一起看")

    listing = sub.add_parser("list", help="列全库")
    listing.add_argument("--json", metavar="文件")

    audit = sub.add_parser("audit", help="审计工作区")
    audit.add_argument("--json", metavar="文件")

    material = sub.add_parser("material", help="看材料")
    material.add_argument("paths", nargs="*", metavar="路径")
    material.add_argument("--json", metavar="文件")

    for name, help_text in (("new-contract", "写契约骨架"), ("new-dossier", "写案卷骨架")):
        sub.add_parser(name, help=help_text).add_argument("target", metavar="文件")
    for name, help_text in (("audit-contract", "核对契约"), ("audit-dossier", "核对案卷")):
        sub.add_parser(name, help=help_text).add_argument("target", metavar="文件")
    sub.add_parser("gui", help="开图形界面")
    return parser


HANDLERS = {
    "find": cmd_find,
    "list": cmd_list,
    "audit": cmd_audit,
    "material": cmd_material,
    "new-contract": cmd_new_contract,
    "new-dossier": cmd_new_dossier,
    "audit-contract": cmd_audit_contract,
    "audit-dossier": cmd_audit_dossier,
    "gui": cmd_gui,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        root = Path(args.root).resolve() if args.root else assets_layer.repo_root()
    except FileNotFoundError as error:
        print(error)
        return 2
    return HANDLERS[args.action](root, args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
