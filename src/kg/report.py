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
from . import workflow as flow_layer
from . import checks as checks_layer
from . import material as material_layer
from . import records

MECHANICAL = ("核对", "结论", "说明")
SECTIONS = ("段位", "结论")
STEPS = ("material", "instruction", "review", "output", "decision", "finish", "history")


@dataclass
class Result:
    ok: bool = True
    lines: list[str] = field(default_factory=list)
    columns: tuple[str, ...] = ()
    rows: list[tuple[str, ...]] = field(default_factory=list)


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


def new_record(target: Path, template: str, about: str = "") -> Result:
    if not str(target).strip():
        return Result(ok=False, lines=["请先填写到哪个文件"])
    if target.exists():
        return Result(ok=False, lines=[f"已存在：{target}"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(records.contract_template(about) if template == "契约" else template, encoding="utf-8")
    return Result(lines=[f"已写：{target}"] + ([f"以 `{about}` 为题"] if about else []))


def new_instruction(target: Path, goal: str = "") -> Result:
    if not str(target).strip():
        return Result(ok=False, lines=["请先写到哪个文件"])
    if target.exists():
        return Result(ok=False, lines=[f"已存在：{target}"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(records.task_template(target.stem, goal), encoding="utf-8")
    return Result(lines=[f"已写：{target}"])


def new_report(target: Path, title: str = "") -> Result:
    return new_record(target, records.report_template(title), title)


def audit_instruction(root: Path, target: Path, into: Path | None = None) -> Result:
    if not str(target).strip():
        return Result(ok=False, lines=["请先选指令文件"])
    if not target.is_file():
        return Result(ok=False, lines=[f"没有这个文件：{target}"])
    missing = records.missing_sections(target, records.TASK_SECTIONS)
    result = Result(ok=not missing, columns=MECHANICAL)
    result.lines += [f"  {'✓' if name not in missing else '✗'} {name}" for name in records.TASK_SECTIONS]
    if missing:
        result.lines.append(f"指令不完整：缺 {'、'.join(missing)}")
        return result
    empty = [name for name in ("步骤", "验收") if not records.read_sections(target).get(name)]
    if empty:
        result.ok = False
        result.lines.append(f"指令还空着：{'、'.join(empty)}——三段齐全才算写完")
        return result
    result.lines.append("指令完整。")
    results, gates = checks_layer.run(root, checks_layer.parse(target.read_text(encoding="utf-8")))
    result.rows = [(item.note, "✓" if ok else "✗", detail) for item, ok, detail in results]
    result.rows += [(item.note, "闸门", "留给人拍板") for item in gates]
    result.ok = all(ok for _, ok, _ in results)
    if results:
        result.lines.append("机械核对：")
        result.lines += [f"  {'✓' if ok else '✗'} {item.note}（{detail}）" for item, ok, detail in results]
    if gates:
        result.lines.append("闸门项（留给人拍板）：")
        result.lines += [f"  - {item.note}" for item in gates]
    if into:
        written = write_review(into, results, gates)
        result.lines.append(f"已写审查者报告：{written}")
    return result


def write_review(target: Path, results: list, gates: list) -> Path:
    """把机械核对与闸门项写进案卷的「审查者报告」一节（没有案卷就先起一份）。"""
    if not target.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(records.report_template(target.stem), encoding="utf-8")
    body = [f"- {'✓' if ok else '✗'} {item.note}" for item, ok, _ in results]
    body += [f"- ⧗ {item.note}（留给闸门）" for item in gates]
    lines = target.read_text(encoding="utf-8").splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("## ") and line[3:].strip() == "审查者报告"), None)
    if start is None:
        lines += ["", "## 审查者报告", "", *body]
    else:
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        lines = lines[: start + 1] + [""] + body + [""] + lines[end:]
    target.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return target


def audit_report(target: Path) -> Result:
    if not str(target).strip():
        return Result(ok=False, lines=["请先选报告文件"])
    if not target.is_file():
        return Result(ok=False, lines=[f"没有这个文件：{target}"])
    missing = records.missing_sections(target, records.REPORT_SECTIONS)
    result = Result(ok=not missing, columns=SECTIONS)
    result.rows = [(name, "✓" if name not in missing else "✗") for name in records.REPORT_SECTIONS]
    result.lines += [f"  {mark} {name}" for name, mark in result.rows]
    result.lines.append("报告完整。" if not missing else f"报告不完整：缺 {'、'.join(missing)}")
    return result


# ---- 主轴：任务 ----

STEP_COLUMNS = ("段", "状态")


def run_new(root: Path, name: str, data: Path, runs: str | None = None, about: str = "") -> Result:
    if not name.strip():
        return Result(ok=False, lines=["请先给这个任务起个名字"])
    run = flow_layer.create(root, name.strip(), data, runs, about)
    return Result(lines=[f"起了：{run.dir}", flow_layer.state_line(run)])


def run_status(root: Path, name: str, data: Path, runs: str | None = None) -> Result:
    if not name.strip():
        return Result(ok=False, lines=["请先选任务（kg run --list 看有哪些）"])
    run = flow_layer.open_run(root, name, data, runs)
    if not run.exists():
        return Result(ok=False, lines=[f"没有这一次运行：{run.dir}"])
    state = run.stages()
    result = Result(columns=STEP_COLUMNS)
    result.rows = [(stage, "✓" if state[stage] else "—") for stage in flow_layer.STAGES]
    result.lines = [f"运行：{run.name}（{run.dir}）"]
    result.lines += [f"  {'✓' if state[s] else '—'} {s}" for s in flow_layer.STAGES]
    result.lines.append(flow_layer.state_line(run))
    result.lines.append(f"报告：{short(root, run.record_file(flow_layer.REPORT))}　历史：{short(root, run.record_file(flow_layer.HISTORY))}")
    events = run.events()[-5:]
    if events:
        result.lines.append("流水（最近五条）：")
        result.lines += [f"  {e['at']}　{e['kind']}　{e['detail']}" for e in events]
    return result


def run_list(root: Path, data: Path, runs: str | None = None) -> Result:
    found = flow_layer.listing(root, data, runs)
    result = Result(columns=("任务", "下一步", "位置"))
    for run in found:
        action, _ = run.next_action()
        result.rows.append((run.name, action, short(root, run.dir)))
        result.lines.append(f"{run.name:24} 下一步：{action}")
    if not found:
        result.lines = ["还没有运行：kg run --new <名字>"]
    return result


def run_step(root: Path, name: str, action: str, value: str = "", data: Path | None = None, runs: str | None = None) -> Result:
    """在任务上走一步；事实自动记进它的流水。"""
    data = data or flow_layer.lab_data()
    run = flow_layer.open_run(root, name, data, runs)
    if not run.exists():
        return Result(ok=False, lines=[f"没有这一次运行：{run.dir}"])

    if action == "material":
        if not value.strip():
            return Result(ok=False, lines=["请给材料一个路径"])
        path = here(root, value.strip())
        if not path.is_file():
            return Result(ok=False, lines=[f"没有这个文件：{value}"])
        mat = material_layer.as_material(root, path)
        rel = short(root, path)
        fields = f"{mat.type} / {mat.stage} / {mat.created_at or '（缺时间）'} / {mat.source}"
        flow_layer.add_material(run, rel, fields)
        message = f"记下材料：{rel}"
    elif action == "instruction":
        goal = value.strip() or (run.items(flow_layer.MATERIALS)[0].split("　")[0].strip("`") if run.items(flow_layer.MATERIALS) else "")
        flow_layer.write_instruction(run, goal)
        message = f"写出指令骨架：{short(root, run.file(flow_layer.TASK_FILE))}——步骤与验收要你填"
    elif action == "review":
        ok, lines = flow_layer.review(run, root)
        message = f"核对完了，审查者报告已写进 {short(root, run.record_file(flow_layer.REPORT))}" if ok else "核对没过：" + "；".join(lines[:2])
        task_after = run_status(root, name, data, runs)
        task_after.lines.insert(0, message)
        return task_after
    elif action == "output":
        if not value.strip():
            return Result(ok=False, lines=["请给产出一个路径"])
        path = here(root, value.strip())
        flow_layer.add_output(run, short(root, path))
        message = f"记下产出：{short(root, path)}"
    elif action == "decision":
        if not value.strip():
            return Result(ok=False, lines=["裁决得写句话：谁拍的板、决定是什么"])
        flow_layer.decide(run, value.strip())
        message = "裁决已记入报告"
    elif action == "finish":
        items = flow_layer.finish(run)
        message = f"成果已收束进报告：{len(items)} 项"
    elif action == "history":
        if not value.strip():
            return Result(ok=False, lines=[f"历史要你来写：{short(root, run.record_file(flow_layer.HISTORY))}"])
        flow_layer.narrate(run, value)
        message = f"历史记下一段：{short(root, run.record_file(flow_layer.HISTORY))}"
    else:
        return Result(ok=False, lines=[f"不认得这一步：{action}"])

    state = run_status(root, name, data, runs)
    state.lines.insert(0, message)
    return state
