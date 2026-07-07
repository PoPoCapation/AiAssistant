"""通用类型层（对应 Java group-buy-market 的 types 模块）。

命名说明：Python 标准库已占用 ``types`` 模块名（解释器启动即缓存，
且 ``enum`` 依赖它），PRD 中的顶层 ``types/`` 包无法被导入
（``from types.enums import ...`` 会报 ``'types' is not a package``）。
因此将该层重命名为 ``common/``，子模块结构与 PRD 保持一致，
其余分层包名（app/api/domain/infrastructure/trigger）不变。
"""
from common.enums import ResponseCode
from common.exception import AppException

__all__ = ["ResponseCode", "AppException"]
