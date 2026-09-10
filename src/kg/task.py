"""任务：工作流的一次执行实例。

规格：任务（Task）＝过程的一次执行实例；它跑的是某条工作流（workflow.py）。

<数据仓>/
├── tasks/<任务>.yaml           这一次的指令：跑哪条工作流、要什么
└── artifacts/                  产物按类型分家，按任务名命名
    ├── report/<任务>.md        报告（事件）：执行记录 + 闸门项，机器写
    ├── history/<任务>.md       历史（叙事）：人写
    └── log/<任务>.jsonl        流水：哪一步、什么时候、结果如何、一句话

任务是 YAML（跑哪条工作流、要什么），定义是 YAML（步骤、执行者、判据——见 workflow.py）；
流水是 JSONL、报告与历史是 Markdown——那是记录与叙事，读物。
走一步：执行者是 AI 的交给 pi 跑，然后程序自己判机械判据、把闸门项列给人，事实记进流水与报告。
"""

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

from . import checks as checks_layer
from . import records
from . import workflow as workflow_layer

LOG = "log"
REPORT = "report"
HISTORY = "history"
SUFFIX = {REPORT: ".md", HISTORY: ".md", LOG: ".jsonl"}
def dump(data: dict) -> str:
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=200)


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


@dataclass
class Task:
    """一次执行：跑某条工作流，有自己的流水与产物。"""

    root: Path  # 工作区：读材料、核判据
    data: Path  # 数据仓
    name: str

    @property
    def file(self) -> Path:
        return self.data / "tasks" / f"{self.name}.yaml"

    @property
    def artifacts_dir(self) -> Path:
        return self.data / "artifacts"

    def artifact(self, kind: str) -> Path:
        """程序的三样记账：一类一目录（report / history / log），按任务名放。"""
        return self.artifacts_dir / kind / f"{self.name}{SUFFIX[kind]}"

    def exists(self) -> bool:
        return self.file.is_file()

    def payload(self) -> dict:
        if not self.file.is_file():
            return {}
        try:
            loaded = yaml.safe_load(self.file.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            return {}
        return loaded if isinstance(loaded, dict) else {}

    def goal(self) -> str:
        return str(self.payload().get("goal", "")).strip()

    def workflow_name(self) -> str:
        return str(self.payload().get("workflow", "")).strip()

    def workflow(self) -> workflow_layer.Workflow:
        return workflow_layer.open_workflow(self.data, self.workflow_name())

    def steps(self) -> list[workflow_layer.Step]:
        return self.workflow().steps()

    def events(self) -> list[dict]:
        path = self.artifact(LOG)
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.is_file() else []

    def done(self) -> set[str]:
        """哪些步骤走过了：流水里成功执行过的、且名字确实是工作流上的步骤。"""
        names = {step.name for step in self.steps()}
        return {event["step"] for event in self.events() if event.get("ok") and event.get("step") in names}

    def next_step(self) -> workflow_layer.Step | None:
        done = self.done()
        return next((step for step in self.steps() if step.name not in done), None)

    def record(self, step: str, detail: str, ok: bool = True) -> None:
        self.artifact(LOG).parent.mkdir(parents=True, exist_ok=True)
        with self.artifact(LOG).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"at": now(), "step": step, "detail": detail, "ok": ok}, ensure_ascii=False) + "\n")

    def relative(self, path: Path) -> str:
        return str(path.relative_to(self.data)) if path.is_relative_to(self.data) else str(path)


def create(root: Path, data: Path, name: str, workflow_name: str, about: str = "") -> Task:
    """起一件任务：写下指令（跑哪条工作流、要什么），备好产物三家。"""
    task = Task(root, Path(data), name)
    task.file.parent.mkdir(parents=True, exist_ok=True)
    task.artifacts_dir.mkdir(parents=True, exist_ok=True)
    for kind in (REPORT, HISTORY, LOG):
        task.artifact(kind).parent.mkdir(parents=True, exist_ok=True)
    if not task.file.is_file():
        task.file.write_text(dump({"name": name, "workflow": workflow_name, "goal": about or "<这一次要什么，一句话>"}), encoding="utf-8")
    if not task.artifact(REPORT).is_file():
        task.artifact(REPORT).write_text(records.report_template(name), encoding="utf-8")
    if not task.artifact(HISTORY).is_file():
        task.artifact(HISTORY).write_text(records.history_template(name), encoding="utf-8")
    task.record("开工", about or f"跑工作流：{workflow_name}")
    return task


def open_task(root: Path, data: Path, name: str) -> Task:
    return Task(root, Path(data), name)


def listing(root: Path, data: Path) -> list[Task]:
    base = Path(data) / "tasks"
    return [Task(root, Path(data), path.stem) for path in sorted(base.glob("*.yaml"))] if base.is_dir() else []


def prompt_for(task: Task, step: workflow_layer.Step) -> str:
    """交给 AI 的那一段话：这一步做什么、判据是什么、产物落在哪。"""
    steps = "、".join(item.name for item in task.steps())
    return f"""你在按一条工作流走一步。只做这一步，做完就停。

工作区：{task.root}
数据仓：{task.data}
任务：{task.name}（目标：{task.goal() or "（没写）"}）
工作流：{task.workflow_name()}（步骤：{steps}）
这一步：{step.name}
做什么：
{step.description}

判据（程序随后自己核对，你不能改判据、也不许改判据文件）：
{criteria_text(step)}

本任务的三样产物（报告 / 历史 / 流水，都是可维护的产物，不是程序的临时文件）：
  报告：{task.relative(task.artifact(REPORT))}（程序只维护「执行记录」与「闸门项」两节，其余节归你写）
  历史：{task.relative(task.artifact(HISTORY))}
  流水：{task.relative(task.artifact(LOG))}
工作流里用 {{{{report}}}} / {{{{history}}}} / {{{{log}}}} 指这三样；产物内容写进报告，别动程序那两节。
规矩：数据只写数据仓；工作区里只动「做什么」点名的东西。最后用一句话说明你做了什么。
"""


def run_ai(prompt: str, root: Path, timeout: int = 900) -> tuple[bool, str]:
    """把这一步交给 AI 跑：非交互调 pi。测试里会替换这个函数，别在测试里真调。"""
    try:
        done = subprocess.run(["pi", "-p", "--no-session", prompt], cwd=root, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return False, "没找到 pi"
    except subprocess.TimeoutExpired:
        return False, "pi 超时"
    out = (done.stdout or "").strip() or (done.stderr or "").strip()
    return done.returncode == 0, out


def criteria_text(step: workflow_layer.Step) -> str:
    lines = [f"- {criterion.get('executor')}：{checks_layer.description_of(criterion) or criterion.get('description', '')}" for criterion in step.criteria]
    return "\n".join(lines) or "（这一步没有判据）"


def judge_prompt(task: "Task", step: workflow_layer.Step, criteria: list[dict]) -> str:
    """交给智能体审的那一段话：产物 + 判准，逐条回答。"""
    listed = "\n".join(f"{index}. {criterion.get('description')}" for index, criterion in enumerate(criteria, start=1))
    return f"""你是审查者，不是执行者。别改产物、别改判据文件。

工作区：{task.root}
要审的东西：这一步的产物在 {task.artifacts_dir}（也可以看工作区里相关文件）
这一步做什么：{step.description}

判准（逐条判）：
{listed}

对每条输出一行，格式只能是「序号. 通过 — 一句话理由」或「序号. 不通过 — 一句话理由」，最后不要写别的。
"""


def judge_by_ai(task: "Task", step: workflow_layer.Step, criteria: list[dict], root: Path) -> list[tuple[str, str, str]]:
    """让智能体按判准审一遍；返回（说明，结论，理由）。"""
    ran, out = run_ai(judge_prompt(task, step, criteria), root)
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
    task.record(f"{step.name}·审", f"AI 审查（同一模型）：{'；'.join(f'{note}→{verdict}' for note, verdict, _ in rows)}", ok=all(verdict == "✓" for _, verdict, _ in rows))
    return rows


def one_line(text: str, limit: int = 80) -> str:
    line = next((line.strip() for line in reversed(text.strip().splitlines()) if line.strip()), "")
    return line[:limit]


PLACEHOLDER = re.compile(r"\{\{(?P<kind>report|history|log|artifacts)\}\}")


def expand(task: Task, value: str) -> str:
    """把 {{report}} / {{history}} / {{log}} / {{artifacts}} 换成这个任务的产物路径（相对工作区根，跨仓则绝对）。"""
    def one(match: re.Match) -> str:
        kind = match.group("kind")
        path = task.artifacts_dir if kind == "artifacts" else task.artifact(kind)
        # 判据按工作区根解析，占位也给工作区根视角的路径
        return str(path.relative_to(task.root)) if path.is_relative_to(task.root) else str(path)

    return PLACEHOLDER.sub(one, value)


def expanded_criteria(task: Task, criteria: list[dict]) -> list[dict]:
    """判据里的占位先换成本次任务的真实路径，再去跑。"""
    return [{key: expand(task, value) if isinstance(value, str) else value for key, value in criterion.items()} for criterion in criteria]


def execute(task: Task, root: Path, step: str, note: str = "", auto: bool = False) -> tuple[bool, list[str], list[tuple[str, str, str]]]:
    """走一步：能让 AI 跑的交给 AI，然后跑判据、记账、写报告。"""
    found = task.workflow().step(step)
    if found is None:
        return False, [f"工作流里没有这一步：{step}"], []
    lines: list[str] = []
    if auto and not found.human:
        lines.append(f"{found.name}：交给 AI（{found.executor}）跑")
        ran, out = run_ai(prompt_for(task, found), root)
        lines.append(f"  AI {'跑完了' if ran else '跑不动'}：{one_line(out) if out else '（没输出）'}")
        task.record(found.name, f"AI 执行：{one_line(out) if out else '（没输出）'}", ok=ran)
        if not ran:
            write_report(task, [])
            lines.append("  （AI 没跑成，这一步不算过；修好再来）")
            return False, lines, []
    elif found.human and auto:
        lines.append(f"{found.name}：这一步的执行者是人（{found.executor}）——轮到你，做完用 kg task <名字> --done {found.name}")
        return True, lines, []
    results, _ = checks_layer.run(root, checks_layer.items_of(expanded_criteria(task, found.rules)))
    judged = judge_by_ai(task, found, found.agents, root) if (auto and found.agents) else [
        (str(criterion.get("description", "")).strip(), "待判", "没跑智能体（人为地记一步）") for criterion in found.agents
    ]
    gates = [str(criterion.get("description", "")).strip() for criterion in found.gates]
    ok = all(passed for _, passed, _ in results) and all(verdict == "✓" for _, verdict, _ in judged)
    detail = note.strip() or ("；".join(item.description for item, _, _ in results) if results else "做完")
    if not (auto and not found.human):
        task.record(step, detail, ok=ok)
    write_report(task, gates + [note for note, verdict, _ in judged if verdict != "✓"])
    lines.append(f"{'✓' if ok else '✗'} {step}：{detail}")
    lines += [f"  {'✓' if passed else '✗'} {item.description}（{spec}）" for item, passed, spec in results]
    lines += [f"  {verdict} {note}（{reason}）" for note, verdict, reason in judged]
    lines += [f"  ⧗ {note}（留给人）" for note in gates]
    rows = [(item.description, "✓" if passed else "✗", spec) for item, passed, spec in results]
    rows += [(note, verdict, reason) for note, verdict, reason in judged]
    return ok, lines, rows + [(note, "闸门", "留给人拍板") for note in gates]


SECTIONS = ("执行记录", "闸门项")   # 报告里归程序管的两节；别的节（人 / AI 写的产物）原样留着


def write_report(task: Task, gates: list[str]) -> Path:
    """报告：程序只动「执行记录」与「闸门项」两节，其余节（产物内容）保留。"""
    path = task.artifact(REPORT)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    if not text.strip():
        text = f"# 报告：{task.name}\n"
    records = [f"- {'✓' if event.get('ok') else '✗'} {event['at']}　{event['step']}　{event['detail']}" for event in task.events()]
    gates_lines = [f"- ⧗ {note}（留给人 / 待判）" for note in gates] or ["- （暂无）"]
    text = replace_section(text, "执行记录", records)
    text = replace_section(text, "闸门项", gates_lines)
    path.write_text(text, encoding="utf-8")
    return path


def replace_section(text: str, title: str, body: list[str]) -> str:
    """把某一节的正文换掉，其它节原样保留；没有这一节就补在后面。"""
    head, marker, tail = text.partition(f"## {title}")
    block = f"## {title}\n\n" + "\n".join(body) + "\n"
    if not marker:
        return text.rstrip() + "\n\n" + block
    _, _, rest = tail.partition("## ")
    return head + block + ("\n## " + rest if rest else "")


def narrate(task: Task, words: str) -> None:
    """历史只收叙事：一段一段往下写。"""
    path = task.artifact(HISTORY)
    text = path.read_text(encoding="utf-8") if path.is_file() else records.history_template(task.name)
    text = "\n".join(line for line in text.splitlines() if not (line.strip().startswith("（") and line.strip().endswith("）"))).rstrip()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{text}\n\n{words.strip()}\n", encoding="utf-8")
    task.record("历史", words.strip()[:40])


def state_line(task: Task) -> str:
    steps = task.steps()
    if not steps:
        return f"这条工作流没有步骤——在 workflows/{task.workflow_name()}.md 里写「### 步骤名」"
    step = task.next_step()
    return f"下一步：{step.name}" if step else f"{len(steps)} 个步骤都走过了"
