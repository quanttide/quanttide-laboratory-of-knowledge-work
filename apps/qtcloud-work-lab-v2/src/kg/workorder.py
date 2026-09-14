"""工单与工作记录：一次行程的账本，用 YAML 存。

规格：工单（WorkOrder）是行程的封面——封皮上写着走哪条工作流，内页是流水；工作记录
（WorkRecord）是账上一笔（见 specification/process/work-order.md 与 work-record.md）。

落点 `<工作区>/workorders/<名字>.yaml`，流水内嵌在工单的 `records` 里，不另落盘。

  id: 3c9a…            凭证号，系统生成，落笔后不变
  name: 课程档案比对
  description: 比对两侧课程档案
  workflow_id: 1f0c…   所引工作流的全球凭证，账本方查填
  created_at: 2026-09-14T10:00:00
  records:
    - id: 5e21…        凭证号，追加方生成（幂等键）
      seq: 1           页码，账本方分配，自 1 起不跳号
      created_at: 2026-09-14T10:05:00
      order_id: 3c9a…
      step: 定位        账页直读的一站（按名）
      step_id: 8a31…    跨边界的机器锚点，账本对账查填
      description: 两侧的源都找齐了
      is_succeeded: true
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from . import clock, ids
from . import workflow as flow

FIELDS = ("id", "name", "description", "workflow_id", "created_at", "records")
RECORD_FIELDS = ("id", "seq", "created_at", "order_id", "step", "step_id", "description", "is_succeeded")


class OrderError(ValueError):
    """这本账不成形，或这笔记不得。"""


def dump(payload: dict) -> str:
    return yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=200)


def validate_records(order_id: str, records: list, where: str = "工单") -> list:
    """流水只增不改：凭证不重、页码自 1 起不跳号、时刻不倒流、两处指认对得上。"""
    seen_ids: set = set()
    last = ""
    for index, record in enumerate(records, start=1):
        spot = f"{where}第 {index} 笔"
        if not isinstance(record, dict):
            raise OrderError(f"{spot}不是映射")
        unknown = [key for key in record if key not in RECORD_FIELDS]
        if unknown:
            raise OrderError(f"{spot}有不认识的字段：{'、'.join(unknown)}（只认 {'、'.join(RECORD_FIELDS)}）")
        if not ids.is_id(record.get("id")):
            raise OrderError(f"{spot}少了 id，或 id 不是 UUID")
        if record["id"] in seen_ids:
            raise OrderError(f"{spot}的 id 撞号：{record['id']}（账被复制）")
        seen_ids.add(record["id"])
        seq = record.get("seq")
        if not isinstance(seq, int) or isinstance(seq, bool) or seq != index:
            raise OrderError(f"{spot}的 seq 应当是从 1 起不跳号的页码，实得 {seq!r}")
        stamp = str(record.get("created_at", "")).strip()
        if not stamp:
            raise OrderError(f"{spot}少了 created_at")
        if last and stamp < last:
            raise OrderError(f"{spot}的时刻早于上一笔（账本时间倒流）")
        last = stamp
        if str(record.get("order_id", "")) != order_id:
            raise OrderError(f"{spot}的 order_id 与工单对不上")
        if not str(record.get("step", "")).strip():
            raise OrderError(f"{spot}少了 step（按名指认的一站）")
        if not ids.is_id(record.get("step_id")):
            raise OrderError(f"{spot}少了 step_id，或 step_id 不是 UUID")
        if not isinstance(record.get("is_succeeded", False), bool):
            raise OrderError(f"{spot}的 is_succeeded 得是布尔")
    return records


def validate(payload, where: str = "工单") -> dict:
    if not isinstance(payload, dict):
        raise OrderError(f"{where}的顶层不是映射")
    unknown = [key for key in payload if key not in FIELDS]
    if unknown:
        raise OrderError(f"{where}有不认识的字段：{'、'.join(unknown)}（只认 {'、'.join(FIELDS)}）")
    if not ids.is_id(payload.get("id")):
        raise OrderError(f"{where}少了 id，或 id 不是 UUID")
    if not str(payload.get("name", "")).strip():
        raise OrderError(f"{where}少了 name")
    if not ids.is_id(payload.get("workflow_id")):
        raise OrderError(f"{where}少了 workflow_id，或 workflow_id 不是 UUID")
    if not str(payload.get("created_at", "")).strip():
        raise OrderError(f"{where}少了 created_at")
    records = payload.get("records")
    if not isinstance(records, list):
        raise OrderError(f"{where}少了 records（流水，可为空表）")
    validate_records(str(payload["id"]), records, where)
    return payload


def load(path: Path) -> dict:
    path = Path(path)
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise OrderError(f"{path.name} 不是合法的 YAML：{error}") from error
    return validate(payload, where=path.name)


def file_for(workspace, name: str) -> Path:
    return workspace.workorders_dir / f"{name}.yaml"


def exists(workspace, name: str) -> bool:
    return file_for(workspace, name).is_file()


@dataclass
class Order:
    """一本账：封面（走哪条工作流）加内页（流水）。"""

    workspace: object
    payload: dict

    @property
    def name(self) -> str:
        return str(self.payload.get("name", "")).strip()

    @property
    def id(self) -> str:
        return str(self.payload.get("id", ""))

    @property
    def description(self) -> str:
        return str(self.payload.get("description", "")).strip()

    @property
    def workflow_id(self) -> str:
        return str(self.payload.get("workflow_id", ""))

    @property
    def created_at(self) -> str:
        return str(self.payload.get("created_at", ""))

    @property
    def records(self) -> list[dict]:
        return list(self.payload.get("records", []))

    @property
    def file(self) -> Path:
        return file_for(self.workspace, self.name)

    def save(self) -> None:
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(dump(self.payload), encoding="utf-8")

    def workflow(self) -> dict:
        """所引工作流：封面钉死的定义（认 workflow_id）。"""
        found = flow.by_id(self.workspace, self.workflow_id)
        if found is None:
            raise OrderError(f"这单引的工作流不见了（workflow_id={self.workflow_id}）")
        return found

    def workflow_name(self) -> str:
        return str(self.workflow().get("name", ""))

    def steps(self) -> list[dict]:
        return flow.steps(self.workflow())

    def step(self, name: str) -> dict | None:
        return flow.step(self.workflow(), name)


def read(workspace, name: str) -> Order:
    path = file_for(workspace, name)
    if not path.is_file():
        raise FileNotFoundError(f"没有这件工单：{path}")
    return Order(workspace, load(path))


def listing(workspace, workflow_name: str = "") -> list[Order]:
    base = workspace.workorders_dir
    orders = [read(workspace, path.stem) for path in sorted(base.glob("*.yaml"))] if base.is_dir() else []
    if workflow_name.strip():
        wanted = flow.read(workspace, workflow_name.strip())["id"]
        orders = [order for order in orders if order.workflow_id == wanted]
    return orders


def create(workspace, name: str, workflow_name: str, description: str = "") -> Order:
    """开工单：名字与所引工作流由请求给，凭证与时刻由账本查填。"""
    name = name.strip()
    if not name:
        raise OrderError("请先给这单起个名字")
    found = flow.read(workspace, workflow_name.strip())
    if exists(workspace, name):
        raise FileExistsError(f"已经有一件工单叫「{name}」：{file_for(workspace, name)}")
    payload = {
        "id": ids.new_id(),
        "name": name,
        "description": description.strip(),
        "workflow_id": found["id"],
        "created_at": clock.now(),
        "records": [],
    }
    validate(payload)
    order = Order(workspace, payload)
    order.save()
    return order


def append(order: Order, record_id: str, step: str, description: str = "", is_succeeded: bool = False, at: str = "") -> dict:
    """追加一笔：id 追加方给（幂等键），seq 与 step_id 账本方分配查填。"""
    if not ids.is_id(record_id):
        raise OrderError("记录的 id 得是 UUID（幂等键）")
    if any(record["id"] == record_id for record in order.records):
        raise OrderError(f"这条记录已经在账上了：{record_id}（视作重放）")
    found = order.step(step)
    if found is None:
        raise OrderError(f"所引工作流里没有这一步：{step}（先看看定义）")
    stamp = at or clock.now()
    last = order.records[-1]["created_at"] if order.records else ""
    if last and stamp < last:
        raise OrderError(f"时间倒序：新记录（{stamp}）早于末条（{last}）")
    record = {
        "id": record_id,
        "seq": len(order.records) + 1,
        "created_at": stamp,
        "order_id": order.id,
        "step": found["name"],
        "step_id": found["id"],
        "description": description.strip(),
        "is_succeeded": bool(is_succeeded),
    }
    order.payload["records"].append(record)
    validate(order.payload)
    order.save()
    return record


def done_steps(order: Order) -> set[str]:
    """走过了的站：流水里成功执行过、且名字确实是定义上的步骤。"""
    names = {item["name"] for item in order.steps()}
    return {record["step"] for record in order.records if record.get("is_succeeded") and record["step"] in names}


def next_step(order: Order) -> dict | None:
    done = done_steps(order)
    return next((item for item in order.steps() if item["name"] not in done), None)


def finished(order: Order) -> bool:
    """走完是一段推导：每个步骤都有成功的流水，不落字段。"""
    items = order.steps()
    return bool(items) and all(item["name"] in done_steps(order) for item in items)


def pending_gates(order: Order) -> list[str]:
    """待拍板清单：定义里 `human` 判据的所在站，还没过的那一站。"""
    done = done_steps(order)
    notes: list[str] = []
    for item in order.steps():
        if item["name"] in done:
            continue
        for criterion in flow.of(item, flow.HUMAN):
            text = str(criterion.get("description", "")).strip()
            if text:
                notes.append(f"{item['name']}：{text}")
    return notes


def progress(order: Order) -> str:
    items = order.steps()
    return f"{len(done_steps(order))}/{len(items)}"


def delete(workspace, name: str) -> None:
    """删一张白纸：流水非空即拒——账本不销户。"""
    order = read(workspace, name)
    if order.records:
        raise OrderError(f"有账不销：这单已经有 {len(order.records)} 笔流水，删不得")
    order.file.unlink()
