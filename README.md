# mcudubby

**让 AI 不只会写固件，也能连接真实 MCU 查问题。**

> 人类负责接线，AI 负责调板。

`mcudubby` 是一个面向 MCU 板级调试的 [MCP](https://modelcontextprotocol.io/) 服务端。
它把调试探针、CPU 状态、内存、ELF/DWARF 符号、UART/RTT 日志、SVD 外设寄存器、RTOS 状态、flash
操作和 GDB server 生命周期工具变成 AI 助手可以调用的工具。

当板子不启动、没有日志或进入 HardFault 时，你可以直接告诉 AI 现象，让它继续收集证据，
而不是只靠猜测修改代码。

## 关键词

`嵌入式 AI 调试`、`AI 辅助 MCU 调试`、`AI 固件调试`、`MCU 调试智能体`、
`MCP 嵌入式调试`、`pyOCD`、`J-Link`、`ST-Link`、`CMSIS-DAP`、`HardFault 诊断`、
`FreeRTOS 调试`、`SVD 外设寄存器`、`RTT 日志`、`UART 日志`、`Codex skill`、
`Claude Code skill`。

## 快速示例

```text
用户：这块板子上电后不启动，帮我看一下。

AI：正在连接探针、暂停目标、读取寄存器……
    PC = 0x08001A3C -> HardFault_Handler (startup.s:42)
    CFSR = 0x00008200 -> 精确数据总线错误
    BFAR = 0x00000000 -> 可能访问了空指针
    固件在 sensor_init() 期间触发了空指针访问。
```

## 开始前先了解

如果你第一次接触嵌入式调试，只需先认识三个概念：

- **调试探针：** 连接电脑和开发板的调试硬件，例如 ST-Link、J-Link 或 CMSIS-DAP。
- **ELF/AXF：** 编译生成的带调试信息文件，让 AI 能把地址还原成函数、源码行和变量。
- **MCP：** 让 Codex、Claude Code 等 AI 客户端调用外部工具的协议。

你还需要一块已供电的 MCU 开发板、正确连接的调试探针，以及 Python 3.10 或更高版本。
如果暂时没有真实硬件，也可以先运行仓库中的 mock demo 了解诊断流程。

## 快速开始

### 1. 安装

```bash
pip install mcudubby
```

使用 J-Link 时，额外安装对应依赖：

```bash
pip install "mcudubby[jlink]"
```

### 2. 配置 AI 客户端

将下面的 MCP 配置加入支持 MCP 的客户端：

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

macOS/Linux 如果使用 `python3`，请替换 `command`。Windows 虚拟环境和本地源码安装见
[Windows MCP 配置示例](docs/windows-mcp-config-example.md)。配置后重启 AI 客户端。

### 3. 第一次对话

连接并给开发板供电，然后直接告诉 AI：

```text
请使用 mcudubby 检查当前调试环境，查找已连接的探针，并在不写入 flash 的前提下
对开发板做第一次只读检查。开始前先告诉我还缺少哪些信息。
```

AI 会依次检查运行环境、发现探针、确认目标芯片并读取基本 CPU 状态。目标和固件路径明确后，
它还可以加载 ELF/AXF、定位源码并继续诊断。完整操作见 [快速上手](docs/quickstart.md)。

> 不确定目标型号、接线或操作风险时，先让 AI 检查并解释，不要直接擦写 flash。

## 它能做什么

- 连接 pyOCD（ST-Link/CMSIS-DAP）或 J-Link，控制 halt、resume、reset 和单步。
- 读取寄存器、内存、断点、观察点，并执行受控的 flash 擦写与校验。
- 使用 ELF/AXF 和 DWARF 定位函数、源码行、本地变量、调用栈和反汇编。
- 使用 CMSIS-SVD 解码外设寄存器，辅助检查时钟、中断和外设状态。
- 查看 UART/RTT 日志、FreeRTOS 任务和栈使用情况。
- 针对启动失败、HardFault、无日志、栈溢出和外设卡住组织诊断证据。

完整工具列表见 [Tool Reference](docs/tool-reference.md)。

## 已验证硬件

| 板卡 | MCU | 调试路径 | 已验证重点 |
|------|-----|----------|------------|
| ATK_PICTURE | STM32L496VETx | ST-Link / pyOCD | ELF/DWARF、SVD、flash、RTT、RTOS、诊断、GDB server |
| 自定义板 | STM32F103C8 | J-Link | 寄存器、内存、观察点、flash、RTT、DWT、GDB server |

其他目标也可以通过 pyOCD、CMSIS-Pack 或 J-Link 接入，但不代表所有能力都经过真实硬件验证。
准确的后端覆盖和限制以 [Support Matrix](docs/support-matrix.md) 为准。

## 当前限制

- build/flash 集成目前主要面向 Windows + Keil UV4。
- RTOS 检查需要 FreeRTOS 符号与加载的 ELF/AXF 匹配。
- SVD 文件不随包内置，需要为目标芯片自行提供。
- SWO 文本捕获仍受芯片、固件配置和板级接线影响。
- 这是 Alpha 阶段项目；涉及 flash 写入前，请确认目标、地址和备份。

## 继续阅读

- **第一次使用：** [Quickstart](docs/quickstart.md) · [Windows MCP 配置](docs/windows-mcp-config-example.md)
- **接入新板卡：** [Generic Board Workflow](docs/generic-board-workflow.md) · [Support Matrix](docs/support-matrix.md)
- **让 AI 正确调试：** [AI Playbook](docs/ai-playbook.md) · [AI Examples](docs/ai-examples.md)
- **深入了解：** [Tool Reference](docs/tool-reference.md) · [Architecture](docs/architecture.md)
- **安装配套 skill：** [mcubug Codex/CC Skill](docs/mcubug-skill.md)
- **参与开发：** [Docs Index](docs/README.md) · [Roadmap](docs/v0.6-roadmap.md)

## 本地开发

```bash
pip install -e ".[dev]"
pytest
ruff check src tests
```

## License

MIT. See [LICENSE](LICENSE).
