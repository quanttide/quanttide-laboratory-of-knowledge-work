"""领域事件：落 JSONL，一条一行，只增不改。

规格：工作流已创建（`WorkflowCreated`）、工单已创建（`WorkOrderCreated`）、工作记录已追加
（`WorkRecorded`）。负载至少带工作区 `id`；工单事件带工单 `id` 与 `name`、`workflow_id` 与
声明全文；记录事件带工单名、记录 `id` 与 `seq`、`step_id` 与记录全文。下游按 `id` 幂等去重。
"""

import json

from . import clock

WORKFLOW_CREATED = "WorkflowCreated"
WORKORDER_CREATED = "WorkOrderCreated"
WORK_RECORDED = "WorkRecorded"


def emit(workspace, payload: dict) -> None:
    workspace.events_file.parent.mkdir(parents=True, exist_ok=True)
    with workspace.events_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=False) + "\n")


def workflow_created(workspace, workflow: dict) -> None:
    emit(
        workspace,
        {
            "event": WORKFLOW_CREATED,
            "at": clock.now(),
            "workspace_id": workspace.workspace_id(),
            "workflow_id": workflow["id"],
            "name": workflow["name"],
            "workflow": workflow,
        },
    )


def workorder_created(workspace, order: dict) -> None:
    emit(
        workspace,
        {
            "event": WORKORDER_CREATED,
            "at": clock.now(),
            "workspace_id": workspace.workspace_id(),
            "order_id": order["id"],
            "name": order["name"],
            "workflow_id": order["workflow_id"],
            "order": order,
        },
    )


def work_recorded(workspace, order: dict, record: dict) -> None:
    emit(
        workspace,
        {
            "event": WORK_RECORDED,
            "at": clock.now(),
            "workspace_id": workspace.workspace_id(),
            "order_id": order["id"],
            "order_name": order["name"],
            "record_id": record["id"],
            "seq": record["seq"],
            "step_id": record["step_id"],
            "record": record,
        },
    )


def listing(workspace) -> list[dict]:
    if not workspace.events_file.is_file():
        return []
    rows = []
    for line in workspace.events_file.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows
