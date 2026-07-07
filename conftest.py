"""pytest 根级配置：确保项目根目录在 ``sys.path`` 首位。

使顶层包（common/app/api/domain/infrastructure/trigger）无论从哪个目录
启动 pytest / 直接运行脚本都能被正确导入。
"""
import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
