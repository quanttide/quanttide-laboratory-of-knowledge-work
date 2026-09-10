"""工作流：串联的工作步骤——过程的编排定义。

规格：工作流（Workflow）＝过程的编排定义；任务（Task）＝过程的一次执行实例（见 task.py）。

工作流落在 <数据仓>/workflows/<名字>.md：

  # 工作流：<名字>
  ## 步骤
  ### 定位
  - 做什么：把两边的源找齐
  - [ ] 机械：…在 `path:…`
  - [ ] 闸门：…

每个步骤自带执行者与验收判据：**默认交给 AI 跑**（`pi -p`），要人做的步骤显式写 `- 执行者：人`；
判据里机械的当场判、闸门的留给人。工作流只管编排与判据，执行是任务的事——同一个工作流可被多次执行。
"""

import re
from dataclasses import dataclass
from pathlib import Path

STEP = re.compile(r"^###\s+(?P<name>.+?)\s*$")


def lab_data() -> Path:
    """数据仓：实验室的 data/——工作纪律：所有数据放这里（见 AGENTS.md）。"""
    return Path(__file__).resolve().parents[2] / "data"


AI = "AI"
HUMAN = "人"
EXECUTOR = re.compile(r"^-\s*执行者[：:]\s*(.+?)\s*$")


@dataclass(frozen=True)
class Step:
    """一个工作步骤：叫什么、做什么、谁执行、怎么算完。

    默认交给 AI 跑；要人做的步骤必须显式写「- 执行者：人」。
    """

    name: str
    text: str

    @property
    def executor(self) -> str:
        for line in self.text.splitlines():
            if match := EXECUTOR.match(line.strip()):
                return match.group(1).strip()
        return AI

    @property
    def human(self) -> bool:
        return self.executor not in (AI, "ai", "AI 执行")

    @property
    def what(self) -> str:
        """做什么：判据行与执行者行之外的正文。"""
        keep = [line for line in self.text.splitlines() if not line.strip().startswith("- [") and not EXECUTOR.match(line.strip())]
        return "\n".join(keep).strip()

    @property
    def judges(self) -> str:
        return "\n".join(line for line in self.text.splitlines() if line.strip().startswith("- ["))


@dataclass
class Workflow:
    """过程的编排定义：一串步骤。"""

    data: Path
    name: str

    @property
    def file(self) -> Path:
        return self.data / "workflows" / f"{self.name}.md"

    def text(self) -> str:
        return self.file.read_text(encoding="utf-8") if self.file.is_file() else ""

    def exists(self) -> bool:
        return self.file.is_file()

    def steps(self) -> list[Step]:
        """步骤：按写进文件的顺序，每步连正文一起取下来。"""
        found: list[Step] = []
        for line in self.text().splitlines():
            if match := STEP.match(line):
                found.append(Step(match.group("name").strip(), ""))
            elif found:
                found[-1] = Step(found[-1].name, f"{found[-1].text}\n{line}".strip())
        return found

    def step(self, name: str) -> Step | None:
        return next((step for step in self.steps() if step.name == name), None)


def create(data: Path, name: str, steps: list[str], note: str = "") -> Workflow:
    """写下一条工作流：步骤串联，每步给一份验收骨架。"""
    flow = Workflow(Path(data), name)
    flow.file.parent.mkdir(parents=True, exist_ok=True)
    body = [f"# 工作流：{name}", "", note or "步骤串联：写清每步做什么、怎么算完。", "", "## 步骤", ""]
    for step in steps:
        body += [
            f"### {step}",
            "",
            f"- 做什么：<{step}这一步做什么>",
            f"- 执行者：{AI}",
            "- [ ] 机械：<能写成断言的> `path:data/journal/README.md`",
            "- [ ] 闸门：<只能人拍板的>",
            "",
        ]
    flow.file.write_text("\n".join(body).rstrip() + "\n", encoding="utf-8")
    return flow


def open_workflow(data: Path, name: str) -> Workflow:
    return Workflow(Path(data), name)


TITLE = re.compile(r"^#\s*工作流[：:]\s*(.*)$", re.M)


def export(flow: Workflow, target: Path) -> Path:
    """把一条工作流存成一份可带走的文件（原样，不改内容）。"""
    target = Path(target)
    if target.is_dir():
        target = target / flow.file.name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(flow.text(), encoding="utf-8")
    return target


def import_workflow(data: Path, source: Path, name: str = "") -> Workflow:
    """把一份工作流文件导进来：验一下有步骤，起个名字，落到 workflows/。"""
    source = Path(source)
    text = source.read_text(encoding="utf-8")
    if not any(STEP.match(line) for line in text.splitlines()):
        raise ValueError(f"{source.name} 里没有步骤（应以「### 步骤名」列出），不像一份工作流")
    found = TITLE.search(text)
    chosen = (name or (found.group(1).strip() if found else "") or source.stem).strip()
    flow = Workflow(Path(data), chosen)
    if flow.exists():
        raise FileExistsError(f"已经有一条工作流叫「{chosen}」：{flow.file}（换名字用 --as）")
    flow.file.parent.mkdir(parents=True, exist_ok=True)
    text = TITLE.sub(f"# 工作流：{chosen}", text, count=1) if found else f"# 工作流：{chosen}\n\n{text}"
    flow.file.write_text(text, encoding="utf-8")
    return flow


def listing(data: Path) -> list[Workflow]:
    base = Path(data) / "workflows"
    return [Workflow(Path(data), path.stem) for path in sorted(base.glob("*.md"))] if base.is_dir() else []
