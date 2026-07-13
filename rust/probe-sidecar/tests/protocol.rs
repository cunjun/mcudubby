use mcudubby_probe_sidecar::{canonical_register_name, handle_request_line, SidecarState};
use serde_json::{json, Value};

#[test]
fn hello_reports_compatible_protocol_version() {
    let mut state = SidecarState::default();
    let response = handle_request_line(
        &mut state,
        r#"{"jsonrpc":"2.0","id":1,"method":"hello","params":{"protocol_version":1}}"#,
    );
    let value: Value = serde_json::from_str(&response).unwrap();

    assert_eq!(value["jsonrpc"], "2.0");
    assert_eq!(value["id"], 1);
    assert_eq!(value["result"]["protocol_version"], 1);
}

#[test]
fn unknown_method_returns_json_rpc_method_not_found() {
    let mut state = SidecarState::default();
    let response = handle_request_line(
        &mut state,
        &json!({"jsonrpc": "2.0", "id": 7, "method": "missing", "params": {}}).to_string(),
    );
    let value: Value = serde_json::from_str(&response).unwrap();

    assert_eq!(value["id"], 7);
    assert_eq!(value["error"]["code"], -32601);
}

#[test]
fn cortex_m_register_names_match_mcudubby_contract() {
    assert_eq!(canonical_register_name("R15"), "pc");
    assert_eq!(canonical_register_name("R14"), "lr");
    assert_eq!(canonical_register_name("R13"), "sp");
    assert_eq!(canonical_register_name("XPSR"), "xpsr");
    assert_eq!(canonical_register_name("R0"), "r0");
}
