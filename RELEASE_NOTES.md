# mcudubby v0.4.0

`mcudubby` 首个公开版本。它是一个面向 AI 辅助 MCU 调试和真实板卡固件诊断的 MCP 服务端，让 AI 助手可以通过调试探针、寄存器、内存、ELF/DWARF 符号、UART/RTT 日志、SVD 外设寄存器、RTOS 状态、flash 操作和 GDB server 生命周期工具观察真实 MCU 目标。

## 本版本包含

- MCP 服务入口：`python -m mcudubby`
- 探针控制：halt、resume、reset、单步、断点、观察点、寄存器、内存和 flash 操作
- pyOCD 后端：支持 ST-Link 和 CMSIS-DAP
- J-Link 后端：通过 `pylink-square` 支持
- ELF/DWARF 源码上下文：符号查询、栈检查、反汇编和源码导航
- UART、Segger RTT、SVD 外设寄存器、FreeRTOS 和 GDB server 工具
- 面向 AI 的诊断流程：启动失败、HardFault、栈溢出、外设异常、时钟问题和调试闭环
- 中英文文档、快速上手、支持矩阵，以及内置 `mcubug` assistant skill 参考资料

## 安装

```bash
pip install mcudubby
```

也可以从本 Release 下载附件安装：

- `mcudubby-0.4.0-py3-none-any.whl`
- `mcudubby-0.4.0.tar.gz`

## 注意事项

这是第一个公开基线版本。涉及真实硬件的功能依赖本机探针驱动、板卡接线、目标固件符号文件，以及可选后端依赖，例如 `pylink-square`。
