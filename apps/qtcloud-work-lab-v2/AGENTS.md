# AGENTS —— 实验室工作纪律（v2）

本 app 是量潮知识工作实验室 v2（`qtcloud-work-lab-v2`），按规格重写、功能对表 v1。在这儿干活的 AI 与人都按本文办。

## 数据：全部放 `data/`

**所有数据放本 app 的 `data/` 下，不许写到实验室外面**——工作区的 `data/`、规格、手册、案例都算外面。

```text
data/
├── workspace.yaml               工作区身份：id / name / title / description / created_at / updated_at（缺则首跑生成）
├── workflows/<工作流>.yaml      定义：name、description 与 steps（每步 name / description / executor / criteria）；凭证按名派生，不落文件
├── workorders/<工单>.yaml       账本：封面（id / name / description / workflow_id / created_at）加内页（records 流水）
├── artifacts/<类别>/<工单名>.md  产物按类别分家，按工单名命名
└── events.jsonl                 领域事件：WorkflowCreated / WorkOrderCreated / WorkRecorded，一条一行，只增不改
```

数据按领域模型分家：workflows（过程的定义）、workorders（一次执行）、artifacts（产物）。

## 单一事实源

本 app 的模型以规格为准：`docs/specification/process/` 的工作流、工作步骤、工单、工作记录四篇。规格没规定的操作不发明——v1 里规格之外的动作用「实验室自留」标记。

## 定义一经引用即冻结

被工单引用的工作流不可改——改步骤、删步骤、调次序，另立新工作流。本程序不设改定义的口子（改就直接改 YAML，那句话不由程序说）。

## 禁止过滤

扫描时允许跳过的只有版本库与构建产物这类非数据目录——`.git/`、`.venv/`、`node_modules/`、`__pycache__/`、`build/`、`dist/`；除此之外一律不过滤。

## 边界

- 只在实验室内做；实验阶段产物不得溢出到工作区的 `data/*`、规格、手册、案例；
- 数据是产物不是代码：进来的东西放上面的格子，不塞进 `src/` 或 `docs/`；
- 数据改动也要提交：与代码同仓，一起进版本库。
