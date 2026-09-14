# 知识工作工具箱（v2）

程序的中心是工单——一条工作流的一次执行实例；命令与窗口里的动作，就是走其中一站。模型与行为差见[设计](../index.md)，里程碑与决策见[开发计划](../dev-guide/index.md)。

## 功能对表（v1 → v2）

v1 的每个动作在 v2 都有归属——沿用、收编或明说退役；规格没规定的动作标记「实验室自留」。下表程序名暂以 `kg` 称（见开发计划·决策点「程序名」）。

| v1 动作 | 规格归属 | v2 动作 | 变化 |
| :-- | :-- | :-- | :-- |
| `workflow --new` | 工作流已创建；`POST /workspaces/{id}/workflows` | `workflow --new` | 步骤带全局 `id`；写判据骨架 |
| `workflow <名字>` / `--list` | 读取单个 / 列出工作流 | 同名 | 读路径不变 |
| （v1 无） | 定义核对（规格约束：路径在不在、小节有没有判据覆盖；不访问文件系统，由端侧判） | `workflow <名字> --check` | 新增 |
| `workflow --export / --import [--as]` | 区间流转（显式导出或导入） | 保留 | 撞名即拒、`--as` 换名，与 v1 同 |
| `task --new` | 工单已创建；`POST /workspaces/{id}/workorders` | `order --new` | 封面落笔即封；`id`、`workflow_id`、`created_at` 账本方查填，参数带了即拒 |
| `task <名字>` / `--list` | 读取工单全貌 / 列出工单（`?workflow_id=` 筛读） | `order <名字>` / `--list` | 全貌 = 封面 + 全量流水；进度与完结由流水推导，不发结论字段 |
| `task <名字> --next` | 追加工作记录（`POST …/workorders/{name}/records`）加判据核对 | `order <名字> --next` | 一步一条工作记录：`id` 追加方生成（幂等键）、`seq` 账本方分配、`step_id` 按 `step` 查填；agent 步骤交给智能体跑，程序核 `rule` 判据 |
| `task <名字> --done` | 同上（人记一笔） | `order <名字> --done <步骤>` | `is_succeeded` 来源与判据 `executor` 一一对应：`rule` 机械比对、`agent` 智能体审查、`human` 闸门放行；闸门放行落一条记录 |
| `task <名字> --journal` | 产物（日志类别） | `order <名字> --journal` | 叙事落产物，不动流水 |
| `find` / `catalog [--json]` / `audit [--make]` | 规格未规定 | 原样保留 | 实验室自留：工作区级动作 |
| `material [路径…]` | 材料；材料已收录 | `material` | 四字段不变（类型 / 内容 / 来源 / 时间），阶段由位置承担 |
| `new-instruction` | 工作流骨架 | 收编进 `workflow --new` | 指令三段（目标 / 步骤 / 验收）由工作流加工单承担 |
| `audit-instruction` | 定义核对 | 收编进 `workflow --check` | 判据跑在定义层 |
| `new-report` / `audit-report` | 产物（报告类别） | 保留 | 实验室自留：报告四段，机器写执行记录与闸门项 |
| `gui` / `kg-gui` | 无 | `kg-gui` | 台面 = 当前工单；浏览 = 工作区动作 |

## 数据

数据全落本 app `data/`，不写实验室外（工作纪律，见 `AGENTS.md`）。

工作区身份落 `workspace.yaml`：`id` / `name` / `title` / `description` / `created_at` / `updated_at`，缺则首跑生成。

工作流与工单都是 YAML，一个一文件；工单的流水（`records`）内嵌在工单里，不另落盘。

产物落 `artifacts/<类别>/<工单名>.md`——报告、日志各按类别分家，落点由工作区按名字算（算法实验室自定，见[设计](../index.md)·行为差）。
