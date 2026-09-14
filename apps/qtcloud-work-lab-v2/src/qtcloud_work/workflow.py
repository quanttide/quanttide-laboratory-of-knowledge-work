"""工作流与工作步骤：过程的定义，用 YAML 存。

规格：工作流（Workflow）是行程的声明，工作步骤（WorkStep）是行程上的一站
（见 specification/process/workflow.md 与 work-step.md）。

定义要有固定的意义，所以是 YAML 而不是散文：字段名、取值、判据种类都由 schema
定死，不认识的字段直接报错。落点 `<工作区>/workflows/<名字>.yaml`，文件名即工作流名。

定义不带凭证：`id` 可以不写——工作流按「工作区 id + 名字」、步骤按「工作流凭证 + 名字」
现算（见 ids.py），所以一份定义指到哪个工作区都能直接跑；写了就照写的用（旧文件兼容）。

  name: 课程档案比对
  description: 比对两边的档案
  steps:
    - name: 定位
      description: 把两边的源找齐
      executor: agent  # agent | human；默认 agent
      criteria:
        - executor: rule
          description: 个人课程档案在
          path: data/profile/iGuo/course/index.md
        - executor: human
          description: 创始人点头
"""

import re
from pathlib import Path

import yaml

from . import ids

TOP_FIELDS = ("id", "name", "description", "steps")
STEP_FIELDS = ("id", "name", "description", "executor", "criteria")
CRITERION_FIELDS = ("executor", "description", "path", "absent", "file", "contains", "run")
JUDGEMENTS = ("path", "absent", "file", "contains", "run")
EXECUTORS = ("agent", "human")
TYPES = ("rule", "agent", "human")
AGENT = "agent"
HUMAN = "human"
RULE = "rule"
SECTION = re.compile(r"「([^」]+)」|##\s*([^\s#]+)")


def _sections(text: str) -> set[str]:
    """描述里点到的小节：引号里的短名，或 `##` 起的标题。

    只认干净的名字（全是字词、不长）——引号里带标点的长句是叙述，不是小节名。
    """
    found = set()
    for match in SECTION.finditer(text):
        name = (match.group(1) or match.group(2)).strip()
        if name and len(name) <= 10 and re.fullmatch(r"[^\W_]+", name):
            found.add(name)
    return found


class WorkflowError(ValueError):
    """这份文件不像一份工作流。"""


def dump(payload: dict) -> str:
    return yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=200)


def _validate_criterion(criterion, where: str) -> None:
    if not isinstance(criterion, dict):
        raise WorkflowError(f"{where}不是映射")
    kind = criterion.get("executor")
    if kind not in TYPES:
        raise WorkflowError(f"{where}的 executor 只能是 {' / '.join(TYPES)}（谁判：规则引擎 / 智能体 / 人）")
    unknown = [key for key in criterion if key not in CRITERION_FIELDS]
    if unknown:
        raise WorkflowError(f"{where}有不认识的字段：{'、'.join(unknown)}（只认 {'、'.join(CRITERION_FIELDS)}）")
    given = [key for key in JUDGEMENTS if key in criterion]
    if kind == RULE:
        if not given:
            raise WorkflowError(f"{where}是 rule，得写一条判法（path / absent / file+contains / run）")
        if ("contains" in given) != ("file" in given):
            raise WorkflowError(f"{where}的 file 与 contains 必须成对（file 写哪儿、contains 写含什么）")
        others = [key for key in given if key not in ("file", "contains")]
        if len(others) > 1 or (others and "file" in given):
            raise WorkflowError(f"{where}的判法只能一种：path / absent / file+contains / run")
    else:
        if not str(criterion.get("description", "")).strip():
            raise WorkflowError(f"{where}是 {kind}，必须写 description（判准 / 要人拍板的事）")
        if given:
            raise WorkflowError(f"{where}是 {kind}，不该带 {'、'.join(given)}（那是 rule 的字段）")


def _validate_step(step, position: int, where: str, seen_ids: set, seen_names: set) -> None:
    spot = f"{where}第 {position} 个步骤"
    if not isinstance(step, dict):
        raise WorkflowError(f"{spot}不是映射")
    unknown = [key for key in step if key not in STEP_FIELDS]
    if unknown:
        raise WorkflowError(f"{spot}有不认识的字段：{'、'.join(unknown)}（只认 {'、'.join(STEP_FIELDS)}）")
    given_id = step.get("id")
    if given_id is not None and not ids.is_id(given_id):
        raise WorkflowError(f"{spot}的 id 不是 UUID（不写就按名字派生）")
    if given_id is not None:
        if given_id in seen_ids:
            raise WorkflowError(f"{spot}的 id 撞号：{given_id}（凭证不重发）")
        seen_ids.add(given_id)
    name = str(step.get("name", "")).strip()
    if not name:
        raise WorkflowError(f"{spot}少了 name")
    if name in seen_names:
        raise WorkflowError(f"{spot}与前面的步骤重名：{name}（工作流内步骤名唯一）")
    seen_names.add(name)
    if not str(step.get("description", "")).strip():
        raise WorkflowError(f"{spot}少了 description（一句话指令）")
    executor = step.get("executor", AGENT)
    if executor not in EXECUTORS:
        raise WorkflowError(f"{spot}的 executor 只能是 {' 或 '.join(EXECUTORS)}，实得 {executor!r}")
    criteria = step.get("criteria") or []
    if not isinstance(criteria, list):
        raise WorkflowError(f"{spot}的 criteria 应当是列表")
    for order, criterion in enumerate(criteria, start=1):
        _validate_criterion(criterion, f"{spot}「{name}」第 {order} 条判据")


def validate(payload, where: str = "定义") -> dict:
    """过一遍 schema：不认识的字段、缺必填、撞名撞号，一律报错。"""
    if not isinstance(payload, dict):
        raise WorkflowError(f"{where}的顶层不是映射（id / name / description / steps）")
    unknown = [key for key in payload if key not in TOP_FIELDS]
    if unknown:
        raise WorkflowError(f"{where}顶层有不认识的字段：{'、'.join(unknown)}（只认 {'、'.join(TOP_FIELDS)}）")
    given_id = payload.get("id")
    if given_id is not None and not ids.is_id(given_id):
        raise WorkflowError(f"{where}的 id 不是 UUID（不写就按名字派生）")
    if not str(payload.get("name", "")).strip():
        raise WorkflowError(f"{where}少了 name")
    steps = payload.get("steps")
    if not isinstance(steps, list) or not steps:
        raise WorkflowError(f"{where}少了 steps（至少一个步骤）")
    seen_ids: set = set()
    seen_names: set = set()
    for index, step in enumerate(steps, start=1):
        _validate_step(step, index, where, seen_ids, seen_names)
    return payload


def load(path: Path) -> dict:
    """读一份定义：不是映射、缺字段、取值不对，当场报错。"""
    path = Path(path)
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise WorkflowError(f"{path.name} 不是合法的 YAML：{error}") from error
    return validate(payload, where=path.name)


def credentials(workspace, payload: dict) -> dict:
    """把定义里缺的凭证补上：工作流按「工作区 id + 名字」，步骤按「工作流凭证 + 名字」。

    定义文件不带凭证；在人写的那份上不添字，凭证只在读进内存时现算。
    """
    filled = dict(payload)
    if not ids.is_id(filled.get("id")):
        filled["id"] = ids.derive("workflow", workspace.workspace_id(), str(filled.get("name", "")).strip())
    steps = []
    for step in payload.get("steps", []):
        item = dict(step)
        if not ids.is_id(item.get("id")):
            item["id"] = ids.derive("step", filled["id"], str(item.get("name", "")).strip())
        steps.append(item)
    filled["steps"] = steps
    return filled


def declared_ids(workspace) -> set[str]:
    """区内定义里白纸黑字写下的凭证（旧文件兼容）。"""
    base = workspace.workflows_dir
    if not base.is_dir():
        return set()
    return {payload["id"] for path in sorted(base.glob("*.yaml")) if ids.is_id((payload := load(path)).get("id"))}


def file_for(workspace, name: str) -> Path:
    return workspace.workflows_dir / f"{name}.yaml"


def exists(workspace, name: str) -> bool:
    return file_for(workspace, name).is_file()


def read(workspace, name: str) -> dict:
    path = file_for(workspace, name)
    if not path.is_file():
        raise FileNotFoundError(f"没有这条工作流：{path}")
    return credentials(workspace, load(path))


def listing(workspace) -> list[dict]:
    base = workspace.workflows_dir
    return [credentials(workspace, load(path)) for path in sorted(base.glob("*.yaml"))] if base.is_dir() else []


def by_id(workspace, workflow_id: str) -> dict | None:
    return next((payload for payload in listing(workspace) if payload["id"] == workflow_id), None)


def _skeleton(name: str) -> dict:
    return {
        "name": name,
        "description": f"<{name}这一步做什么>",
        "executor": AGENT,
        "criteria": [
            {"executor": RULE, "description": "<这一步怎么算完>", "path": "<相对工作区的路径>"},
            {"executor": HUMAN, "description": "<只能人拍板的事项>"},
        ],
    }


def create(workspace, name: str, steps: list[str], description: str = "") -> dict:
    """写一条工作流：步骤各写一份判据骨架（写判据 = 写怎么算完）；凭证不入文件，读时现算。"""
    name = name.strip()
    if not name:
        raise WorkflowError("请先给工作流起个名字")
    steps = [item.strip() for item in steps if item.strip()]
    if not steps:
        raise WorkflowError("至少给一个步骤：--steps 甲,乙,丙")
    if exists(workspace, name):
        raise FileExistsError(f"已经有一条工作流叫「{name}」：{file_for(workspace, name)}")
    payload = {
        "name": name,
        "description": description.strip(),
        "steps": [_skeleton(step) for step in steps],
    }
    validate(payload)
    workspace.workflows_dir.mkdir(parents=True, exist_ok=True)
    file_for(workspace, name).write_text(dump(payload), encoding="utf-8")
    return credentials(workspace, payload)


def export(workspace, name: str, target: Path) -> Path:
    """把一条工作流原样存成一份可带走的文件。"""
    payload = load(file_for(workspace, name))
    target = Path(target)
    if target.is_dir():
        target = target / f"{name}.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dump(payload), encoding="utf-8")
    return target


def import_(workspace, source: Path, name: str = "") -> dict:
    """把一份工作流导进来：先照 schema 验一遍，再落进 workflows/。"""
    payload = load(Path(source))
    chosen = (name or str(payload.get("name", "")).strip() or Path(source).stem).strip()
    if exists(workspace, chosen):
        raise FileExistsError(f"已经有一条工作流叫「{chosen}」：{file_for(workspace, chosen)}（换名字用 --as）")
    payload = dict(payload)
    payload["name"] = chosen
    validate(payload)
    if ids.is_id(payload.get("id")) and payload["id"] in declared_ids(workspace):
        raise WorkflowError(f"区内已有工作流白纸黑字写着同一 id：{payload['id']}（凭证不重发）")
    workspace.workflows_dir.mkdir(parents=True, exist_ok=True)
    file_for(workspace, chosen).write_text(dump(payload), encoding="utf-8")
    return credentials(workspace, payload)


def steps(payload: dict) -> list[dict]:
    """步骤：按定义里的顺序——这就是「串联」。"""
    return list(payload.get("steps", []))


def step(payload: dict, name: str) -> dict | None:
    return next((item for item in steps(payload) if item["name"] == name), None)


def of(step_payload: dict, kind: str) -> list[dict]:
    return [item for item in step_payload.get("criteria", []) if item.get("executor") == kind]


def _inside(root: Path, text: str) -> bool:
    """路径落在工作区内（不访问文件系统，只看写下的位置）。"""
    written = str(text).strip()
    if not written or written.startswith("<"):
        return True
    path = Path(written)
    if path.is_absolute():
        return path.is_relative_to(root)
    return ".." not in path.parts


def check(workspace, name: str) -> list[str]:
    """定义核对：判据路径须在区内，描述提到的小节须有 contains 判据覆盖。

    核对不访问文件系统——在不在由端侧判断。
    """
    payload = read(workspace, name)
    root = workspace.root.resolve()
    problems: list[str] = []
    for item in steps(payload):
        spot = item["name"]
        for criterion in item.get("criteria", []):
            for key in ("path", "file"):
                if key in criterion and not _inside(root, criterion[key]):
                    problems.append(f"{spot}：{key} 不在工作区内——{criterion[key]}")
        mentioned = _sections(item["description"])
        covered = {str(criterion.get("contains", "")) for criterion in item.get("criteria", [])}
        for section in sorted(mentioned):
            if not any(section in text for text in covered):
                problems.append(f"{spot}：描述提到「{section}」，却没有 contains 判据覆盖")
    return problems
