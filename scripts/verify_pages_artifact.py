"""Require the uploaded Pages artifact to be visible in this exact workflow run."""
import argparse
import json
import os
import subprocess
import time

def verify(payload, artifact_id, name):
    matches = [a for a in payload.get("artifacts", []) if a.get("name") == name and not a.get("expired")]
    if len(matches) != 1 or str(matches[0].get("id")) != str(artifact_id) or matches[0].get("size_in_bytes", 0) <= 0:
        raise ValueError("Pages upload not visible as one nonempty, unexpired artifact with the expected ID")
    return matches[0]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-id", required=True)
    parser.add_argument("--name", default="github-pages")
    args = parser.parse_args()
    if not args.artifact_id.isdecimal():
        raise SystemExit("Pages upload did not return an artifact ID")
    endpoint = f"repos/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}/artifacts?per_page=100"
    for attempt in range(4):
        response = subprocess.run(["gh", "api", endpoint], capture_output=True, text=True)
        try:
            if response.returncode:
                raise ValueError("Cannot read artifact metadata")
            artifact = verify(json.loads(response.stdout), args.artifact_id, args.name)
            print(json.dumps({"status": "ARTIFACT_READBACK_PASS", "id": artifact["id"], "name": artifact["name"]}))
            return 0
        except (ValueError, KeyError):
            if attempt == 3:
                raise SystemExit("Pages artifact readback failed; deployment blocked")
            time.sleep(5)

if __name__ == "__main__":
    raise SystemExit(main())
