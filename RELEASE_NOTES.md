# mcudubby v0.5.0

`mcudubby` v0.5.0 重点加强并发执行、硬件操作安全边界、构建结果可信度和发布验证。

## 本版本包含

- 阻塞式 MCP 工具转移到工作线程，避免探针调用阻塞事件循环。
- 同一会话的硬件操作串行化，不同会话仍可并行执行。
- Keil 构建和烧录同时校验进程返回码与本次生成的日志，避免旧日志误报成功。
- smoke/first-contact 工具按实际行为标记为会改变目标执行状态。
- pyOCD GDB server 远程绑定新增显式确认，默认继续仅监听本机。
- CI 新增 Windows、Rust sidecar、脚本 lint 和 skill 参考文档漂移检查。
- GitHub Release 自动构建并附加 wheel 与源码包。

## 安装

```bash
pip install mcudubby
```

也可以从本 Release 下载附件安装：

- `mcudubby-0.5.0-py3-none-any.whl`
- `mcudubby-0.5.0.tar.gz`

## 注意事项

涉及真实硬件的功能依赖本机探针驱动、板卡接线、目标固件符号文件，以及可选后端依赖，例如 `pylink-square`。远程开放 GDB server 前请确认网络边界可信。
