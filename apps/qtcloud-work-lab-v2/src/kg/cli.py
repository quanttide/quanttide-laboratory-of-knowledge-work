"""入口：一个程序，六个动作——工作流、工单，加工作区的看与核。

工作流（过程的定义：一串有序的步骤，每步写明谁做、怎么算完）
  kg workflow create <名字> --steps 甲,乙,丙 [--description 一句话]   写一条工作流
  kg workflow show <名字>              看这条工作流的步骤与判据
  kg workflow list                     有哪些工作流
  kg workflow check <名字>             定义核对：路径在不在区内、小节有没有判据覆盖
  kg workflow export <名字> <文件>      存成一份可带走的文件
  kg workflow import <文件> [--as 名字]  导进来用（先照 schema 验，重名挡）

工单（行程的账本：封面落笔即封，流水只增不改）
  kg order create <名字> --workflow <工作流> [--description 一句话]   开工单
  kg order show <名字>                 读全貌：封面加全量流水，进度照流水推导
  kg order list [--workflow <工作流>] [--json]   列本工作区的工单
  kg order next <名字> [--note 一句话]   走下一步：智能体执行，程序核 rule 判据
  kg order done <名字> <步骤> [--note 一句话]   人记一笔（闸门放行也走这里）
  kg order journal <名字> <一段话>       日志：叙事落产物
  kg order delete <名字>               删一张白纸：流水非空即拒

工作区（实验室自留：规格未规定，按 v1 原样保留）
  kg catalog [--json 文件]             看目录——按资产表清点工作区里实际有什么
  kg audit [--json 文件] [--make]      审计——资产表有而工作区无、工作区有而资产表无；--make 补建
  kg find <名字> [--show]              按名找文档——认文件名与中文标题
  kg material [路径…] [--json 文件]     看材料——类型、内容、来源、时间，阶段由位置承担

位置不进模型，由启动参数装载：--root 工作区根（判据基准与扫描面，缺省往上找 data/journal）、
--data 账本仓（工单与产物，缺省本 app 的 data/）、--workflows 定义目录（缺省 <账本仓>/workflows/）。
v1 的旗标写法也认：`order <名字> --next` 同 `order next <名字>`。
"""

import argparse
import sys
from pathlib import Path

from . import actions, catalog as catalog_layer, workspace as workspace_layer

WORKFLOW_VERBS = ("create", "show", "list", "check", "export", "import")
ORDER_VERBS = ("create", "show", "list", "next", "done", "journal", "delete")


def emit(result: actions.Result) -> int:
    print("\n".join(result.lines))
    return 0 if result.ok else 1


def split(words: list[str], verbs: tuple[str, ...]) -> tuple[str, list[str]]:
    """子命令取「名词 动词」：头一个词是动词就认，否则算旧写法（名字在前）。"""
    if words and words[0] in verbs:
        return words[0], words[1:]
    return "", words


def cmd_workflow(workspace, args) -> int:
    verb, rest = split(args.words, WORKFLOW_VERBS)
    if args.list or verb == "list":
        return emit(actions.workflow_list(workspace))
    if args.new or verb == "create":
        name = rest[0] if rest else ""
        steps = [item.strip() for item in args.steps.split(",") if item.strip()]
        return emit(actions.workflow_new(workspace, name, steps, args.description))
    if args.import_from or verb == "import":
        source = rest[0] if rest else args.import_from
        return emit(actions.workflow_import(workspace, Path(source), args.as_name))
    if args.check or verb == "check":
        return emit(actions.workflow_check(workspace, rest[0] if rest else ""))
    if args.export or verb == "export":
        name = rest[0] if rest else ""
        target = rest[1] if len(rest) > 1 else args.export
        return emit(actions.workflow_export(workspace, name, Path(target)))
    return emit(actions.workflow_show(workspace, rest[0] if rest else ""))


def cmd_order(workspace, args) -> int:
    verb, rest = split(args.words, ORDER_VERBS)
    if args.list or verb == "list":
        return emit(actions.order_list(workspace, args.workflow, args.json))
    if args.new or verb == "create":
        name = rest[0] if rest else ""
        return emit(actions.order_new(workspace, name, args.workflow, args.description))
    if args.delete or verb == "delete":
        return emit(actions.order_delete(workspace, rest[0] if rest else ""))
    if args.next or verb == "next":
        return emit(actions.order_next(workspace, rest[0] if rest else "", args.note))
    if args.journal is not None or verb == "journal":
        if verb == "journal":
            name, words = (rest[0] if rest else ""), " ".join(rest[1:])
        else:
            name, words = (rest[0] if rest else ""), (args.journal if isinstance(args.journal, str) else "")
        return emit(actions.order_journal(workspace, name, words))
    if args.done is not None or verb == "done":
        if verb == "done":
            name, step = (rest[0] if rest else ""), (rest[1] if len(rest) > 1 else "")
        else:
            name, step = (rest[0] if rest else ""), (args.done if isinstance(args.done, str) else "")
        return emit(actions.order_done(workspace, name, step, args.note))
    return emit(actions.order_show(workspace, rest[0] if rest else ""))


def cmd_catalog(workspace, args) -> int:
    if args.json:
        payload = actions.catalog_payload(workspace)
        catalog_layer.write_json(Path(args.json), payload)
        print(f"已导出：{args.json}（{payload['count']} 条）")
        return 0
    return emit(actions.catalog(workspace))


def cmd_find(workspace, args) -> int:
    return emit(actions.find(workspace, args.name, args.show))


def cmd_audit(workspace, args) -> int:
    if args.json:
        catalog_layer.write_json(Path(args.json), actions.audit_payload(workspace))
    return emit(actions.audit(workspace, args.make))


def cmd_material(workspace, args) -> int:
    if args.json:
        payload = actions.material_payload(workspace, args.paths)
        catalog_layer.write_json(Path(args.json), payload)
        print(f"已导出：{args.json}（{payload['count']} 条）")
        return 0
    return emit(actions.material(workspace, args.paths))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kg", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", help="工作区根（判据基准与工作区级扫描面；缺省从当前目录往上找 data/journal）")
    parser.add_argument("--data", help="账本仓：工单与产物（草稿）落在这里，缺省本 app 的 data/")
    parser.add_argument("--workflows", help="定义目录（缺省 <账本仓>/workflows/；固定资产常另指一处）")
    sub = parser.add_subparsers(dest="action", required=True)

    flow = sub.add_parser("workflow", help="工作流：一串有序的步骤")
    flow.add_argument("words", nargs="*", metavar="名字")
    flow.add_argument("--steps", default="", metavar="甲,乙,丙", help="串联的步骤（create 用）")
    flow.add_argument("--description", default="", metavar="一句话", help="这条工作流是干什么的")
    flow.add_argument("--list", action="store_true", help="有哪些工作流")
    flow.add_argument("--new", action="store_true", help="写一条工作流（同 create）")
    flow.add_argument("--check", action="store_true", help="定义核对")
    flow.add_argument("--export", metavar="文件", help="存成一份可带走的文件")
    flow.add_argument("--import", dest="import_from", metavar="文件", help="导进来一份工作流文件")
    flow.add_argument("--as", dest="as_name", default="", metavar="名字", help="导入时另起名字")

    order = sub.add_parser("order", help="工单：工作流的一次执行")
    order.add_argument("words", nargs="*", metavar="名字")
    order.add_argument("--workflow", default="", metavar="工作流", help="走哪条工作流")
    order.add_argument("--description", default="", metavar="一句话", help="这单要干什么")
    order.add_argument("--list", action="store_true", help="有哪些工单")
    order.add_argument("--new", action="store_true", help="开工单（同 create）")
    order.add_argument("--next", action="store_true", help="走下一步")
    order.add_argument("--done", nargs="?", const=True, metavar="步骤", help="人记一笔 / 闸门放行")
    order.add_argument("--delete", action="store_true", help="删一张白纸")
    order.add_argument("--journal", nargs="?", const=True, metavar="一段话", help="日志：叙事落产物")
    order.add_argument("--note", default="", metavar="一句话", help="记一句这一步做了什么")
    order.add_argument("--json", action="store_true", help="list 出机读一份")

    listing = sub.add_parser("catalog", help="看目录（工作区级）")
    listing.add_argument("--json", metavar="文件")

    audit = sub.add_parser("audit", help="审计工作区")
    audit.add_argument("--json", metavar="文件")
    audit.add_argument("--make", action="store_true", help="补建缺的资产格子")

    finding = sub.add_parser("find", help="按名找文档")
    finding.add_argument("name", metavar="名字")
    finding.add_argument("--show", action="store_true", help="连正文一起看")

    material = sub.add_parser("material", help="看材料")
    material.add_argument("paths", nargs="*", metavar="路径")
    material.add_argument("--json", metavar="文件")
    return parser


HANDLERS = {
    "workflow": cmd_workflow,
    "order": cmd_order,
    "catalog": cmd_catalog,
    "audit": cmd_audit,
    "find": cmd_find,
    "material": cmd_material,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    workspace = workspace_layer.resolve(args.root, args.data, args.workflows)
    return HANDLERS[args.action](workspace, args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
