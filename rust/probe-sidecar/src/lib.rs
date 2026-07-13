use std::collections::BTreeMap;
use std::time::Duration;

use base64::engine::general_purpose::STANDARD as BASE64;
use base64::Engine;
use probe_rs::probe::list::Lister;
use probe_rs::{CoreStatus, MemoryInterface, Permissions, RegisterValue, Session};
use serde::Deserialize;
use serde_json::{json, Value};
use uuid::Uuid;

pub const PROTOCOL_VERSION: u64 = 1;

#[derive(Default)]
pub struct SidecarState {
    session: Option<ActiveSession>,
}

struct ActiveSession {
    id: String,
    target: String,
    session: Session,
}

#[derive(Deserialize)]
struct Request {
    jsonrpc: String,
    id: Value,
    method: String,
    #[serde(default)]
    params: Value,
}

pub fn handle_request_line(state: &mut SidecarState, line: &str) -> String {
    let request = match serde_json::from_str::<Request>(line) {
        Ok(request) => request,
        Err(error) => {
            return json!({
                "jsonrpc": "2.0",
                "id": Value::Null,
                "error": {"code": -32700, "message": format!("invalid JSON: {error}")}
            })
            .to_string();
        }
    };
    let id = request.id.clone();
    if request.jsonrpc != "2.0" {
        return error_response(id, -32600, "jsonrpc must be '2.0'");
    }
    match dispatch(state, &request.method, &request.params) {
        Ok(result) => json!({"jsonrpc": "2.0", "id": id, "result": result}).to_string(),
        Err(RpcFailure::MethodNotFound(message)) => error_response(id, -32601, &message),
        Err(RpcFailure::InvalidParams(message)) => error_response(id, -32602, &message),
        Err(RpcFailure::Operation(message)) => error_response(id, -32000, &message),
    }
}

enum RpcFailure {
    MethodNotFound(String),
    InvalidParams(String),
    Operation(String),
}

fn error_response(id: Value, code: i64, message: &str) -> String {
    json!({"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}).to_string()
}

fn dispatch(state: &mut SidecarState, method: &str, params: &Value) -> Result<Value, RpcFailure> {
    match method {
        "hello" => hello(params),
        "list_probes" => list_probes(),
        "connect" => connect(state, params),
        "disconnect" => disconnect(state, params),
        "halt" => with_core(state, params, |core| {
            core.halt(Duration::from_secs(1)).map_err(operation_error)?;
            Ok(json!({"state": "halted"}))
        }),
        "resume" => with_core(state, params, |core| {
            core.run().map_err(operation_error)?;
            Ok(json!({"state": "running"}))
        }),
        "reset" => reset(state, params),
        "step" => with_core(state, params, |core| {
            core.step().map_err(operation_error)?;
            Ok(json!({"state": "halted"}))
        }),
        "get_state" => with_core(state, params, |core| {
            let status = core.status().map_err(operation_error)?;
            Ok(json!({"state": status_name(status)}))
        }),
        "read_core_registers" => read_core_registers(state, params),
        "read_memory" => read_memory(state, params),
        "write_memory" => write_memory(state, params),
        "set_breakpoint" => breakpoint(state, params, true),
        "clear_breakpoint" => breakpoint(state, params, false),
        _ => Err(RpcFailure::MethodNotFound(format!(
            "unknown method '{method}'"
        ))),
    }
}

fn hello(params: &Value) -> Result<Value, RpcFailure> {
    let requested = optional_u64(params, "protocol_version")?.unwrap_or(PROTOCOL_VERSION);
    if requested != PROTOCOL_VERSION {
        return Err(RpcFailure::Operation(format!(
            "unsupported protocol version {requested}"
        )));
    }
    Ok(json!({
        "protocol_version": PROTOCOL_VERSION,
        "sidecar_version": env!("CARGO_PKG_VERSION")
    }))
}

fn list_probes() -> Result<Value, RpcFailure> {
    let probes = Lister::new()
        .list_all()
        .into_iter()
        .map(|probe| {
            json!({
                "unique_id": probe.serial_number,
                "description": probe.identifier,
                "vendor_id": probe.vendor_id,
                "product_id": probe.product_id,
                "probe_type": format!("{:?}", probe.probe_type())
            })
        })
        .collect::<Vec<_>>();
    Ok(json!(probes))
}

fn connect(state: &mut SidecarState, params: &Value) -> Result<Value, RpcFailure> {
    if state.session.is_some() {
        return Err(RpcFailure::Operation(
            "a probe-rs session is already connected".to_string(),
        ));
    }
    let target = required_str(params, "target")?.to_string();
    let unique_id = optional_str(params, "unique_id")?;
    let probes = Lister::new().list_all();
    let probe_info = probes
        .into_iter()
        .find(|probe| {
            unique_id.is_none_or(|wanted| {
                probe.serial_number.as_deref() == Some(wanted) || probe.identifier.contains(wanted)
            })
        })
        .ok_or_else(|| RpcFailure::Operation("no matching debug probe found".to_string()))?;
    let description = probe_info.identifier.clone();
    let mut probe = probe_info.open().map_err(operation_error)?;
    let actual_speed_khz = probe.set_speed(1_000).map_err(operation_error)?;
    let mut session = probe
        .attach(&target, Permissions::new())
        .map_err(operation_error)?;
    session
        .core(0)
        .map_err(operation_error)?
        .halt(Duration::from_secs(1))
        .map_err(operation_error)?;
    let session_id = Uuid::new_v4().to_string();
    state.session = Some(ActiveSession {
        id: session_id.clone(),
        target: target.clone(),
        session,
    });
    Ok(json!({
        "session_id": session_id,
        "target": target,
        "probe": description,
        "speed_khz": actual_speed_khz
    }))
}

fn disconnect(state: &mut SidecarState, params: &Value) -> Result<Value, RpcFailure> {
    require_session_id(state, params)?;
    let session = state.session.take().expect("session checked above");
    Ok(json!({"session_id": session.id, "target": session.target}))
}

fn reset(state: &mut SidecarState, params: &Value) -> Result<Value, RpcFailure> {
    let halt = optional_bool(params, "halt")?.unwrap_or(false);
    with_core(state, params, |core| {
        if halt {
            core.reset_and_halt(Duration::from_secs(1))
                .map_err(operation_error)?;
        } else {
            core.reset().map_err(operation_error)?;
        }
        Ok(json!({"state": if halt { "halted" } else { "running" }}))
    })
}

fn read_core_registers(state: &mut SidecarState, params: &Value) -> Result<Value, RpcFailure> {
    with_core(state, params, |core| {
        let descriptions = core.registers().core_registers().collect::<Vec<_>>();
        let mut registers = BTreeMap::new();
        for register in descriptions {
            if let Ok(value) = core.read_core_reg(register) {
                if let Ok(value) = <RegisterValue as TryInto<u64>>::try_into(value) {
                    registers.insert(canonical_register_name(register.name()), value);
                }
            }
        }
        Ok(json!({"registers": registers}))
    })
}

pub fn canonical_register_name(name: &str) -> String {
    match name.to_ascii_uppercase().as_str() {
        "R15" => "pc".to_string(),
        "R14" => "lr".to_string(),
        "R13" => "sp".to_string(),
        _ => name.to_ascii_lowercase(),
    }
}

fn read_memory(state: &mut SidecarState, params: &Value) -> Result<Value, RpcFailure> {
    let address = required_u64(params, "address")?;
    let size = required_u64(params, "size")? as usize;
    if size > 1024 * 1024 {
        return Err(RpcFailure::InvalidParams(
            "memory read size exceeds 1 MiB".to_string(),
        ));
    }
    with_core(state, params, |core| {
        let mut data = vec![0_u8; size];
        core.read(address, &mut data).map_err(operation_error)?;
        Ok(json!({"data_base64": BASE64.encode(data), "size": size}))
    })
}

fn write_memory(state: &mut SidecarState, params: &Value) -> Result<Value, RpcFailure> {
    let address = required_u64(params, "address")?;
    let encoded = required_str(params, "data_base64")?;
    let data = BASE64
        .decode(encoded)
        .map_err(|error| RpcFailure::InvalidParams(format!("invalid base64 data: {error}")))?;
    if data.len() > 64 * 1024 {
        return Err(RpcFailure::InvalidParams(
            "memory write size exceeds 64 KiB".to_string(),
        ));
    }
    with_core(state, params, |core| {
        core.write(address, &data).map_err(operation_error)?;
        Ok(json!({"bytes_written": data.len()}))
    })
}

fn breakpoint(state: &mut SidecarState, params: &Value, set: bool) -> Result<Value, RpcFailure> {
    let address = required_u64(params, "address")?;
    with_core(state, params, |core| {
        if set {
            core.set_hw_breakpoint(address).map_err(operation_error)?;
        } else {
            core.clear_hw_breakpoint(address).map_err(operation_error)?;
        }
        Ok(json!({"address": address}))
    })
}

fn with_core<F>(state: &mut SidecarState, params: &Value, operation: F) -> Result<Value, RpcFailure>
where
    F: FnOnce(&mut probe_rs::Core<'_>) -> Result<Value, RpcFailure>,
{
    require_session_id(state, params)?;
    let active = state.session.as_mut().expect("session checked above");
    let mut core = active.session.core(0).map_err(operation_error)?;
    operation(&mut core)
}

fn require_session_id(state: &SidecarState, params: &Value) -> Result<(), RpcFailure> {
    let requested = required_str(params, "session_id")?;
    let active = state
        .session
        .as_ref()
        .ok_or_else(|| RpcFailure::Operation("no active probe-rs session".to_string()))?;
    if active.id != requested {
        return Err(RpcFailure::Operation("unknown session_id".to_string()));
    }
    Ok(())
}

fn required_str<'a>(params: &'a Value, name: &str) -> Result<&'a str, RpcFailure> {
    params
        .get(name)
        .and_then(Value::as_str)
        .ok_or_else(|| RpcFailure::InvalidParams(format!("'{name}' must be a string")))
}

fn optional_str<'a>(params: &'a Value, name: &str) -> Result<Option<&'a str>, RpcFailure> {
    match params.get(name) {
        None | Some(Value::Null) => Ok(None),
        Some(value) => value
            .as_str()
            .map(Some)
            .ok_or_else(|| RpcFailure::InvalidParams(format!("'{name}' must be a string"))),
    }
}

fn required_u64(params: &Value, name: &str) -> Result<u64, RpcFailure> {
    params
        .get(name)
        .and_then(Value::as_u64)
        .ok_or_else(|| RpcFailure::InvalidParams(format!("'{name}' must be an unsigned integer")))
}

fn optional_u64(params: &Value, name: &str) -> Result<Option<u64>, RpcFailure> {
    match params.get(name) {
        None | Some(Value::Null) => Ok(None),
        Some(value) => value.as_u64().map(Some).ok_or_else(|| {
            RpcFailure::InvalidParams(format!("'{name}' must be an unsigned integer"))
        }),
    }
}

fn optional_bool(params: &Value, name: &str) -> Result<Option<bool>, RpcFailure> {
    match params.get(name) {
        None | Some(Value::Null) => Ok(None),
        Some(value) => value
            .as_bool()
            .map(Some)
            .ok_or_else(|| RpcFailure::InvalidParams(format!("'{name}' must be a boolean"))),
    }
}

fn status_name(status: CoreStatus) -> &'static str {
    match status {
        CoreStatus::Running => "running",
        CoreStatus::Halted(_) => "halted",
        CoreStatus::LockedUp => "locked-up",
        CoreStatus::Sleeping => "sleeping",
        CoreStatus::Unknown => "unknown",
    }
}

fn operation_error(error: impl std::fmt::Display) -> RpcFailure {
    RpcFailure::Operation(error.to_string())
}
