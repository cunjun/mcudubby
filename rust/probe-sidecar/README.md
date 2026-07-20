# McuBubby probe sidecar

This Rust binary provides the experimental `probe-rs` execution backend for McuBubby.
It communicates with the Python MCP server using newline-delimited JSON-RPC 2.0 over stdio.

Build it with:

```powershell
cargo build --release --manifest-path rust/probe-sidecar/Cargo.toml
```

Then configure McuBubby with the resulting executable:

```text
configure_probe(
    backend="probe-rs",
    target="STM32F103C8",
    probe_rs_sidecar_path="rust/probe-sidecar/target/release/McuBubby-probe-sidecar.exe",
)
```

The current protocol covers probe discovery, connection lifecycle, core control, core registers,
memory access, and hardware breakpoints. Flash, RTT, SWO, and hardware validation are intentionally
deferred to later slices.
