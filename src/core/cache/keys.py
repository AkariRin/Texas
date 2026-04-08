"""缓存键命名规范 —— 各模块就近定义。

所有键遵循格式：texas:{scope}:{identifier}

键按模块分布：
  - src/core/framework/session/keys.py：会话相关键
  - src/core/rpc/keys.py：RPC 相关键
  - src/services/personnel.py：人员管理相关键
  - src/services/daily_checkin.py：每日打卡相关键

新业务模块请在本地通过 cache_key() 定义键，无需修改此文件。
"""

from __future__ import annotations
