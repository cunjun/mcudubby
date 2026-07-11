# mcudubby

**面向 AI 的嵌入式板级调试与观测工具。**

> 人类负责接线，AI 负责调板。

`mcudubby` 是一个面向 AI 辅助 MCU 调试、嵌入式 AI 调试和真实板卡固件诊断的
[MCP](https://modelcontextprotocol.io/) 服务端。它让 AI 助手可以通过调试探针、CPU
寄存器、内存、ELF/DWARF 符号、UART/RTT 日志、SVD 外设寄存器、RTOS 状态、flash
操作和 GDB server 生命周期工具，直接观察真实 MCU 目标。

很多 AI 编码工具只停留在“生成固件”。`mcudubby` 解决的是后半段：板子不启动、串口没输出、
中断卡住，或者固件跑进 HardFault 时，AI 仍然可以继续往下调。

## 关键词

`嵌入式 AI 调试`、`AI 辅助 MCU 调试`、`AI 固件调试`、`MCU 调试智能体`、
`MCP 嵌入式调试`、`pyOCD`、`J-Link`、`ST-Link`、`CMSIS-DAP`、`HardFault 诊断`、
`FreeRTOS 调试`、`SVD 外设寄存器`、`RTT 日志`、`UART 日志`、`Codex skill`、
`Claude Code skill`。

## 快速示例

```text
用户: 这块板子上电后不启动，帮我看一下。

AI:   正在连接探针、暂停目标、读取寄存器...
      PC = 0x08001A3C -> HardFault_Handler (startup.s:42)
      CFSR = 0x00008200 -> 精确数据总线错误
      BFAR = 0x00000000 -> 可能访问了空指针
      固件在 sensor_init() 期间触发了空指针访问。
```

## 能力范围

- **探针控制：** pyOCD 支持 ST-Link/CMSIS-DAP，J-Link 通过 `pylink-square` 支持。
- **执行状态：** halt、resume、reset、单步、断点、观察点、寄存器、内存、flash 擦写校验、
  周期计数和部分 trace 路径。
- **源码上下文：** ELF/AXF 符号加载、源码映射、反汇编、本地变量、运行到函数/源码行、
  源码级单步和 backtrace。
- **外设诊断：** CMSIS-SVD 寄存器解码、field 读写、时钟和引脚复用检查，以及按症状触发的外设诊断。
- **RTOS 与日志：** FreeRTOS 任务列表/上下文、栈使用率、UART 日志、Segger RTT、J-Link 原生 RTT 读取。
- **AI 诊断入口：** 启动失败、HardFault、内存破坏、栈溢出、中断问题、时钟问题、外设卡住和调试闭环。
- **板卡 bring-up：** CMSIS-Pack 目标配置、Keil MDK 项目发现、AXF/ELF 发现、只读 smoke test、
  Keil UV4 build/flash 集成。
- **GDB server：** 启动、停止和查看 pyOCD 或 J-Link GDB server 进程。

完整工具分组见 [Tool Reference](docs/tool-reference.md)。当前后端和硬件覆盖见
[Support Matrix](docs/support-matrix.md)。第一次接板建议先使用 `doctor()` 和 `first_contact(...)`。

## 安装

```bash
pip install mcudubby
```

从源码安装：

```bash
git clone https://github.com/SolarWang233/mcudubby
cd mcudubby
pip install -e .
```

## 开发验证

从新 checkout 本地跑测试时，先用 editable 模式安装包和开发依赖：

```bash
pip install -e ".[dev]"
pytest
ruff check src tests
```

要求：

- Python 3.10+
- 受支持的调试探针
- 源码级调试需要带调试符号的 ELF/AXF

可选：

- CMSIS-SVD 文件，用于外设寄存器解码
- CMSIS-Pack 文件，用于 pyOCD 非内置目标
- J-Link backend 需要 `pylink-square`
- Windows + Keil UV4，用于集成 build/flash 流程

## 第一次会话

完整上手流程请看 quickstart。一次真实板卡会话的大致形状是：

```python
doctor()
configure_probe(target="stm32l496vetx", backend="pyocd")
configure_elf("firmware.axf")
first_contact(target="stm32l496vetx", backend="pyocd", elf_path="firmware.axf")

probe_halt()
read_stopped_context()
diagnose("board does not boot")
```

CMSIS-Pack 目标、J-Link、Keil 项目、UART 日志和排查步骤请看
[Quickstart](docs/quickstart.md) 以及 [Generic Board Workflow](docs/generic-board-workflow.md)。

## MCP 配置

最小配置：

```json
{
  "mcpServers": {
    "mcudubby": {
      "command": "python",
      "args": ["-m", "mcudubby"]
    }
  }
}
```

macOS/Linux 上如果 Python 命令是 `python3`，请相应替换。Windows 虚拟环境和 editable install
配置见 [Windows MCP Config Example](docs/windows-mcp-config-example.md)。

## 文档

- [Docs Index](docs/README.md)：安装、AI 操作、验证和路线图的阅读路径
- [Quickstart](docs/quickstart.md)：从安装到第一次真实板卡会话
- [Generic Board Workflow](docs/generic-board-workflow.md)：接入任意 MCU 目标
- [AI Playbook](docs/ai-playbook.md)：AI 助手使用 `mcudubby` 的操作手册
- [AI Examples](docs/ai-examples.md)：按场景组织的工具序列和解释方式
- [Board Validation Guide](docs/board-validation-guide.md)：真实硬件验证证据清单
- [Support Matrix](docs/support-matrix.md)：后端、目标和验证覆盖
- [Tool Reference](docs/tool-reference.md)：MCP 工具分组索引
- [mcubug Codex/CC Skill](docs/mcubug-skill.md)：安装和维护仓库自带 assistant skill
- [v0.6 Roadmap](docs/v0.6-roadmap.md)：后续路线图和高价值缺口

## 已验证硬件

当前最可信的验证路径是：

| 板子 | MCU | Probe | 重点能力 |
|------|-----|-------|----------|
| ATK_PICTURE | STM32L496VETx | ST-Link / pyOCD | ELF/DWARF、SVD、flash、RTT、RTOS、diagnosis、GDB server、FreeRTOS 同步场景 |
| 自定义板 | STM32F103C8 | J-Link | connect、registers、memory、watchpoints、flash、J-Link GDB server、RTT、DWT cycle counter |

部分支持路径和已知限制见 [Support Matrix](docs/support-matrix.md)。

## 架构

```text
AI assistant / IDE / Agent
        |
        v
     mcudubby MCP server
        |
        +-- core / session / tools / result shaping
        |
        +-- probe backends
        |    +-- pyOCD (ST-Link, CMSIS-DAP)
        |    +-- J-Link (pylink-square)
        |
        +-- UART log / RTT / SVD / ELF-DWARF / RTOS
```

后续可扩展方向：

- `mcudubby-io`：GPIO 相关辅助工具
- `mcudubby-bench`：万用表、电源、示波器、逻辑分析仪工作流

## 当前限制

- build/flash 集成目前主要面向 Windows + Keil UV4。
- RTOS 检查需要 FreeRTOS 符号与加载的 ELF/AXF 匹配。
- 高阶 DWARF 行为取决于编译器调试信息质量。
- SVD 文件不随包内置，需要为目标芯片自行提供。
- 即使后端路径可用，SWO 文本捕获仍然受板级条件影响。

## License

MIT. See [LICENSE](LICENSE).
