"""入口：一个程序，六个动作（含开图形界面）。

工作区
  kg catalog [--json 文件]       看目录 / 导出目录
  kg audit [--json 文件] [--make]  审计——资产表有而工作区无、工作区有而资产表无；--make 补建缺的格子

查看
  kg find <名字> [--show]        按名找文档——认文件名与中文标题
  kg material [路径…] [--json]   看材料——类型、内容、来源、时间、阶段

工作流（过程的编排：串联的步骤，每步自带验收判据）
  kg workflow --list             有哪些工作流、各自的步骤
  kg workflow --new <名字> --steps 甲,乙,丙 [--note 一句话]   写一条工作流
  kg workflow <名字>             看这条工作流的步骤与判据

任务（工作流的一次执行实例）
  kg task --list                 有哪些任务、跑哪条工作流、下一步
  kg task --new <名字> --workflow <工作流> [--about 一句话]   起一件任务
  kg task <名字>                 看步骤状态与流水
  kg task <名字> --next           走下一步：执行者是 AI 的交给 AI（pi -p）跑，然后跑判据、记账
  kg task <名字> --done <步骤> [--note 一句话]   人为地记一步（人自己做的）
  kg task <名字> --history <一段话>   历史：写下这一次的来龙去脉（叙事）
  （数据默认落在实验室的 data/：工作流 workflows/、任务 tasks/、产物 artifacts/）

默认工作区从当前目录往上找（含 data/journal 的目录）；用 --root 指定别的第二大脑。
"""

import argparse
import sys
from pathlib import Path

from . import assets as assets_layer
from . import workflow as flow_layer
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


def cmd_workflow(root: Path, args) -> int:
    data = Path(args.data)
    if args.list:
        return emit(report.workflow_list(data))
    if args.new:
        steps = [item.strip() for item in args.steps.split(",") if item.strip()]
        return emit(report.workflow_new(data, args.name or "", steps, args.note))
    if not args.name:
        return emit(report.Result(ok=False, lines=["用法：kg workflow <名字>，或 kg workflow --list / --new <名字> --steps 甲,乙"]))
    return emit(report.workflow_show(data, args.name))


def cmd_task(root: Path, args) -> int:
    data = Path(args.data)
    if args.list:
        return emit(report.task_list(root, data))
    if args.new:
        return emit(report.task_new(root, data, args.name or "", args.workflow, args.about))
    if not args.name:
        return emit(report.Result(ok=False, lines=["用法：kg task <名字>，或 kg task --list / --new <名字> --workflow <工作流>"]))
    if args.history is not None:
        return emit(report.task_history(root, data, args.name, args.history if isinstance(args.history, str) else ""))
    if args.next:
        return emit(report.task_step(root, data, args.name, "", args.note, auto=True))
    if args.done is not None:
        return emit(report.task_step(root, data, args.name, args.done if isinstance(args.done, str) else "", args.note))
    return emit(report.task_status(root, data, args.name))


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
    parser.add_argument("--data", default=str(flow_layer.lab_data()), help="数据仓（默认实验室 data/）")
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

    flow = sub.add_parser("workflow", help="工作流：串联的步骤")
    flow.add_argument("name", nargs="?", metavar="名字")
    flow.add_argument("--list", action="store_true", help="有哪些工作流")
    flow.add_argument("--new", action="store_true", help="写一条工作流")
    flow.add_argument("--steps", default="", metavar="甲,乙,丙")
    flow.add_argument("--note", default="", metavar="一句话", help="这条工作流是干什么的")

    task = sub.add_parser("task", help="任务：工作流的一次执行实例")
    task.add_argument("name", nargs="?", metavar="名字")
    task.add_argument("--list", action="store_true", help="有哪些任务")
    task.add_argument("--new", action="store_true", help="起一件任务")
    task.add_argument("--workflow", default="", metavar="工作流", help="跑哪条工作流")
    task.add_argument("--about", default="", metavar="一句话", help="这一次要什么")
    task.add_argument("--next", action="store_true", help="走下一步（AI 执行者交给 pi 跑）")
    task.add_argument("--done", nargs="?", const=True, metavar="步骤", help="人为地记一步")
    task.add_argument("--note", default="", metavar="一句话", help="记一句这一步做了什么")
    task.add_argument("--history", nargs="?", const=True, metavar="一段话")
    sub.add_parser("gui", help="开图形界面")
    return parser


HANDLERS = {
    "find": cmd_find,
    "catalog": cmd_catalog,
    "audit": cmd_audit,
    "material": cmd_material,
    "workflow": cmd_workflow,
    "task": cmd_task,
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
