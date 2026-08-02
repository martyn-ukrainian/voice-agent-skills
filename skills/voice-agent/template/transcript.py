"""
Local transcript collector. Subscribes to the pipecat TranscriptProcessor and
saves utterances to a VTT + JSON file.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from loguru import logger


class TranscriptCollector:
    def __init__(self, session_id: str, out_dir: str = "./transcripts"):
        self.session_id = session_id
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.session_start: Optional[datetime] = None
        self.messages: list[dict] = []

    def start_session(self, started_at: Optional[datetime] = None):
        self.session_start = started_at or datetime.now(timezone.utc)
        logger.info(f"Transcript session started at {self.session_start.isoformat()}")

    def add_utterance(self, role: str, text: str, ts: Optional[datetime] = None):
        if not text.strip():
            return
        now = ts or datetime.now(timezone.utc)
        if self.session_start is None:
            self.start_session(now)
        offset = now - self.session_start
        self.messages.append(
            {
                "role": role,
                "text": text.strip(),
                "offset_seconds": offset.total_seconds(),
                "ts": now.isoformat(),
            }
        )

    def save(self) -> dict[str, str]:
        json_path = self.out_dir / f"{self.session_id}.json"
        vtt_path = self.out_dir / f"{self.session_id}.vtt"

        json_path.write_text(
            json.dumps(
                {
                    "session_id": self.session_id,
                    "started_at": self.session_start.isoformat()
                    if self.session_start
                    else None,
                    "messages": self.messages,
                },
                ensure_ascii=False,
                indent=2,
            )
        )

        lines = ["WEBVTT", ""]
        for i, m in enumerate(self.messages, start=1):
            start = timedelta(seconds=m["offset_seconds"])
            end = start + timedelta(seconds=max(2.0, len(m["text"]) / 15))
            lines.append(str(i))
            lines.append(f"{_fmt_vtt(start)} --> {_fmt_vtt(end)}")
            lines.append(f"<v {m['role']}>{m['text']}")
            lines.append("")
        vtt_path.write_text("\n".join(lines))

        logger.info(f"Transcript saved: {json_path}, {vtt_path}")
        return {"json": str(json_path), "vtt": str(vtt_path)}


def _fmt_vtt(td: timedelta) -> str:
    total_ms = int(td.total_seconds() * 1000)
    h, rem = divmod(total_ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"
