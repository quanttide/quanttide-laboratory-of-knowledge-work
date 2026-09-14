"""走一步：能让智能体跑的交给智能体，然后核 rule 判据，记一条工作记录。

规格：工作记录的 `is_succeeded` 来源与判据的 `executor` 一一对应——`rule` 机械比对、
`agent` 智能体审查、`human` 闸门放行（见 specification/process/work-record.md）。
闸门不落封面字段：带 `human` 判据的站，只能由人放行（`order done`）。
"""

import subprocess
from pathlib import Path

from . import checks as checks_layer
from . import ids, workorder

TYPES = ("rule", "agent", "human")


def one_line(text: str, limit: int = 80) -> str:
    line = next((item.strip() for item in reversed(text.strip().splitlines()) if item.strip()), "")
    return line[:limit]


def criteria_text(step: dict) -> str:
    lines = [
        f"- {criterion.get('executor')}：{checks_layer.description_of(criterion) or criterion.get('description', '')}"
        for criterion in step.get("criteria", [])
    ]
    return "\n".join(lines) or "（这一步没有判据）"


def prompt_for(order: workorder.Order, step: dict) -> str:
    """交给智能体的那一段话：这一步做什么、判据是什么、落点在哪。"""
    steps = "、".join(item["name"] for item in order.steps())
    return f"""你在按一条工作流走一步。只做这一步，做完就停。

工作区：{order.workspace.root}
工单：{order.name}（{order.description or '（没写描述）'}）
工作流：{order.workflow_name()}
步骤：{steps}
这一步：{step['name']}
做什么：
{step['description']}

判据（程序随后自己核对，你不能改判据、也不许改判据文件）：
{criteria_text(step)}

规矩：数据只写工作区；工作区里只动「做什么」点名的东西。最后用一句话说明你做了什么。
"""


def run_ai(prompt: str, root: Path, timeout: int = 900) -> tuple[bool, str]:
    """把这一步交给智能体跑：非交互调用 pi。测试里会替换这个函数，别在测试里真调。"""
    try:
        done = subprocess.run(["pi", "-p", "--no-session", prompt], cwd=root, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return False, "没找到 pi"
    except subprocess.TimeoutExpired:
        return False, "pi 超时"
    out = (done.stdout or "").strip() or (done.stderr or "").strip()
    return done.returncode == 0, out


def judge_prompt(order: workorder.Order, step: dict, criteria: list[dict]) -> str:
    """交给智能体审的那一段话：判准逐条回答。"""
    listed = "\n".join(f"{index}. {criterion.get('description')}" for index, criterion in enumerate(criteria, start=1))
    return f"""你是审查者，不是执行者。别改产物、别改判据文件。

工作区：{order.workspace.root}
要审的东西：这一步的产物与相关文件都在工作区内
这一步做什么：{step['description']}

判准（逐条判）：
{listed}

对每条输出一行，格式只能是「序号. 通过 — 一句话理由」或「序号. 不通过 — 一句话理由」，最后不要写别的。
"""


def judge_by_ai(order: workorder.Order, step: dict, criteria: list[dict]) -> list[tuple[str, str, str]]:
    """让智能体按判准审一遍；返回（说明，结论，理由）。"""
    ran, out = run_ai(judge_prompt(order, step, criteria), order.workspace.root)
    rows = []
    for index, criterion in enumerate(criteria, start=1):
        note = str(criterion.get("description", "")).strip()
        if not ran:
            rows.append((note, "待判", f"智能体没跑成：{one_line(out)}"))
            continue
        verdict, reason = "待判", one_line(out)
        for line in out.splitlines():
            stripped = line.strip()
            if stripped.startswith(f"{index}."):
                tail = stripped.split(".", 1)[1].strip()
                verdict = "✓" if tail.startswith("通过") else "✗" if tail.startswith("不通过") else "待判"
                reason = tail
                break
        rows.append((note, verdict, reason))
    return rows


def _evaluate(order: workorder.Order, step: dict, note: str, auto: bool) -> tuple[bool, list[str], list[tuple], dict | None]:
    root = order.workspace.root
    lines: list[str] = []
    criteria = step.get("criteria", [])
    rules = [item for item in criteria if item.get("executor") == "rule"]
    agents = [item for item in criteria if item.get("executor") == "agent"]
    gates = [item for item in criteria if item.get("executor") == "human"]

    if step.get("executor") == "human":
        lines.append(f"{step['name']}：这一步的执行者是人——轮到你，做完用 `order done {order.name} {step['name']}` 记一笔。")
        return True, lines, [], None

    if auto:
        lines.append(f"{step['name']}：交给智能体跑。")
        ran, out = run_ai(prompt_for(order, step), root)
        lines.append(f"  智能体{'跑完了' if ran else '跑不动'}：{one_line(out) if out else '（没输出）'}")
        if not ran:
            lines.append("  （没跑成，这一步不算过；修好再来。）")
            return False, lines, [], None

    results, _ = checks_layer.run(root, checks_layer.items_of(rules))
    if auto and agents:
        judged = judge_by_ai(order, step, agents)
    else:
        judged = [(str(item.get("description", "")).strip(), "待判", "没跑智能体（人记一笔）") for item in agents]

    passed = all(ok for _, ok, _ in results)
    if auto and agents:
        passed = passed and all(verdict == "✓" for _, verdict, _ in judged)
    detail = note.strip() or ("；".join(item.description for item, _, _ in results) if results else "做完")

    lines.append(f"{'✓' if passed else '✗'} {step['name']}：{detail}")
    lines += [f"  {'✓' if ok else '✗'} {item.description}（{spec}）" for item, ok, spec in results]
    lines += [f"  {verdict} {text}（{reason}）" for text, verdict, reason in judged]
    lines += [f"  ⧗ {str(item.get('description', '')).strip()}（留给人）" for item in gates]

    rows = [(item.description, "✓" if ok else "✗", spec) for item, ok, spec in results]
    rows += [(text, verdict, reason) for text, verdict, reason in judged]
    rows += [(str(item.get("description", "")).strip(), "闸门", "留给人拍板") for item in gates]

    if passed and gates and auto:
        lines.append(f"  这一步有闸门，等人放行：`order done {order.name} {step['name']}`")
        return True, lines, rows, None

    record = workorder.append(order, ids.new_id(), step["name"], detail, is_succeeded=passed)
    return passed, lines, rows, record


def walk(order: workorder.Order, step: dict, note: str = "") -> tuple[bool, list[str], list[tuple], dict | None]:
    """机器路径（`order next`）：智能体执行，程序核 rule 判据。"""
    return _evaluate(order, step, note, auto=True)


def record_by_human(order: workorder.Order, step: dict, note: str = "") -> tuple[bool, list[tuple], dict]:
    """人的路径（`order done`）：闸门放行，或人自己做完记一笔；程序仍核 rule 判据。"""
    results, _ = checks_layer.run(order.workspace.root, checks_layer.items_of(
        [item for item in step.get("criteria", []) if item.get("executor") == "rule"]
    ))
    ok = all(passed for _, passed, _ in results)
    detail = note.strip() or ("；".join(item.description for item, _, _ in results) if results else "人记一笔")
    record = workorder.append(order, ids.new_id(), step["name"], detail, is_succeeded=ok)
    rows = [(item.description, "✓" if passed else "✗", spec) for item, passed, spec in results]
    return ok, rows, record
