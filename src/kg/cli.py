"""入口：一个程序，十个动作（含开图形界面）。

工作区
  kg catalog [--json 文件]       看目录 / 导出目录
  kg audit [--json 文件] [--make]  审计——契约有而工作区无、工作区有而契约无；--make 补建缺的格子

查看
  kg find <名字> [--show]        按名找文档——认文件名与中文标题
  kg material [路径…] [--json]   看材料——类型、内容、来源、时间、阶段

契约
  kg new-contract <文件> [--about 路径]   写契约骨架；--about 以某件东西为题
  kg audit-contract <文件> [--into 案卷]  核对契约；--into 把审查者报告写进案卷

案卷
  kg new-dossier <文件> [--about 标题]    写案卷骨架
  kg audit-dossier <文件>        核对案卷——段位齐全

一件事
  kg case <文件>                 看这件事走到哪一步、下一步做什么
  kg case --new <文件>           起一件事（材料 / 契约 / 产出 / 案卷）

  kg gui                         开图形界面（同一个程序的窗口版）

默认工作区从当前目录往上找（含 data/journal 的目录）；用 --root 指定别的第二大脑。
"""

import argparse
import sys
from pathlib import Path

from . import assets as assets_layer
from . import catalog as catalog_layer
from . import report


def emit(result: report.Result) -> int:
    print("\n".join(result.lines))
    return 0 if result.ok else 1


def cmd_find(root: Path, args) -> int:
    return emit(report.find(root, args.name, args.show))


def cmd_catalog(root: Path, args) -> int:
    result = report.catalog(root)
    if args.json:
        payload = report.catalog_payload(root)
        catalog_layer.write_json(Path(args.json), payload)
        print(f"已导出：{args.json}（{payload['count']} 条）")
        return 0
    return emit(result)


def cmd_audit(root: Path, args) -> int:
    if args.json:
        catalog_layer.write_json(Path(args.json), report.audit_payload(root))
    return emit(report.audit(root, make=args.make))


def cmd_material(root: Path, args) -> int:
    if args.json:
        payload = report.material_payload(root, args.paths)
        catalog_layer.write_json(Path(args.json), payload)
        print(f"已导出：{args.json}（{payload['count']} 条）")
        return 0
    return emit(report.material(root, args.paths))


def cmd_new_contract(root: Path, args) -> int:
    return emit(report.new_contract(Path(args.target), args.about))


def cmd_new_dossier(root: Path, args) -> int:
    return emit(report.new_dossier(Path(args.target), args.about))


def cmd_audit_contract(root: Path, args) -> int:
    return emit(report.audit_contract(root, Path(args.target), Path(args.into) if args.into else None))


def cmd_case(root: Path, args) -> int:
    if args.new:
        return emit(report.case_new(Path(args.target or ""), args.about))
    return emit(report.case(root, Path(args.target or "")))


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

    listing = sub.add_parser("catalog", help="看目录")
    listing.add_argument("--json", metavar="文件")

    audit = sub.add_parser("audit", help="审计工作区")
    audit.add_argument("--json", metavar="文件")
    audit.add_argument("--make", action="store_true", help="补建缺的资产格子")

    material = sub.add_parser("material", help="看材料")
    material.add_argument("paths", nargs="*", metavar="路径")
    material.add_argument("--json", metavar="文件")

    contract = sub.add_parser("new-contract", help="写契约骨架")
    contract.add_argument("target", metavar="文件")
    contract.add_argument("--about", default="", metavar="路径", help="以某件已有的东西为题")
    dossier = sub.add_parser("new-dossier", help="写案卷骨架")
    dossier.add_argument("target", metavar="文件")
    dossier.add_argument("--about", default="", metavar="标题")
    checking = sub.add_parser("audit-contract", help="核对契约")
    checking.add_argument("target", metavar="文件")
    checking.add_argument("--into", metavar="案卷", help="把审查者报告写进这份案卷")
    sub.add_parser("audit-dossier", help="核对案卷").add_argument("target", metavar="文件")
    case = sub.add_parser("case", help="看一件事 / 起一件事")
    case.add_argument("target", nargs="?", metavar="文件")
    case.add_argument("--new", action="store_true", help="起一件事（写出四段骨架）")
    case.add_argument("--about", default="", metavar="标题")
    sub.add_parser("gui", help="开图形界面")
    return parser


HANDLERS = {
    "find": cmd_find,
    "catalog": cmd_catalog,
    "audit": cmd_audit,
    "material": cmd_material,
    "new-contract": cmd_new_contract,
    "new-dossier": cmd_new_dossier,
    "audit-contract": cmd_audit_contract,
    "audit-dossier": cmd_audit_dossier,
    "case": cmd_case,
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
