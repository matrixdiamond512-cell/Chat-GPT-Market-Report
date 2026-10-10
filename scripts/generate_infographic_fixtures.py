"""Generate nonproduction synthetic infographic layout fixtures."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from reporting.infographic_fixtures import build_synthetic_fixture
from reporting.infographic_renderer import render_infographic

OUT = ROOT / "artifacts" / "infographic-quality-v1"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for slot in ("08:00", "12:00", "16:00", "21:00"):
        source = build_synthetic_fixture(slot)
        key = f"{source['report_id']}"
        png = OUT / f"synthetic_{key}.png"
        result = render_infographic(source, png)
        metadata = {key: value for key, value in result.items() if key != "image_bytes"}
        metadata["output_file"] = png.name if result.get("image_sha256") else None
        (OUT / f"synthetic_{key}.validation.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        quality = result.get("quality_score", {}).get("total", "N/A")
        print(f"{slot} {result['status']} {metadata['output_file'] or 'PNG_NOT_WRITTEN'} {result.get('image_sha256')} {quality}/30")


if __name__ == "__main__":
    main()
