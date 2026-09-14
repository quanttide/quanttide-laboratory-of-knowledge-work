"""凭证：UUID——跨边界的身份。

规格：工作流与工作步骤各带一枚全局凭证，永不重发；工单与工作记录同理（见
specification/process/ 四篇）。

本 app 的两条线：

- **人写的定义不带凭证**（工作流、工作步骤）：落盘只有名字与内容，凭证按「工作区 id +
  名字」现算（`derive`）——单个工作区里名字本就唯一，(工作区 id, 名字) 就够定一件东西，
  再把算得出来的值抄进文件，等于同一件事记两处。定义读得到处都能跑：指着一处固定资产
  目录就能跑，程序不必先「导入」、也不必往人写的文件里添字。
- **程序写的账本带凭证**（工单、工作记录）：它们是事实的实例，不是有名字的定义；凭证由
  账本生成、落盘随事件走，认它做幂等与跨区归并。

`derive` 的算法要各平台一致：命名空间恒为 `NAMESPACE`，串取「上级凭证/类别/名字」，
即 `工作区 id/workflow/名字` 与 `工作流凭证/step/名字`。
"""

import uuid

NAMESPACE = uuid.UUID("90cf5627-95f3-5e25-ba48-47d50dee6e09")


def new_id() -> str:
    """程序自己发的凭证：工单与工作记录用。"""
    return str(uuid.uuid4())


def derive(kind: str, *parts: str) -> str:
    """按名派生凭证：同一组字段在同一工作区里永远算出同一枚。"""
    return str(uuid.uuid5(NAMESPACE, "/".join([*parts, kind])))


def is_id(value) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError, AttributeError):
        return False
