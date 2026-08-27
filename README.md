# icedecoding
icepak project folder decoding


## GUI 100% 对标进度（P0–P9 全部完成）

按 docs/ICEPAK_UI_100PCT_PLAN.md 分阶段实施：P0 黄金规格驱动注册表 → P1 壳层 → P2 树与导航 → P3 3D 完整化（含对齐/吸附/测量） → P4 Form 引擎+18 类对象编辑器+写回 → P5 网格（AutoHex 六页签+结构网格+job 文件） → P6 求解与后处理 → P7 宏（三级注册+向导） → P8 ECAD（ECXML/IDF/Networks/JEDEC/Powermaps/EM Mapping/ICB） → P9 收尾（i18n/Preferences 七页签/.icepak_config 兼容/Annotations/横幅）。

- 测试：pytest tests/ 全绿（119 项，headless offscreen 可跑：QT_QPA_PLATFORM=offscreen）。
- 关键文件：docs/ICEPAK_UI_100PCT_PLAN.md（总规划）、docs/icepak_gui_golden.json（黄金规格）、ice_actions.py / ice_menus_toolbars.py（注册表+生成器）、ice_mesh.py / ice_solve.py / ice_macros.py / ice_ecad.py / ice_prefs.py / ice_i18n.py（分阶段模块）、REVERSE_STATUS.md（阶段验收）。
