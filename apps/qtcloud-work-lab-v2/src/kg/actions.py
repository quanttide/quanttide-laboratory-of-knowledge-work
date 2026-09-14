"""动作：命令行要做的每一件事。

每个动作返回一个 Result——`ok` 通不通，`lines` 是要打印的话，`columns` / `rows` 是同一
份表格。算法只在这里写一遍。模型会抛错（schema 不合、撞名、有账不销），这里兜住、转成
不通的结果。
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import artifacts, assets as assets_layer, catalog as catalog_layer, events, execute, material as material_layer, workorder
from . import workflow as flow


@dataclass
class Result:
    ok: bool = True
    lines: list[str] = field(default_factory=list)
    columns: tuple[str, ...] = ()
    rows: list[tuple[str, ...]] = field(default_factory=list)


def short(workspace, path: Path) -> str:
    path = Path(path)
    return str(path.relative_to(workspace.root)) if path.is_relative_to(workspace.root) else str(path)


def fail(*errors) -> Result:
    return Result(ok=False, lines=[str(error) for error in errors if str(error)])


def _guard(action) -> Result:
    try:
        return action()
    except (flow.WorkflowError, workorder.OrderError, ValueError, FileNotFoundError, FileExistsError) as error:
        return fail(error)


# ---- 工作流 ----


def workflow_new(workspace, name: str, steps: list[str], description: str = "") -> Result:
    def action() -> Result:
        payload = flow.create(workspace, name, steps, description)
        events.workflow_created(workspace, payload)
        result = workflow_show(workspace, payload["name"])
        result.lines.insert(0, f"写下工作流：{short(workspace, flow.file_for(workspace, payload['name']))}")
        return result

    return _guard(action)


def workflow_show(workspace, name: str) -> Result:
    def action() -> Result:
        payload = flow.read(workspace, name)
        result = Result(columns=("步骤", "谁做", "判据"), lines=[f"工作流：{payload['name']}（{short(workspace, flow.file_for(workspace, name))}）"])
        result.lines.append(f"  id：{payload['id']}")
        if payload.get("description"):
            result.lines.append(f"  描述：{payload['description']}")
        for item in flow.steps(payload):
            counts = f"{len(flow.of(item, flow.RULE))} rule / {len(flow.of(item, flow.AGENT))} agent / {len(flow.of(item, flow.HUMAN))} human"
            result.rows.append((item["name"], item.get("executor", flow.AGENT), counts))
            result.lines.append(f"  {item['name']}（{item.get('executor', flow.AGENT)}）：{item['description']}")
            for criterion in item.get("criteria", []):
                result.lines.append(f"      {criterion.get('executor')}：{criterion.get('description', '')}")
        return result

    return _guard(action)


def workflow_list(workspace) -> Result:
    def action() -> Result:
        found = flow.listing(workspace)
        result = Result(columns=("工作流", "步骤", "位置"))
        for payload in found:
            names = "、".join(item["name"] for item in flow.steps(payload))
            result.rows.append((payload["name"], names, short(workspace, flow.file_for(workspace, payload["name"]))))
            result.lines.append(f"{payload['name']:24} 步骤：{names}")
        if not found:
            result.lines = ["还没有工作流：kg workflow create <名字> --steps 甲,乙"]
        return result

    return _guard(action)


def workflow_check(workspace, name: str) -> Result:
    def action() -> Result:
        problems = flow.check(workspace, name)
        if problems:
            return Result(ok=False, columns=("问题",), lines=[f"定义核对：{name} 有 {len(problems)} 处要改"] + [f"  {item}" for item in problems], rows=[(item,) for item in problems])
        return Result(lines=[f"定义核对通过：{name}——判据路径都在区内，描述提到的小节都有 contains 判据覆盖。"])

    return _guard(action)


def workflow_export(workspace, name: str, target: Path) -> Result:
    def action() -> Result:
        saved = flow.export(workspace, name, target)
        payload = flow.read(workspace, name)
        return Result(lines=[f"已导出：{saved}（步骤 {len(flow.steps(payload))} 个，原样带走）"])

    return _guard(action)


def workflow_import(workspace, source: Path, name: str = "") -> Result:
    def action() -> Result:
        payload = flow.import_(workspace, source, name)
        events.workflow_created(workspace, payload)
        return Result(lines=[f"已导入：{short(workspace, flow.file_for(workspace, payload['name']))}（步骤 {len(flow.steps(payload))} 个）"])

    return _guard(action)


# ---- 工单 ----


def order_new(workspace, name: str, workflow: str, description: str = "") -> Result:
    def action() -> Result:
        order = workorder.create(workspace, name, workflow, description)
        events.workorder_created(workspace, order.payload)
        result = order_show(workspace, order.name)
        result.lines.insert(0, f"开了工单：{short(workspace, order.file)}")
        return result

    return _guard(action)


def order_show(workspace, name: str) -> Result:
    def action() -> Result:
        order = workorder.read(workspace, name)
        payload = order.workflow()
        done = workorder.done_steps(order)
        result = Result(columns=("步骤", "状态"), lines=[f"工单：{order.name}（{short(workspace, order.file)}）"])
        result.lines.append(f"  id：{order.id}")
        result.lines.append(f"  工作流：{payload['name']}（{order.workflow_id}）")
        result.lines.append(f"  开工：{order.created_at}")
        if order.description:
            result.lines.append(f"  描述：{order.description}")
        for item in order.steps():
            state = "✓" if item["name"] in done else "—"
            result.rows.append((item["name"], state))
            result.lines.append(f"  {state} {item['name']}")
        result.lines.append(_state_line(order))
        gates = workorder.pending_gates(order)
        result.lines += [f"  闸门：{note}" for note in gates]
        if order.records:
            result.lines.append("流水：")
            for record in order.records:
                mark = "✓" if record.get("is_succeeded") else "✗"
                result.lines.append(f"  {record['seq']:>3}  {record['created_at']}  {mark} {record['step']}　{record['description']}")
        return result

    return _guard(action)


def order_list(workspace, workflow: str = "", as_json: bool = False) -> Result:
    def action() -> Result:
        found = workorder.listing(workspace, workflow)
        if as_json:
            payload = [
                {
                    "name": order.name,
                    "workflow": order.workflow_name(),
                    "workflow_id": order.workflow_id,
                    "progress": workorder.progress(order),
                    "finished": workorder.finished(order),
                }
                for order in found
            ]
            return Result(lines=[json.dumps(payload, ensure_ascii=False, indent=2)])
        result = Result(columns=("工单", "工作流", "进度", "下一步"))
        for order in found:
            step = workorder.next_step(order)
            result.rows.append((order.name, order.workflow_name(), workorder.progress(order), step["name"] if step else "走完"))
            result.lines.append(f"{order.name:24} {order.workflow_name()}　{workorder.progress(order)}　下一步：{step['name'] if step else '走完'}")
        if not found:
            result.lines = ["还没有工单：kg order create <名字> --workflow <工作流>"]
        return result

    return _guard(action)


def order_delete(workspace, name: str) -> Result:
    def action() -> Result:
        workorder.delete(workspace, name)
        return Result(lines=[f"删了白纸：{short(workspace, workorder.file_for(workspace, name))}"])

    return _guard(action)


def order_next(workspace, name: str, note: str = "") -> Result:
    def action() -> Result:
        order = workorder.read(workspace, name)
        step = workorder.next_step(order)
        if step is None:
            return Result(lines=["所有步骤都走过了。"])
        ok, lines, rows, record = execute.walk(order, step, note)
        if record is not None:
            events.work_recorded(workspace, order.payload, record)
        result = Result(ok=ok, lines=lines, columns=("判据", "结论", "说明"), rows=rows)
        result.lines.append(_state_line(workorder.read(workspace, name)))
        return result

    return _guard(action)


def order_done(workspace, name: str, step: str, note: str = "") -> Result:
    def action() -> Result:
        order = workorder.read(workspace, name)
        if not step.strip():
            return fail(f"请给步骤名（看 {short(workspace, order.file)}）")
        found = order.step(step.strip())
        if found is None:
            return fail(f"所引工作流里没有这一步：{step}")
        ok, rows, record = execute.record_by_human(order, found, note)
        events.work_recorded(workspace, order.payload, record)
        result = Result(ok=ok, lines=[f"{'✓' if ok else '✗'} {found['name']}：{record['description']}"], columns=("判据", "结论", "说明"), rows=rows)
        result.lines.append(_state_line(workorder.read(workspace, name)))
        return result

    return _guard(action)


def order_journal(workspace, name: str, words: str) -> Result:
    def action() -> Result:
        order = workorder.read(workspace, name)
        if not words.strip():
            return fail(f"日志要人来写：{short(workspace, artifacts.journal_path(workspace, order.name))}")
        path = artifacts.write_journal(workspace, order.name, words)
        return Result(lines=[f"日志记下一段：{short(workspace, path)}"])

    return _guard(action)


def _state_line(order: workorder.Order) -> str:
    if not order.steps():
        return "这条工作流没有步骤——在定义里写 steps"
    step = workorder.next_step(order)
    if step is None:
        return f"走完了：{len(order.steps())} 个步骤都过了。"
    return f"进度：{workorder.progress(order)}　下一步：{step['name']}"


# ---- 工作区（实验室自留：规格未规定，按 v1 原样保留）----


def catalog(workspace) -> Result:
    """看目录：按资产表清点工作区里实际有什么。"""
    found = catalog_layer.build(workspace.root)
    result = Result(columns=("种类", "路径"))
    for entry in found.entries:
        rel = short(workspace, entry.path)
        result.lines.append(f"[{entry.kind}] {rel}")
        result.rows.append((entry.kind, rel))
    return result


def catalog_payload(workspace) -> dict:
    found = catalog_layer.build(workspace.root)
    return {
        "root": workspace.root.name,
        "count": len(found.entries),
        "entries": [{"kind": entry.kind, "path": short(workspace, entry.path), "names": sorted(entry.names)} for entry in found.entries],
    }


def audit(workspace, make: bool = False) -> Result:
    """审计工作区：资产表有而工作区无、工作区有而资产表无；make 为真则补建缺的格子。"""
    root = workspace.root
    missing = assets_layer.missing(root)
    unregistered = catalog_layer.build(root).unregistered(root)
    made = assets_layer.make(root, missing) if make else []
    missing = assets_layer.missing(root)
    unregistered = catalog_layer.build(root).unregistered(root)
    ok = not (missing or unregistered)
    result = Result(
        ok=ok,
        columns=("问题", "说明"),
        rows=[("缺资产", f"{asset.kind}（{asset.name}）") for asset in missing] + [("未登记", short(workspace, path)) for path in unregistered],
    )
    result.lines = [f"补建：{short(workspace, path)}" for path in made]
    result.lines += [f"{kind}：{what}" for kind, what in result.rows]
    if ok:
        result.lines.append("审计通过：二十格齐备，无未登记目录。")
    elif unregistered and not missing:
        result.lines.append("未登记的目录要么属于某一格（改资产表），要么不该在这儿。")
    return result


def audit_payload(workspace) -> dict:
    root = workspace.root
    missing = assets_layer.missing(root)
    unregistered = catalog_layer.build(root).unregistered(root)
    return {
        "root": root.name,
        "result": "通过" if not (missing or unregistered) else "有问题",
        "missing": [{"kind": asset.kind, "name": asset.name} for asset in missing],
        "unregistered": [short(workspace, path) for path in unregistered],
    }


def find(workspace, name: str, show: bool = False) -> Result:
    """按名找文档：认文件名与中文标题。"""
    if not name.strip():
        return fail("请填要找的名字")
    matches = catalog_layer.build(workspace.root).find(name)
    if not matches:
        return fail(f"未找到：{name}")
    result = Result(columns=("种类", "路径"))
    for entry in matches:
        rel = short(workspace, entry.path)
        result.lines.append(f"[{entry.kind}] {rel}")
        result.rows.append((entry.kind, rel))
        if show:
            if entry.path.is_dir():
                result.lines.append("  （目录）" + "、".join(sorted(path.name for path in entry.path.iterdir() if not path.name.startswith("."))))
            else:
                result.lines.append(entry.path.read_text(encoding="utf-8").rstrip())
    return result


def material(workspace, paths: list[str] | None = None) -> Result:
    """看材料：类型、内容、来源、时间，阶段由位置承担。"""
    found = material_layer.materials(workspace.root, paths)
    result = Result(columns=("材料", "类型", "阶段", "时间", "来源"))
    for rel, item in found:
        result.rows.append((rel, item.type, item.stage, item.created_at or "（缺）", item.source))
        result.lines.append(f"{rel:52} {item.type:5} {item.stage:5} {item.created_at or '（缺）':11} {item.source}")
        if item.missing:
            result.ok = False
            result.lines.append(f"缺字段：{rel}——{'、'.join(item.missing)}")
    if result.ok:
        result.lines.append("阶段由资产位置承担：日志是原始，其余是材料。")
    return result


def material_payload(workspace, paths: list[str] | None = None) -> dict:
    found = material_layer.materials(workspace.root, paths)
    return {"count": len(found), "materials": [{"path": rel, **vars(item)} for rel, item in found]}
