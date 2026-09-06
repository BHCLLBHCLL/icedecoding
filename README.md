# icedecoding
icepak project folder decoding


## GUI 100% 对标进度（P0–P9 全部完成）

按 docs/ICEPAK_UI_100PCT_PLAN.md 分阶段实施：P0 黄金规格驱动注册表 → P1 壳层 → P2 树与导航 → P3 3D 完整化（含对齐/吸附/测量） → P4 Form 引擎+18 类对象编辑器+写回 → P5 网格（AutoHex 六页签+结构网格+job 文件） → P6 求解与后处理 → P7 宏（三级注册+向导） → P8 ECAD（ECXML/IDF/Networks/JEDEC/Powermaps/EM Mapping/ICB） → P9 收尾（i18n/Preferences 七页签/.icepak_config 兼容/Annotations/横幅）。

- 测试：pytest tests/ 全绿（119 项，headless offscreen 可跑：QT_QPA_PLATFORM=offscreen）。
- 关键文件：docs/ICEPAK_UI_100PCT_PLAN.md（总规划）、docs/icepak_gui_golden.json（黄金规格）、ice_actions.py / ice_menus_toolbars.py（注册表+生成器）、ice_mesh.py / ice_solve.py / ice_macros.py / ice_ecad.py / ice_prefs.py / ice_i18n.py（分阶段模块）、REVERSE_STATUS.md（阶段验收）。

## HDM 逐点复刻（Phase J，I 收官后）

> 目标：逐节点级复刻 HDM mesher（叶放置量化/平衡判据/平滑器全链路）。

- **成果复核**：J1a 架构重定性（z 分层 150 层 + 每层 2D 网格）→ J1b 骨架定律（38×45 粗网格 EXACT）→ J1c 环带公式 + 模板/翘曲金表 → J2 层栈 + J2b 尾族跨工程定律（z_ref + m·H2 + TAIL，8/8 err=0）→ J3 装配器（66% 组件覆盖）→ J3-A as-built（150/150 层、62,626/62,626 节点 1e-12）。
- **状态**：复刻 100%（as-built，34% 金表）；law-only 规律 66%；1e-9 逐点验收未闭环（开放项 = TAIL 封闭式 + 簇层 xy 生成器）。
- **关键文件**：DEV_SUMMARY.md（A/B 路现状与瓶颈）、DEV_PLAN.md（B 路数据瓶颈与 P1–P4 突破路径）、docs/PLAN_100PCT.md（Phase J 规划）、REVERSE_STATUS.md（J 阶段全细节）、ice_hdm_layers.py（分级链引擎）、tools/hdm_j3_asbuilt.py（as-built 装配器）、tools/probe_work/（全部取证产物）。
- **测试**：全量分片 CI（tools/run_sharded.py --all，8 片）ALL PASS；J 阶段测试 tests/test_p19_layers.py（8 项）+ tests/test_p19_asbuilt.py（2 项，oracle 缺失自动跳过）。
