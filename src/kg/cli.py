"""入口：一个程序，十个动作（含开图形界面）。

工作区
  kg catalog [--json 文件]       看目录 / 导出目录
  kg audit [--json 文件] [--make]  审计——资产表有而工作区无、工作区有而资产表无；--make 补建缺的格子

查看
  kg find <名字> [--show]        按名找文档——认文件名与中文标题
  kg material [路径…] [--json]   看材料——类型、内容、来源、时间、阶段

指令
  kg new-instruction <文件> [--about 目标]  写指令骨架（目标 / 步骤 / 验收）
  kg audit-instruction <文件> [--into 报告] 核对指令；--into 把审查者报告写进报告

报告（事件）
  kg new-report <文件> [--about 标题]     写报告骨架（事件）
  kg audit-report <文件>         核对报告——段位齐全

工作流
  kg workflow                    看工作流：默认「一次交付」的七个标准任务与各自产出物

运行（工作流的一次运行；每个动作就是把一个标准任务执行一次）
  kg run --list                  有哪些运行、各自下一个标准任务
  kg run --new <名字>            起一次运行
  kg run <名字>                  看七个标准任务的状态与流水
  kg run <名字> --material <路径>    材料：记一条输入（类型 / 阶段 / 时间 / 来源现填）
  kg run <名字> --instruction     指令：写出目标 / 步骤 / 验收，人补齐
  kg run <名字> --review          核对：跑验收里的机械判据，结果写进报告
  kg run <名字> --output <路径>      产出：记一笔做出来的东西
  kg run <名字> --decision <话>      裁决：谁拍板、决定是什么
  kg run <名字> --finish          成果：把产出收束成成果，写进报告
  kg run <名字> --history <一段话>   历史：写下这一次的来龙去脉（叙事）
  （数据默认落在实验室的 data/：报告进 report/、历史进 history/、运行的现场进 runs/）

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


def cmd_new_instruction(root: Path, args) -> int:
    return emit(report.new_instruction(Path(args.target), args.about))


def cmd_new_report(root: Path, args) -> int:
    return emit(report.new_report(Path(args.target), args.about))


def cmd_audit_instruction(root: Path, args) -> int:
    return emit(report.audit_instruction(root, Path(args.target), Path(args.into) if args.into else None))


def cmd_run(root: Path, args) -> int:
    data = Path(args.data)
    if args.list:
        return emit(report.run_list(root, data, args.runs))
    if args.new:
        return emit(report.run_new(root, args.name or "", data, args.runs, args.about))
    if not args.name:
        return emit(report.Result(ok=False, lines=["用法：kg run <名字>，或 kg run --list / --new <名字>"]))
    for action in ("material", "instruction", "review", "output", "decision", "finish", "history"):
        if getattr(args, action):
            value = value_of(args, action)
            return emit(report.run_step(root, args.name, action, value, data, args.runs))
    return emit(report.run_status(root, args.name, data, args.runs))


def value_of(args, action: str) -> str:
    """能带值的几步：材料与产出给路径，裁决与历史给一段话；指令与核对不带值也能走。"""
    given = getattr(args, action)
    if action in ("material", "output"):
        return given if isinstance(given, str) else ""
    if action in ("decision", "history", "instruction"):
        return given if isinstance(given, str) else ""
    return ""


def cmd_audit_report(root: Path, args) -> int:
    return emit(report.audit_report(Path(args.target)))


def cmd_workflow(root: Path, args) -> int:
    flow = flow_layer.WORKFLOW
    result = report.Result(columns=("标准任务", "产出物", "怎么算完"), lines=[f"工作流：{flow.name}——{flow.note}", "标准任务："])
    for task in flow.tasks:
        result.rows.append((task.name, task.output, task.accept))
        result.lines.append(f"  {task.name}：{task.what} → {task.output}（{task.accept}）")
    return emit(result)


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

    instruction = sub.add_parser("new-instruction", help="写指令骨架")
    instruction.add_argument("target", metavar="文件")
    instruction.add_argument("--about", default="", metavar="目标", help="目标一句话")
    dossier = sub.add_parser("new-report", help="写报告骨架")
    dossier.add_argument("target", metavar="文件")
    dossier.add_argument("--about", default="", metavar="标题")
    checking = sub.add_parser("audit-instruction", help="核对指令")
    checking.add_argument("target", metavar="文件")
    checking.add_argument("--into", metavar="报告", help="把审查者报告写进这份报告")
    sub.add_parser("audit-report", help="核对报告").add_argument("target", metavar="文件")
    runner = sub.add_parser("run", help="工作流的一次运行：起、看、走一个标准任务")
    runner.add_argument("name", nargs="?", metavar="名字")
    runner.add_argument("--list", action="store_true", help="有哪些事、各自下一步")
    runner.add_argument("--new", action="store_true", help="起一次运行")
    runner.add_argument("--about", default="", metavar="一句话", help="这次运行的一句话（目标）")
    runner.add_argument("--runs", metavar="目录", help="任务放哪（默认 <数据仓>/tasks）")
    runner.add_argument("--material", nargs="?", const=True, metavar="路径")
    runner.add_argument("--instruction", nargs="?", const=True, metavar="目标一句话")
    runner.add_argument("--review", action="store_true")
    runner.add_argument("--output", nargs="?", const=True, metavar="路径")
    runner.add_argument("--decision", nargs="?", const=True, metavar="一句话")
    runner.add_argument("--finish", action="store_true")
    runner.add_argument("--history", nargs="?", const=True, metavar="一段话")
    sub.add_parser("workflow", help="看工作流：一串标准任务")
    sub.add_parser("gui", help="开图形界面")
    return parser


HANDLERS = {
    "find": cmd_find,
    "catalog": cmd_catalog,
    "audit": cmd_audit,
    "material": cmd_material,
    "new-instruction": cmd_new_instruction,
    "new-report": cmd_new_report,
    "audit-instruction": cmd_audit_instruction,
    "audit-report": cmd_audit_report,
    "run": cmd_run,
    "workflow": cmd_workflow,
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
