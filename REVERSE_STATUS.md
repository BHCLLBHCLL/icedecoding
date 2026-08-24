# Icepak 项目文件/目录逆向解析 — 状态总结

> 生成时间: 2026-08-24
> 范围: 对 ANSYS Icepak (v19.5) 项目文件与目录的逆向解析实现现状

## 1. 项目目标

解析 ANSYS Icepak 的项目文件（目录结构 + `.tzr` 打包归档），还原其中的几何对象、求解设置、网格参数、材料与后处理对象，并支持 JSON / CSV 结构化导出与 3D 可视化预览。

## 2. 当前总体状态

**核心解析链路已跑通，全部 26 个项目扫描通过、无解析异常、无未知对象类型、post 引用对象全部可在 model 中找到。**

- 已解析项目数: **26**（16 个目录 + 10 个 `.tzr` 归档）
- 覆盖对象类型: domain / block / plate / source / fan / opening / wall / pcb / package / heatsink / material / part / resistance / ventres / enclosure / assembly 等
- 解析对象总数: 约 **1200+**（单项目最多 259 个，如 datacenter）
- 交叉验证: 全部项目 `post_missing_in_model = []`、`unknown_object_types = []`

## 3. 逆向解析方法论

编码算法并非文档公开，而是通过对 **icepak.exe 反汇编 + 统计分析** 逐步复现：

| 阶段 | 手段 | 产物 |
| --- | --- | --- |
| 二进制定位 | 在 icepak.exe 中搜索特征字符串/常量 | `search_exe.py` / `search_binaries.py` / `find_refs.py` |
| 反汇编 | 定位混淆编码相关函数并人工分析 | `disasm1/2/3.py`、`func_disasm.txt` |
| 编码分析 | 从反汇编还原 `v = c - KQ[i%7] - KC[i%16] - seed` 公式 | `decoder.py` 中公式注释 |
| 统计验证 | 位置频率分析、字符集分布、往返编码验证 | `analyze2.py` / `analyze3.py` / `analyze_encoding.py` / `test_decode.py` / `verify_full.py` |
| 归档格式 | 识别 `.tzr` 为 gzip+tar 双层封装 | `dump_bytes.py` / `tzr.py` |

### 3.1 混淆编码 (Il!!)

model、materials_from_libraries 等文件以 `Il!!` 开头并整体混淆：

- 解码: `v = c - KQ[i % 7] - KC[i % 16] - seed`，`v < 0x20` 时循环加 `0x5F`
- 密钥: `KQ = "q|sz}y~"`（周期 7）、`KC = "cor5(#b!S0efP3+E"`（周期 16）
- seed = `Il!!` 后的第一个字符；有效字符区间 `0x20–0x7E`，周期 lcm(7,16)=112
- 已实现可逆编解码（`decoder.py`），同 seed 往返一致

## 4. 已实现能力（icepak_parser 包）

| 模块 | 功能 | 状态 |
| --- | --- | --- |
| `decoder.py` | `Il!!` 混淆编解码 | 完成，往返验证通过 |
| `tzr.py` | `.tzr` gzip+tar 解包 | 完成 |
| `model_parser.py` | model 文件 → 对象树（object/shape/setval/嵌套 object） | 基本完成（见限制） |
| `problem_parser.py` | problem 文件 → set / array set 结构 | 基本完成 |
| `project.py` | 目录/归档聚合入口 + main.ice.xml / grid_params / materials / post_objects | 完成 |
| `export.py` | 类型化导出 JSON / objects / problem / grid CSV，几何量提取（bbox/center/radius 等） | 完成 |
| `cli.py` | 批量 scan + 交叉验证（post 引用、grid 对照、未知类型） | 完成 |
| `ice_gui.py` | PyQt5 + VTK 3D 可视化查看器（几何构建/拾取/渲染模式） | 实现（GUI 依赖 PyQt5/VTK） |

## 5. 交叉验证结果（_report/report.json）

- post 对象引用的 model 对象名：**全部命中**（各项目 `post_missing_in_model` 均为空）
- 未知对象类型：**0 个**
- grid_params 行类型与 model 对象类型分布可对照（信息性校验）

## 6. 已知限制与待办

| 项 | 说明 |
| --- | --- |
| 多 shape 对象 | `model_parser` 目前只保留最后一个 shape；`end shape` 嵌套时处理有缺陷 |
| 多边形几何 | `shape_polygon` 仅标注 "详见 setvals"，未提取顶点坐标 |
| 其他 shape 类型 | 仅 hexa/quad/plate/cyl 有几何提取，其余走通用 pts |
| grid_params | 仅 token 级切分，未结构化解释各字段含义 |
| problem 数组 | `_pairs` 只处理标量键值，列表/嵌套值未完整建模 |
| 硬编码路径 | 多个脚本默认参数硬编码 `D:\training\icepak` |
| GUI 依赖 | 3D 查看器需要 PyQt5 + VTK，非核心解析依赖 |

## 7. 目录结构

```
icedecoding/
├── icepak_parser/         # 核心解析库
│   ├── decoder.py         # Il!! 混淆编解码（逆向自 exe）
│   ├── tzr.py             # .tzr 归档解包
│   ├── model_parser.py    # model 对象树解析
│   ├── problem_parser.py  # problem 设置解析
│   ├── project.py         # 聚合入口
│   ├── export.py          # JSON/CSV 导出
│   └── cli.py             # 批量扫描 + 交叉验证
├── ice_gui.py             # PyQt5+VTK 3D 查看器
├── disasm*.py / func_disasm.txt   # 逆向分析脚本与反汇编输出
├── analyze*.py            # 统计分析脚本
├── verify_full.py / test_decode.py # 解码验证
├── _report/               # 批量扫描报告（json/csv + 各项目导出）
└── _out/                  # 示例导出
```

## 8. 结论

逆向解析主线（混淆解码 → model/problem/网格/材料/后处理解析 → 聚合导出 → 可视化）已全部实现并通过 26 个真实项目验证，处于"功能完整、细节待打磨"阶段。后续工作重点是补齐多边形/多 shape 几何解析与 problem 数组结构化。
