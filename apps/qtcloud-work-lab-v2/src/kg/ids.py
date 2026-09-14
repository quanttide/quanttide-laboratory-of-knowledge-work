"""凭证：UUID——跨边界的身份。

规格：工作流与工作步骤各带一枚全局凭证，永不重发；工单与工作记录同理（见
specification/process/ 四篇）。名是辖区内的读法，凭证是跨边界的认法。
"""

import uuid


def new_id() -> str:
    return str(uuid.uuid4())


def is_id(value) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError, AttributeError):
        return False
