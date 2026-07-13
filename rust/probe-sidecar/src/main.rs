use std::io::{self, BufRead, Write};

use mcudubby_probe_sidecar::{handle_request_line, SidecarState};

fn main() {
    let stdin = io::stdin();
    let mut stdout = io::stdout().lock();
    let mut state = SidecarState::default();
    for line in stdin.lock().lines() {
        let response = match line {
            Ok(line) => handle_request_line(&mut state, &line),
            Err(error) => format!(
                r#"{{"jsonrpc":"2.0","id":null,"error":{{"code":-32000,"message":"stdin error: {error}"}}}}"#
            ),
        };
        if writeln!(stdout, "{response}").is_err() || stdout.flush().is_err() {
            break;
        }
    }
}
