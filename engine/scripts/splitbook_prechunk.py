#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

CHAPTER_RE = re.compile(r"^\s*(第[0-9零一二三四五六七八九十百千万两]+[章回节卷].*|chapter\s+\d+.*)$", re.IGNORECASE)


def detect_encoding(path: Path, preferred: str | None = None) -> str:
    candidates: list[str] = []
    if preferred:
        candidates.append(preferred)
    candidates.extend(["utf-8", "utf-8-sig", "ascii", "gb18030", "big5", "shift_jis", "latin-1"])
    sample = path.read_bytes()[:65536]
    if sample.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    for enc in candidates:
        try:
            sample.decode(enc)
            return enc
        except Exception:
            continue
    return "utf-8"


def hard_split(text_value: str, chunk_size: int, overlap: int) -> list[str]:
    content = text_value.strip()
    if not content:
        return []
    if len(content) <= chunk_size:
        return [content]
    step = max(1, chunk_size - overlap)
    out: list[str] = []
    idx = 0
    while idx < len(content):
        piece = content[idx : idx + chunk_size].strip()
        if piece:
            out.append(piece)
        idx += step
    return out


def iter_chunks(path: Path, encoding: str, chunk_size: int, overlap: int):
    chapter_no = 0
    chapter_title = "未分章"
    paragraph_buf: list[str] = []
    current_chunk = ""
    overlap_seed = ""

    def flush_paragraph() -> str:
        nonlocal paragraph_buf
        if not paragraph_buf:
            return ""
        para = " ".join(paragraph_buf).strip()
        paragraph_buf = []
        return para

    with path.open("r", encoding=encoding, errors="replace") as f:
        for raw in f:
            line = raw.replace("\r\n", "\n").replace("\r", "\n")
            stripped = line.strip()
            if CHAPTER_RE.match(stripped):
                para = flush_paragraph()
                if para:
                    if not current_chunk:
                        current_chunk = para
                    elif len(f"{current_chunk}\n\n{para}") <= chunk_size:
                        current_chunk = f"{current_chunk}\n\n{para}"
                    else:
                        yield chapter_no, chapter_title, current_chunk.strip()
                        overlap_seed = current_chunk[-overlap:] if overlap > 0 else ""
                        current_chunk = (f"{overlap_seed}\n\n{para}" if overlap_seed else para).strip()
                if current_chunk.strip():
                    yield chapter_no, chapter_title, current_chunk.strip()
                    current_chunk = ""
                    overlap_seed = ""
                chapter_no += 1
                chapter_title = stripped[:120]
                continue
            if not stripped:
                para = flush_paragraph()
                if not para:
                    continue
                if not current_chunk and overlap_seed:
                    current_chunk = overlap_seed
                if not current_chunk:
                    if len(para) <= chunk_size:
                        current_chunk = para
                    else:
                        for piece in hard_split(para, chunk_size, overlap):
                            yield chapter_no, chapter_title, piece
                    continue
                candidate = f"{current_chunk}\n\n{para}".strip()
                if len(candidate) <= chunk_size:
                    current_chunk = candidate
                else:
                    yield chapter_no, chapter_title, current_chunk.strip()
                    overlap_seed = current_chunk[-overlap:] if overlap > 0 else ""
                    current_chunk = (f"{overlap_seed}\n\n{para}" if overlap_seed else para).strip()
                    if len(current_chunk) > chunk_size:
                        for piece in hard_split(current_chunk, chunk_size, overlap):
                            yield chapter_no, chapter_title, piece
                        current_chunk = ""
                        overlap_seed = ""
                continue
            paragraph_buf.append(stripped)

    para = flush_paragraph()
    if para:
        if not current_chunk:
            current_chunk = para
        elif len(f"{current_chunk}\n\n{para}") <= chunk_size:
            current_chunk = f"{current_chunk}\n\n{para}"
        else:
            yield chapter_no, chapter_title, current_chunk.strip()
            overlap_seed = current_chunk[-overlap:] if overlap > 0 else ""
            current_chunk = (f"{overlap_seed}\n\n{para}" if overlap_seed else para).strip()
    if current_chunk.strip():
        yield chapter_no, chapter_title, current_chunk.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Pre-chunk large TXT for splitbook ingest.")
    parser.add_argument("--input", required=True, help="Path to TXT/MD file")
    parser.add_argument("--output", required=True, help="Output JSONL path")
    parser.add_argument("--chunk-size", type=int, default=1200)
    parser.add_argument("--overlap", type=int, default=180)
    parser.add_argument("--encoding", default="")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.exists():
        raise SystemExit(f"INPUT_NOT_FOUND: {input_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    chunk_size = max(300, min(int(args.chunk_size), 5000))
    overlap = max(0, min(int(args.overlap), chunk_size - 60))
    encoding = detect_encoding(input_path, preferred=args.encoding or None)

    total = 0
    total_chars = 0
    with output_path.open("w", encoding="utf-8") as fw:
        for idx, (chapter_no, chapter_title, text_value) in enumerate(iter_chunks(input_path, encoding, chunk_size, overlap), start=1):
            row = {
                "chunk_no": idx,
                "chapter_no": chapter_no or None,
                "chapter_title": chapter_title,
                "text": text_value,
                "char_len": len(text_value),
                "token_est": max(1, len(text_value) // 2),
            }
            fw.write(json.dumps(row, ensure_ascii=False) + "\n")
            total += 1
            total_chars += len(text_value)

    summary = {
        "ok": True,
        "input": str(input_path),
        "output": str(output_path),
        "encoding": encoding,
        "chunk_size": chunk_size,
        "overlap": overlap,
        "chunks_total": total,
        "chars_total": total_chars,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
