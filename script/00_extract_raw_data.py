import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


REQUIRED_KEYS = {"rtctime", "rawdata", "serial"}


def extract_json_from_line(line: str) -> Optional[Dict[str, Any]]:
    """Extract JSON object from a log line."""
    start = line.find("{")
    end = line.rfind("}")
    if start == -1 or end == -1 or start >= end:
        return None

    candidate = line[start : end + 1]
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None
    return payload


def is_valid_payload(payload: Dict[str, Any]) -> bool:
    """Check whether payload contains all required keys."""
    return REQUIRED_KEYS.issubset(payload.keys())


def parse_log_file(input_log: Path) -> List[Dict[str, Any]]:
    """Read log file and keep valid JSON objects."""
    valid_items: List[Dict[str, Any]] = []
    with input_log.open("r", encoding="utf-8") as f:
        for line in f:
            payload = extract_json_from_line(line.strip())
            if payload and is_valid_payload(payload):
                valid_items.append(payload)
    return valid_items


def write_output(output_log: Path, data: List[Dict[str, Any]]) -> None:
    """Write extracted data as JSON array."""
    output_log.parent.mkdir(parents=True, exist_ok=True)
    with output_log.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract valid raw JSON payloads from log file."
    )
    parser.add_argument(
        "--input_log",        
        default="Log/190125070005457.log",
        help="Input log file path, e.g. 190124110002379-1.log",
    )
    parser.add_argument(
        "--output_log",
        default="Log/raw.json",        
        help="Output JSON path, e.g. Log/raw.json",
    )
    args = parser.parse_args()

    input_path = Path(args.input_log)
    output_path = Path(args.output_log)

    if not input_path.exists():
        raise FileNotFoundError(f"Input log file not found: {input_path}")

    data = parse_log_file(input_path)
    write_output(output_path, data)
    print(f"Extracted {len(data)} valid JSON records to {output_path}")


if __name__ == "__main__":
    main()
