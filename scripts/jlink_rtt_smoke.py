from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from McuBubby.session import create_default_session  # noqa: E402
from McuBubby.tools.configuration import configure_probe  # noqa: E402
from McuBubby.tools.probe import connect_probe, disconnect_probe, read_rtt_log  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safe J-Link RTT smoke test with bounded polling and guaranteed disconnect."
    )
    parser.add_argument("--target", required=True, help="Target name, for example STM32F103C8")
    parser.add_argument("--serial", help="Optional J-Link serial number")
    parser.add_argument("--channel", type=int, default=0, help="RTT up-buffer channel")
    parser.add_argument("--max-bytes", type=int, default=512, help="Max RTT bytes to read per attempt")
    parser.add_argument(
        "--attempts",
        type=int,
        default=5,
        help="Number of RTT polling attempts before giving up",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=0.5,
        help="Delay between RTT polling attempts",
    )
    parser.add_argument(
        "--require-text",
        action="store_true",
        help="Fail unless at least one RTT read returns non-empty text",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    session = create_default_session()
    connected = False
    history: list[dict] = []

    try:
        config_result = configure_probe(
            session,
            backend="jlink",
            target=args.target,
            unique_id=args.serial,
        )
        print(json.dumps({"phase": "configure", "result": config_result}, ensure_ascii=False))
        if config_result.get("status") != "ok":
            return 2

        connect_result = connect_probe(
            session,
            target=args.target,
            unique_id=args.serial,
        )
        print(json.dumps({"phase": "connect", "result": connect_result}, ensure_ascii=False))
        if connect_result.get("status") != "ok":
            return 3
        connected = True

        for attempt in range(1, args.attempts + 1):
            result = read_rtt_log(
                session,
                channel=args.channel,
                max_bytes=args.max_bytes,
            )
            history.append(result)
            print(
                json.dumps(
                    {
                        "phase": "read_rtt_log",
                        "attempt": attempt,
                        "result": result,
                    },
                    ensure_ascii=False,
                )
            )
            if result.get("status") == "ok" and result.get("text"):
                return 0
            if attempt < args.attempts:
                time.sleep(args.delay_seconds)

        if args.require_text:
            return 4

        for result in history:
            if result.get("status") == "ok":
                return 0
        return 5
    except KeyboardInterrupt:
        print(
            json.dumps(
                {
                    "phase": "interrupted",
                    "result": {
                        "status": "error",
                        "summary": "Interrupted by user.",
                    },
                },
                ensure_ascii=False,
            )
        )
        return 130
    except Exception as exc:
        print(
            json.dumps(
                {
                    "phase": "exception",
                    "result": {
                        "status": "error",
                        "summary": str(exc),
                    },
                },
                ensure_ascii=False,
            )
        )
        return 1
    finally:
        if connected:
            disconnect_result = disconnect_probe(session)
            print(
                json.dumps(
                    {"phase": "disconnect", "result": disconnect_result},
                    ensure_ascii=False,
                )
            )


if __name__ == "__main__":
    raise SystemExit(main())
