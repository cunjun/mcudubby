# Generic Board Workflow

Use this workflow when bringing up a board that is not one of the built-in demo targets.
The intent is to keep target-specific details in configuration, not in hard-coded Python
branches.

## Concepts

- `backend`: debug backend, currently `pyocd` or `jlink`.
- `target`: backend target name, such as a pyOCD target ID from `list --targets`.
- `pack_path` / `pack_paths`: local CMSIS-Pack files used by pyOCD when the target is not
  built in.
- `connect_attempts`: ordered fallback attempts for frequency and reset/connect mode.
- `elf_path`: `.elf` or Keil `.axf` image used for symbols, source mapping, and backtrace.
- `uv4_path`: Keil `UV4.exe` path, only needed for `build_project` and `flash_firmware`.

## 1. Find the probe and target

Start with non-destructive discovery:

```python
list_connected_probes()
list_supported_targets("pyocd")
match_chip_name("your_mcu_name", backend="pyocd")
```

For pyOCD targets supplied by a CMSIS-Pack, verify the pack with pyOCD first:

```powershell
pyocd list --targets --pack C:\path\Vendor.Device.1.0.0.pack
```

Use the exact target ID reported by pyOCD when configuring `mcudubby`.

## 2. Configure the probe

For a CMSIS-DAP probe and a target supplied by a CMSIS-Pack:

```python
configure_probe(
    target="PY32F030X8",
    backend="pyocd",
    unique_id="LU_2022_8888",
    pack_path=r"E:\work_code\mcudubby\packs\Puya.PY32F0xx_DFP.1.2.8.pack",
    connect_attempts=[
        {"frequency": 100000, "connect_mode": "attach"},
        {"frequency": 100000, "connect_mode": "under-reset"},
    ],
)
```

Use `pack_paths=[...]` when more than one pack is needed. The paths are passed directly to
pyOCD, so they can point anywhere on the local machine.
For `PY32F030X8`, mcudubby can also auto-discover `Puya.PY32F0xx_DFP.*.pack` from a
local `packs/` directory.

## 3. Discover the Keil project and firmware image

If the firmware is built with Keil MDK:

```python
discover_keil_projects(r"E:\work_code\your_project_root")
configure_keil_project(
    root=r"E:\work_code\your_project_root",
    uv4_path=r"E:\Keil_v5\UV4\UV4.exe",
)
```

`configure_keil_project` reads `.uvprojx` / `.uvoptx`, selects the first target if one is not
provided, searches common output directories plus the project's configured `OutputDirectory`,
and configures the selected `.axf` / `.elf` for symbol loading.

If auto-discovery picks the wrong item, pass explicit values:

```python
configure_keil_project(
    project_path=r"E:\work_code\app\MDK-ARM\Project.uvprojx",
    target_name="Debug",
    elf_path=r"E:\work_code\app\MDK-ARM\Objects\Project.axf",
    uv4_path=r"E:\Keil_v5\UV4\UV4.exe",
)
```

## 4. Run a smoke test

Before flashing or making deeper assumptions, run:

```python
board_smoke_test(disconnect_after=True)
```

The smoke test lists probes, loads the configured ELF/AXF if available, connects, optionally
halts the target, reads stopped context, and reads a few vector-table words. Connecting and
halting changes the target execution state; `disconnect_after=True` closes the probe afterward.
It is meant as a first sanity check, not a replacement for feature validation.

## 5. Continue into debugging

Once the smoke test can connect and read state:

```python
probe_connect(target="py32f030x8")
read_stopped_context()
diagnose("board does not boot")
run_to_function("main")
svd_load(r"C:\path\Device.svd")
svd_read_peripheral("RCC")
```

For build and flash workflows:

```python
build_project()
flash_firmware()
compare_elf_to_flash()
```

## Troubleshooting

- `No ACK` from SWD usually means the probe enumerates but the target did not answer. Check
  target power, SWDIO/SWCLK/GND wiring, reset wiring, whether Keil already owns the probe, and
  whether firmware repurposed SWD pins.
- Try a lower frequency and `under-reset` before assuming the target ID is wrong.
- Keep downloaded packs and local `pyocd.yaml` files out of source control. They are machine
  setup, not portable project state.
- UART is optional for probe bring-up. Configure it only when a log-based diagnosis needs it.
