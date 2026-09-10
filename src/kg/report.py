"""动作的结果：命令行与图形界面共用的一层。

每个动作返回一个 Result——`ok` 通不通，`lines` 是命令行要打印的话，
`columns`/`rows` 是界面要画的同一份表格。界面只管画，命令行只管印，
算法只在这里写一遍。

几个动作之间有接口，任务就是这么串起来的：
  材料（输入）→ 以它立契约 → 核对契约（审查者报告）→ 写进案卷 → 成果登记回工作区。
"""

from dataclasses import dataclass, field
from pathlib import Path

from . import assets as assets_layer
from . import catalog as catalog_layer
from . import task as task_layer
from . import workflow as flow_layer
from . import checks as checks_layer
from . import material as material_layer
from . import records

MECHANICAL = ("核对", "结论", "说明")
STEPS = ("material", "instruction", "review", "output", "decision", "finish", "history")


@dataclass
class Result:
    ok: bool = True
    lines: list[str] = field(default_factory=list)
    columns: tuple[str, ...] = ()
    rows: list[tuple[str, ...]] = field(default_factory=list)

    def with_first(self, line: str) -> "Result":
        self.lines.insert(0, line)
        return self


def short(root: Path, path: Path) -> str:
    return str(path.relative_to(root)) if path.is_relative_to(root) else str(path)


def here(root: Path, text: str) -> Path:
    """把记录里写的一个路径，认成盘上的路径（相对工作区或绝对）。"""
    path = Path(text.strip())
    return path if path.is_absolute() else root / path


# ---- 工作区 ----


def catalog(root: Path) -> Result:
    found = catalog_layer.build(root)
    result = Result(columns=("种类", "路径"))
    for entry in found.entries:
        rel = short(root, entry.path)
        result.lines.append(f"[{entry.kind}] {rel}")
        result.rows.append((entry.kind, rel))
    return result


def catalog_payload(root: Path) -> dict:
    found = catalog_layer.build(root)
    return {
        "root": root.name,
        "count": len(found.entries),
        "entries": [{"kind": e.kind, "path": short(root, e.path), "names": sorted(e.names)} for e in found.entries],
    }


def audit(root: Path, make: bool = False) -> Result:
    """审计工作区：契约有而工作区无、工作区有而契约无；make 为真则补建缺的格子。"""
    missing = assets_layer.missing(root)
    unregistered = catalog_layer.build(root).unregistered(root)
    made = assets_layer.make(root, missing) if make else []
    missing = assets_layer.missing(root)
    unregistered = catalog_layer.build(root).unregistered(root)
    ok = not (missing or unregistered)
    result = Result(
        ok=ok,
        columns=("问题", "说明"),
        rows=[("缺资产", f"{a.kind}（{a.name}）") for a in missing] + [("未登记", short(root, p)) for p in unregistered],
    )
    result.lines = [f"补建：{short(root, path)}" for path in made]
    result.lines += [f"{kind}：{what}" for kind, what in result.rows]
    if ok:
        result.lines.append("审计通过：二十格齐备，无未登记目录。")
    elif unregistered and not missing:
        result.lines.append("未登记的目录要么属于某一格（改资产表），要么不该在这儿。")
    return result


def audit_payload(root: Path) -> dict:
    missing = assets_layer.missing(root)
    unregistered = catalog_layer.build(root).unregistered(root)
    return {
        "root": root.name,
        "result": "通过" if not (missing or unregistered) else "有问题",
        "missing": [{"kind": asset.kind, "name": asset.name} for asset in missing],
        "unregistered": [short(root, path) for path in unregistered],
    }


# ---- 查看 ----


def find(root: Path, name: str, show: bool = False) -> Result:
    if not name.strip():
        return Result(ok=False, lines=["请填要找的名字"])
    matches = catalog_layer.build(root).find(name)
    if not matches:
        return Result(ok=False, lines=[f"未找到：{name}"])
    result = Result()
    for entry in matches:
        rel = short(root, entry.path)
        result.lines.append(f"[{entry.kind}] {rel}")
        result.rows.append((entry.kind, rel))
        if show:
            if entry.path.is_dir():
                result.lines.append("  （目录）" + "、".join(sorted(p.name for p in entry.path.iterdir() if not p.name.startswith("."))))
            else:
                result.lines.append(entry.path.read_text(encoding="utf-8").rstrip())
    result.columns = ("种类", "路径")
    return result


def material(root: Path, paths: list[str] | None = None) -> Result:
    found = material_layer.materials(root, paths)
    result = Result(columns=("材料", "类型", "阶段", "时间", "来源"))
    for rel, mat in found:
        result.rows.append((rel, mat.type, mat.stage, mat.created_at or "（缺）", mat.source))
        result.lines.append(f"{rel:52} {mat.type:5} {mat.stage:5} {mat.created_at or '（缺）':11} {mat.source}")
        if mat.missing:
            result.ok = False
            result.lines.append(f"缺字段：{rel}——{'、'.join(mat.missing)}")
    if result.ok:
        result.lines.append("阶段由资产位置承担：日志是原始，其余是材料。")
    return result


def material_payload(root: Path, paths: list[str] | None = None) -> dict:
    found = material_layer.materials(root, paths)
    return {"count": len(found), "materials": [{"path": rel, **vars(mat)} for rel, mat in found]}


# ---- 记录：骨架与核对 ----


def workflow_new(data: Path, name: str, steps: list[str], note: str = "") -> Result:
    if not name.strip():
        return Result(ok=False, lines=["请先给工作流起个名字"])
    if not steps:
        return Result(ok=False, lines=["至少给一个步骤：--steps 甲,乙,丙"])
    flow = flow_layer.create(data, name.strip(), steps, note)
    return workflow_show(data, name.strip()).with_first(f"写下工作流：{short(data, flow.file)}")


def workflow_show(data: Path, name: str) -> Result:
    flow = flow_layer.open_workflow(data, name)
    if not flow.exists():
        return Result(ok=False, lines=[f"没有这条工作流：{short(data, flow.file)}"])
    result = Result(columns=("步骤", "谁执行", "怎么算完"), lines=[f"工作流：{flow.name}（{short(data, flow.file)}）"])
    for step in flow.steps():
        counts = f"{len(step.rules)} rule / {len(step.agents)} agent / {len(step.gates)} human"
        result.rows.append((step.name, step.executor, counts))
        result.lines.append(f"  {step.name}：{step.executor}　{counts}")
    return result


def workflow_export(data: Path, name: str, target: Path) -> Result:
    flow = flow_layer.open_workflow(data, name)
    if not flow.exists():
        return Result(ok=False, lines=[f"没有这条工作流：{short(data, flow.file)}"])
    saved = flow_layer.export(flow, target)
    result = workflow_show(data, name)
    result.lines.insert(0, f"已导出：{saved}（步骤 {len(flow.steps())} 个，原样带走）")
    return result


def workflow_import(data: Path, source: Path, name: str = "") -> Result:
    if not Path(source).is_file():
        return Result(ok=False, lines=[f"没有这份文件：{source}"])
    try:
        flow = flow_layer.import_workflow(data, source, name)
    except (ValueError, FileExistsError) as error:
        return Result(ok=False, lines=[str(error)])
    result = workflow_show(data, flow.name)
    result.lines.insert(0, f"已导入：{short(data, flow.file)}（步骤 {len(flow.steps())} 个）")
    return result


def workflow_list(data: Path) -> Result:
    found = flow_layer.listing(data)
    result = Result(columns=("工作流", "步骤", "位置"), lines=[])
    for flow in found:
        result.rows.append((flow.name, "、".join(step.name for step in flow.steps()), short(data, flow.file)))
        result.lines.append(f"{flow.name:24} 步骤：{'、'.join(step.name for step in flow.steps())}")
    if not found:
        result.lines = ["还没有工作流：kg workflow --new <名字> --steps 甲,乙"]
    return result


def task_new(root: Path, data: Path, name: str, workflow: str) -> Result:
    if not name.strip():
        return Result(ok=False, lines=["请先给这件任务起个名字"])
    flow = flow_layer.open_workflow(data, workflow)
    if not flow.exists():
        return Result(ok=False, lines=[f"没有这条工作流：{short(data, flow.file)}（kg workflow --list 看有哪些）"])
    task = task_layer.create(root, data, name.strip(), workflow.strip())
    result = task_status(root, data, name.strip())
    result.lines.insert(0, f"起了：{short(data, task.file)}")
    return result


def task_status(root: Path, data: Path, name: str) -> Result:
    if not name.strip():
        return Result(ok=False, lines=["请先选一件任务（kg task --list 看有哪些）"])
    task = task_layer.open_task(root, data, name)
    if not task.exists():
        return Result(ok=False, lines=[f"没有这件任务：{short(data, task.file)}"])
    done = task.done()
    result = Result(columns=("步骤", "状态"), lines=[f"任务：{task.name}"])
    result.lines.append(f"  开工：{task.start() or '（没记）'}")
    result.lines.append(f"  工作流：{task.workflow_name()}——{task.workflow().description}")
    result.lines.append(f"  步骤：{len(task.steps())} 个")
    for step in task.steps():
        state = "✓" if step.name in done else "—"
        result.rows.append((step.name, state))
        result.lines.append(f"  {state} {step.name}")
    result.lines.append(task_layer.state_line(task))
    result.lines.append(f"指令：{short(data, task.file)}")
    result.lines.append(f"产物：{short(data, task.artifact(task_layer.REPORT))}、{short(data, task.artifact(task_layer.JOURNAL))}　流水：{short(data, task.artifact(task_layer.LOG))}")
    events = task.events()[-5:]
    if events:
        result.lines.append("流水（最近五条）：")
        result.lines += [f"  {e['at']}　{e['step']}　{e['detail']}" for e in events]
    return result


def task_list(root: Path, data: Path) -> Result:
    found = task_layer.listing(root, data)
    result = Result(columns=("任务", "工作流", "下一步"))
    for task in found:
        step = task.next_step()
        result.rows.append((task.name, task.workflow_name(), step.name if step else "走完"))
        result.lines.append(f"{task.name:24} 工作流 {task.workflow_name()}　下一步：{step.name if step else '走完'}")
    if not found:
        result.lines = ["还没有任务：kg task --new <名字> --workflow <工作流>"]
    return result


def task_step(root: Path, data: Path, name: str, step: str = "", note: str = "", auto: bool = False) -> Result:
    """走一步：能让 AI 跑的交给 AI（auto），然后跑判据、记账。"""
    task = task_layer.open_task(root, data, name)
    if not task.exists():
        return Result(ok=False, lines=[f"没有这件任务：{short(data, task.file)}"])
    if not step.strip():
        if not auto:
            return Result(ok=False, lines=["请给步骤名（kg task <名字> 看有哪些步骤）"])
        nxt = task.next_step()
        if nxt is None:
            return Result(lines=["所有步骤都走过了"])
        step = nxt.name
    ok, lines, rows = task_layer.execute(task, root, step.strip(), note, auto=auto)
    result = Result(ok=ok, lines=lines, columns=MECHANICAL, rows=rows)
    result.lines.append(task_layer.state_line(task))
    return result


def task_journal(root: Path, data: Path, name: str, words: str) -> Result:
    task = task_layer.open_task(root, data, name)
    if not task.exists():
        return Result(ok=False, lines=[f"没有这件任务：{short(data, task.file)}"])
    if not words.strip():
        return Result(ok=False, lines=[f"日志要人来写：{short(data, task.artifact(task_layer.JOURNAL))}"])
    task_layer.narrate(task, words)
    return Result(lines=[f"日志记下一段：{short(data, task.artifact(task_layer.JOURNAL))}", task_layer.state_line(task)])
