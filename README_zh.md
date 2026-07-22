# McuBuddy — MCU 与嵌入式固件 AI 调试 MCP 服务

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-server-8A2BE2)](https://modelcontextprotocol.io/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**语言版本：** [English](README.md) | [中文](README_zh.md)

**让 AI 不只会分析固件代码，也能连接真实 MCU、操作调试工具并收集板级证据。**

`McuBuddy` 是一个面向 MCU 板级调试的
[Model Context Protocol（MCP）](https://modelcontextprotocol.io/) 服务端。它把调试探针、
Keil MDK 工程、ELF/DWARF 符号、CPU 与内存状态、SVD 外设寄存器、UART/RTT 日志、
FreeRTOS 状态、Flash 操作和 GDB Server 统一成 AI 助手可以调用的结构化工具。

它适合固件开发、板卡 Bring-up、故障定位、调试自动化和 AI 辅助验证。

McuBuddy v0.5.2 默认启用精简的 `core` MCP 工具配置档；如需早期 Alpha 版本中的完整专家
工具集，请在 MCP 服务环境中设置 `MCUBUDDY_TOOL_PROFILE=full`。

> [!IMPORTANT]
> 项目仍处于 Alpha 阶段。人负责目标、接线和风险决策；AI 负责调用工具、组织证据和推进调试。
> 涉及复位、运行控制、内存写入和 Flash 擦写时，应先确认目标、影响和恢复方式。

**文档入口：** [快速开始](docs/quickstart.md) ·
[工具索引](docs/tool-reference.md) ·
[支持矩阵](docs/support-matrix.md) ·
[项目架构](docs/architecture.md)

## ✨ 核心能力

- **真实硬件调试**：发现并连接 ST-Link、J-Link、CMSIS-DAP 等探针，控制目标运行状态，
  读取寄存器、内存、断点和观察点。
- **Keil 工程闭环**：发现 `.uvprojx` / `.uvproj`，选择 Target，调用 UV4 构建或下载，
  并将生成的 AXF/ELF 接入后续调试。
- **源码级故障诊断**：利用 ELF/DWARF 将地址还原为函数、源码行、局部变量和调用栈，
  辅助分析 HardFault、启动失败、栈溢出和内存破坏。
- **外设与 RTOS 检查**：通过 CMSIS-SVD 解码外设寄存器，检查 FreeRTOS 任务、任务上下文
  和栈使用情况。
- **日志与运行观测**：读取 UART、RTT 和部分 J-Link SWO 日志，管理 pyOCD/J-Link
  GDB Server 生命周期。
- **安全边界**：为工具标记只读、执行状态变化、运行时写入和持久性破坏等级，要求高风险
  操作显式确认。
- **证据驱动**：返回结构化的目标、状态和验证结果，让 AI 基于板级证据继续排查，
  而不是只根据现象猜测修改代码。

## 🏗️ 工作原理

```mermaid
flowchart LR
    AI["AI 客户端<br/>Codex / Claude Code"] --> MCP["McuBuddy<br/>MCP Server"]
    MCP --> EB["执行边界<br/>Session 串行化"]
    EB --> TOOLS["调试工具<br/>诊断 / 符号 / SVD / RTOS / 日志"]
    TOOLS --> KEIL["Keil UV4<br/>构建 / 可选下载"]
    TOOLS --> PROBE["探针后端<br/>pyOCD / J-Link / probe-rs"]
    KEIL --> IMAGE["AXF / ELF / HEX / BIN"]
    IMAGE --> TOOLS
    PROBE --> BOARD["真实 MCU 开发板"]
```

| 组件 | 主要职责 |
| --- | --- |
| Codex、Claude Code 等 AI 客户端 | 理解问题、选择工具、解释结果并提出下一步检查 |
| MCP | AI 客户端与 `McuBuddy` 之间的标准工具调用协议 |
| `McuBuddy` | 管理调试 Session、调用后端、执行安全检查并返回结构化结果 |
| Keil MDK / UV4 | 构建和链接 Keil 工程，并可按配置执行固件下载 |
| pyOCD、J-Link、实验性 probe-rs | 连接调试探针，控制目标并访问寄存器、内存、断点和 Flash |
| ELF/AXF、DWARF、SVD | 提供符号、源码、变量、调用栈和外设寄存器语义 |

MCP 不是“调用 Keil 的协议”。AI 通过 MCP 调用 `McuBuddy`；`McuBuddy` 再根据任务使用
Keil UV4、pyOCD、J-Link 或其他内部后端。

## 🚀 快速开始

### 1. 准备环境

基本要求：

- Python 3.10 或更高版本；
- 一块已供电的 MCU 开发板；
- 正确连接的 ST-Link、J-Link 或 CMSIS-DAP 探针；
- 目标芯片名称；
- 推荐准备带调试信息的 ELF/AXF。

只有在使用 Keil 构建或下载功能时，才需要 Windows 和已安装的 Keil MDK / UV4。

### 2. 安装

```bash
pip install McuBuddy
```

使用 J-Link Python 后端时安装可选依赖：

```bash
pip install "McuBuddy[jlink]"
```

从源码开发：

```bash
git clone https://github.com/cunjun/McuBuddy.git
cd McuBuddy
pip install -e ".[dev]"
```

### 3. 配置 MCP 客户端

```json
{
  "mcpServers": {
    "McuBuddy": {
      "command": "McuBuddy",
      "args": []
    }
  }
}
```

Windows 源码环境建议显式配置虚拟环境 Python 和工作目录，详见
[Windows MCP 配置示例](docs/windows-mcp-config-example.md)。配置后重新启动 AI 客户端。

### 4. 第一次只读检查

连接探针并给开发板供电后，可以直接告诉 AI：

```text
请使用 McuBuddy 检查当前调试环境，查找已连接的探针，并在不写入 Flash 的前提下
对开发板做第一次只读检查。开始前先告诉我还缺少哪些信息。
```

推荐先运行环境和目标预检，再配置探针并读取最小状态：

```text
doctor()
list_connected_probes()
match_chip_name("py32f030x8")
configure_probe(target="py32f030x8", backend="pyocd")
probe_connect(target="py32f030x8")
read_stopped_context()
```

`probe_connect` 和 `read_stopped_context` 均属于默认 `core` 配置档。读取稳定上下文时可能
暂停目标，因此仍属于执行状态变化。如果设备不能被暂停，应先告诉 AI 只做非侵入式探针和环境检查。

## 💬 AI 使用示例

这些提示词可以直接交给已连接 `McuBuddy` 的 AI 助手。

### 检查探针和开发板

```text
列出当前连接的调试探针，确认目标芯片是否匹配，然后对开发板执行一次只读检查。
不要复位、写内存或擦写 Flash；发现风险时先停下来说明。
```

### 定位 HardFault

```text
暂停目标，读取 PC、LR、SP 和故障寄存器，结合当前 AXF/ELF 解析调用栈，
判断 HardFault 最可能发生在哪段源码，并列出支持结论的证据。
```

### 构建 Keil 工程并继续调试

```text
在项目目录中查找 Keil 工程和 Target，先告诉我将使用哪个工程、哪个 Target 和哪个 UV4.exe。
确认后构建工程，加载生成的 AXF，但不要下载固件；随后通过探针运行到 main。
```

### 检查外设配置

```text
加载与目标芯片匹配的 SVD，读取 RCC、GPIOA 和 UART 外设状态，
检查时钟、引脚复用和中断配置是否一致，并说明异常字段。
```

### 检查 FreeRTOS 卡顿

```text
读取 FreeRTOS 任务列表、当前任务上下文和栈使用情况，找出阻塞、异常状态或栈风险，
不要修改目标状态。
```

更多证据驱动的提示词和决策顺序见 [AI Playbook](docs/ai-playbook.md) 与
[AI Examples](docs/ai-examples.md)。

## 🧰 能力与后端支持

### 能力分类

| 类别 | 主要能力 |
| --- | --- |
| 探针与目标 | 探针发现、目标匹配、连接/断开、暂停/继续、复位、单步 |
| CPU 与内存 | 核心/FPU/故障寄存器、内存读写、停止上下文、Flash 对比与校验 |
| 断点与执行 | 硬件/软件断点、观察点、运行到函数或源码行、Step Over/Out |
| 符号与源码 | ELF/AXF、DWARF、反汇编、函数与变量、源码定位、调用栈 |
| 外设与 RTOS | CMSIS-SVD、外设字段、FreeRTOS 任务、任务上下文、栈检查 |
| 日志与服务 | UART、RTT、部分 SWO、pyOCD/J-Link GDB Server |
| 工程与诊断 | Keil 工程发现、构建/下载、HardFault、启动、时钟、中断和外设诊断 |

完整工具名称、参数和返回值见 [Tool Reference](docs/tool-reference.md)。

### 后端支持状态

| 路径 | 当前定位 | 主要能力 |
| --- | --- | --- |
| pyOCD + ST-Link/CMSIS-DAP | 主要后端 | 控制、内存、Flash、源码调试、RTT、RTOS、GDB Server |
| J-Link | 主要后端 | 控制、内存、Flash、源码调试、原生 RTT、DWT、GDB Server |
| probe-rs sidecar | 实验性 | 发现、连接、核心控制、寄存器、内存、硬件断点 |
| Keil UV4（Windows） | 构建/下载后端 | 工程发现、Target 配置、构建、日志、可选下载 |

已重点验证：

- STM32L496VETx + ST-Link / pyOCD；
- STM32F103C8 + J-Link；
- 内置目标预检还包括 STM32F103ZE 和 PY32F030X8。

“代码已实现”不等于“所有板卡均已验证”。准确记录以
[Support Matrix](docs/support-matrix.md) 和 `list_validation_records()` 为准。

## 🔄 Keil MDK / UV4 工作流

Keil 在本项目中承担工程构建、链接和可选的固件下载。`McuBuddy` 不替代 Keil 编译器，
也不解析或重写工程构建规则；它负责发现工程、选择 Target、调用 UV4、读取日志与输出文件，
并把结果接入后续自动化调试。

```text
发现 Keil 工程
  → 配置 UV4、Target 和日志
  → 调用 Keil 构建
  → 加载生成的 AXF/ELF
  → 通过 pyOCD/J-Link 连接开发板并诊断
  → 用户确认后调用 Keil 下载
  → 重新连接并验证 Flash
```

### 1. 发现并配置工程

```text
discover_keil_projects(root=r"C:\path\to\app")

configure_keil_project(
    project_path=r"C:\path\to\app\MDK-ARM\Project.uvprojx",
    uv4_path=r"C:\Keil_v5\UV4\UV4.exe",
    target_name="Debug",
)
```

自动发现结果应由用户或 AI 检查。一个目录存在多个工程、Target 或输出文件时，建议显式传入
`project_path`、`target_name` 和 `elf_path`。

### 2. 构建并加载 AXF

```text
build_project(timeout_seconds=120)
configure_elf(elf_path=r"C:\path\to\app\MDK-ARM\Objects\Project.axf")
elf_load(path=r"C:\path\to\app\MDK-ARM\Objects\Project.axf")
```

加载 AXF 后，AI 才能稳定地把 PC、LR 和内存地址解析为函数、源码行、局部变量与调用栈。

### 3. 连接探针继续调试

```text
configure_probe(target="py32f030x8", backend="pyocd")
probe_connect(target="py32f030x8")
probe_halt()
read_stopped_context()
run_to_function("main")
```

如果 Keil、J-Link Commander、GDB Server 或其他调试器已经占用探针，应先关闭对应会话，
否则 pyOCD/J-Link 可能无法连接。

### 4. 下载与验证

`flash_firmware` 会调用配置好的 Keil UV4 下载流程并修改目标 Flash，因此必须明确确认：

```text
flash_firmware(timeout_seconds=120, confirm=True)
compare_elf_to_flash()
```

下载前应确认工程、Target、固件输出、芯片型号和恢复策略。更完整的新工程接入流程见
[Generic Board Workflow](docs/generic-board-workflow.md)。

## 🔍 常见调试流程

### 板卡无法启动或进入 HardFault

```text
probe_halt()
read_stopped_context(include_fault_registers=True)
diagnose_hardfault()
backtrace()
```

### 外设没有输出

```text
svd_load(svd_path=r"C:\path\Device.svd")
svd_read_peripheral(peripheral="RCC")
svd_read_peripheral(peripheral="GPIOA")
diagnose_peripheral_stuck(peripheral="UART")
```

### FreeRTOS 卡住

```text
list_rtos_tasks()
rtos_task_context(task_name="WorkerTask")
read_stack_usage()
```

### 运行到指定源码位置

```text
run_to_function("main")
run_to_source(file="main.c", line=120)
source_step()
step_over()
```

## 🛡️ 安全模型

`McuBuddy` 为工具提供机器可读的安全分类，可通过 `list_tool_safety()` 查询。

| 类别 | 例子 | 默认要求 |
| --- | --- | --- |
| 只读 | 目标匹配、寄存器/内存读取、符号解析、日志、诊断 | 不要求确认 |
| 执行状态变化 | halt、resume、reset、continue、单步 | 不写 Flash，但会改变运行状态 |
| 运行时状态写入 | 内存/寄存器写入、断点、观察点、SVD 字段写入 | 明确确认 |
| 持久性破坏操作 | Flash 擦除、编程、Keil 固件下载 | 明确确认 |
| 主机进程 | Keil 构建、GDB Server 启停 | 会启动或停止本机进程 |

安全原则：

1. 未知目标先匹配芯片和探针，不猜测地址。
2. 优先读取证据，再暂停、复位或写入。
3. Flash 操作前确认目标、范围、镜像和恢复方式。
4. 电机、继电器、电源开关等执行器优先使用断点和低能量测试。

## 🔒 Session 与并发行为

- 同一个 `Session` 中，共享探针、Keil、ELF/SVD、日志和运行配置的操作会串行执行。
- 不同 Session 可以并行，适合互不相关的多块开发板。
- 目标匹配、工具安全信息等无状态查询可以与 Session 操作并发。
- 取消请求不能强行终止已经进入同步 SDK 的调用；服务器会等工作线程结束后再释放 Session 锁。

这可以避免一个探针操作尚未完成时，另一个请求同时切换后端、断开连接或修改共享状态。

## 📦 mcubug Skill

仓库包含 `skills/mcubug`，用于指导 Codex 和 Claude Code 按“先证据、后判断”的顺序使用
这些工具，而不是把 MCP 工具当作无序命令列表。

安装到 Codex：

```powershell
python .\skills\mcubug\scripts\install_skill.py --target codex --overwrite
```

安装到 Claude Code：

```powershell
python .\skills\mcubug\scripts\install_skill.py --target cc --overwrite
```

安装完成后重启客户端或新建会话。详细说明见
[mcubug Skill for Codex and Claude Code](docs/mcubug-skill.md)。

## ⚠️ 当前限制

- Keil 构建和下载目前面向 Windows + Keil UV4。
- probe-rs sidecar 仍是实验性后端，尚未覆盖 Flash、RTT、SWO 和正式发布二进制。
- RTOS 检查依赖与目标固件匹配的 FreeRTOS 符号和 ELF/AXF。
- SVD 文件不随所有芯片自动提供，通常需要来自 CMSIS-Pack 或芯片厂商。
- SWO 文本捕获受芯片配置、探针能力、引脚复用和板级接线影响。
- 设备补丁和连接策略仍是轻量机制，不是完整的板卡插件系统。

## 📚 文档导航

- 第一次使用：[Quickstart](docs/quickstart.md)
- 接入任意板卡和 Keil 工程：[Generic Board Workflow](docs/generic-board-workflow.md)
- Windows MCP 配置：[Windows MCP Configuration](docs/windows-mcp-config-example.md)
- AI 调试决策顺序：[AI Playbook](docs/ai-playbook.md)
- 常见场景示例：[AI Examples](docs/ai-examples.md)
- 完整工具索引：[Tool Reference](docs/tool-reference.md)
- 后端与硬件验证：[Support Matrix](docs/support-matrix.md)
- 项目架构：[Architecture](docs/architecture.md)
- Skill 安装维护：[mcubug Skill](docs/mcubug-skill.md)
- v0.5.2 发布摘要：[v0.5.2 Release Notes](docs/releases/v0.5.2.md)

## 🧪 本地开发

```bash
pip install -e ".[dev]"
pytest
ruff check src tests
```

项目目录约定和贡献文档归属见 [Docs Index](docs/README.md)。

## 🙏 上游来源与致谢

McuBuddy 基于 [SolarWang233/mcudbg](https://github.com/SolarWang233/mcudbg) 开发，并在其
MIT License 授权的代码基础上扩展了架构、安全边界、证据工作流、后端支持和文档。
原始版权声明保留在 [LICENSE](LICENSE) 中，来源详情见 [NOTICE](NOTICE)。

## 📄 License

本项目采用 MIT License，详见 [LICENSE](LICENSE)。

---

如果 `McuBuddy` 对你的 MCU 调试工作有帮助，欢迎给项目一个 Star。
