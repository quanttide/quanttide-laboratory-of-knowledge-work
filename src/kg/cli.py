"""入口：一个程序，十个动作（含开图形界面）。

工作区
  kg catalog [--json 文件]       看目录 / 导出目录
  kg audit [--json 文件] [--make]  审计——契约有而工作区无、工作区有而契约无；--make 补建缺的格子

查看
  kg find <名字> [--show]        按名找文档——认文件名与中文标题
  kg material [路径…] [--json]   看材料——类型、内容、来源、时间、阶段

契约
  kg new-contract <文件> [--about 路径]   写契约骨架；--about 以某件东西为题
  kg audit-contract <文件> [--into 报告]  核对契约；--into 把审查者报告写进报告

报告（事件）
  kg new-report <文件> [--about 标题]     写报告骨架（事件）
  kg audit-report <文件>         核对报告——段位齐全

一件事（对象在盘上，动作作用在它身上，事实自动记进流水）
  kg case --list                 有哪些事、各自下一步
  kg case --new <名字>           起一件事
  kg case <名字>                 看这件事的七格状态与流水
  kg case <名字> --material <路径>   记一条材料（类型 / 阶段 / 时间 / 来源现填）
  kg case <名字> --contract       以记下的材料立契约
  kg case <名字> --review         跑机械核对，审查者报告写进报告
  kg case <名字> --output <路径>     记一笔产出
  kg case <名字> --decision <话>     写下裁决
  kg case <名字> --finish         收尾：产出收束成成果，写进报告
  kg case <名字> --history <一段话>   写下这件事的来龙去脉（历史：叙事）
  （案子默认落在 <工作区>/cases/，用 --cases 换地方）

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


def cmd_new_report(root: Path, args) -> int:
    return emit(report.new_report(Path(args.target), args.about))


def cmd_audit_contract(root: Path, args) -> int:
    return emit(report.audit_contract(root, Path(args.target), Path(args.into) if args.into else None))


def cmd_case(root: Path, args) -> int:
    if args.list:
        return emit(report.case_list(root, args.cases))
    if args.new:
        return emit(report.case_new(root, args.name or "", args.cases, args.about))
    if not args.name:
        return emit(report.Result(ok=False, lines=["用法：kg case <名字>，或 kg case --list / --new <名字>"]))
    for action in ("material", "contract", "review", "output", "decision", "finish", "history"):
        if getattr(args, action):
            value = value_of(args, action)
            return emit(report.case_step(root, args.name, action, value, args.cases))
    return emit(report.case_status(root, args.name, args.cases))


def value_of(args, action: str) -> str:
    """能带值的几步：材料与产出给路径，裁决给一句话；契约与核对不带值也能走。"""
    given = getattr(args, action)
    if action in ("material", "output"):
        return given if isinstance(given, str) else ""
    if action in ("decision", "history"):
        return given if isinstance(given, str) else ""
    return ""


def cmd_audit_report(root: Path, args) -> int:
    return emit(report.audit_report(Path(args.target)))


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
    dossier = sub.add_parser("new-report", help="写报告骨架")
    dossier.add_argument("target", metavar="文件")
    dossier.add_argument("--about", default="", metavar="标题")
    checking = sub.add_parser("audit-contract", help="核对契约")
    checking.add_argument("target", metavar="文件")
    checking.add_argument("--into", metavar="报告", help="把审查者报告写进这份报告")
    sub.add_parser("audit-report", help="核对报告").add_argument("target", metavar="文件")
    case = sub.add_parser("case", help="一件事：起、看、走一步")
    case.add_argument("name", nargs="?", metavar="名字")
    case.add_argument("--list", action="store_true", help="有哪些事、各自下一步")
    case.add_argument("--new", action="store_true", help="起一件事")
    case.add_argument("--about", default="", metavar="一句话", help="起案时的一句话，或立契约时以哪件东西为题")
    case.add_argument("--cases", metavar="目录", help="案子放哪（默认 工作区/cases）")
    case.add_argument("--material", nargs="?", const=True, metavar="路径")
    case.add_argument("--contract", nargs="?", const=True, metavar="以它为题的路径")
    case.add_argument("--review", action="store_true")
    case.add_argument("--output", nargs="?", const=True, metavar="路径")
    case.add_argument("--decision", nargs="?", const=True, metavar="一句话")
    case.add_argument("--finish", action="store_true")
    case.add_argument("--history", nargs="?", const=True, metavar="一段话")
    sub.add_parser("gui", help="开图形界面")
    return parser


HANDLERS = {
    "find": cmd_find,
    "catalog": cmd_catalog,
    "audit": cmd_audit,
    "material": cmd_material,
    "new-contract": cmd_new_contract,
    "new-report": cmd_new_report,
    "audit-contract": cmd_audit_contract,
    "audit-report": cmd_audit_report,
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
