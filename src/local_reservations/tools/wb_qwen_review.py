"""Obtain source-pinned second readings from a local Ollama vision model.

This writes review evidence only. It never replaces reservation/name records.
API: https://docs.ollama.com/api/generate
"""

import argparse
import base64
import hashlib
import io
import json
import time
from pathlib import Path

import requests
from PIL import Image

from local_reservations.common.runlog import command

PROMPT = (
    "Transcribe only the text visibly printed in this cropped election-table cell. "
    "Preserve original spelling, Bengali script, Roman numerals, and reservation "
    "codes. Do not correct or complete place names. If blank or only a dash, return "
    "an empty text string. Mark unreadable characters with [?]. "
    'Return JSON with one key: "text". Do not infer reservation from a name.'
)


def fingerprint(image_bytes, model_digest, prompt):
    return {
        "image_sha256": hashlib.sha256(image_bytes).hexdigest(),
        "model_digest": model_digest,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "temperature": 0,
        "num_predict": 512,
    }


@command("ocr", state="West Bengal", source="local_qwen_vision")
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--model", default="qwen2.5vl:7b")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    url = "http://127.0.0.1:11434"
    session = requests.Session()
    session.trust_env = False
    response = session.get(url + "/api/tags", timeout=20)
    response.raise_for_status()
    model = next(r for r in response.json()["models"] if r["name"] == args.model)
    args.output.mkdir(parents=True, exist_ok=True)
    entries = json.loads(args.manifest.read_text())
    for i, entry in enumerate(entries, 1):
        image = Path(entry["image_path"]).read_bytes()
        if (
            entry.get("image_sha256")
            and hashlib.sha256(image).hexdigest() != entry["image_sha256"]
        ):
            raise ValueError("Frozen sample image hash changed")
        rotation = entry.get("image_rotation_clockwise", 0)
        if rotation not in {0, 90, 180, 270}:
            raise ValueError("Unsupported source orientation")
        if rotation:
            with Image.open(io.BytesIO(image)) as original:
                rotated = original.rotate(-rotation, expand=True)
                encoded = io.BytesIO()
                rotated.save(encoded, format="PNG")
                image = encoded.getvalue()
        key = fingerprint(image, model["digest"], PROMPT)
        digest = hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()
        target = args.output / f"{digest}.json"
        if target.exists():
            print(
                json.dumps({"item": i, "status": "cached", "cache": str(target)}),
                flush=True,
            )
            continue
        started = time.monotonic()
        response = session.post(
            url + "/api/generate",
            json={
                "model": args.model,
                "prompt": PROMPT,
                "images": [base64.b64encode(image).decode()],
                "stream": False,
                "format": "json",
                "options": {"temperature": 0, "num_predict": 512},
                "keep_alive": "10m",
            },
            timeout=600,
        )
        response.raise_for_status()
        body = response.json()
        result = {
            "source": entry,
            "fingerprint": key,
            "prompt": PROMPT,
            "response": body,
            "seconds": time.monotonic() - started,
        }
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(
            json.dumps(
                {
                    "item": i,
                    "seconds": result["seconds"],
                    "reading": body.get("response"),
                    "cache": str(target),
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
