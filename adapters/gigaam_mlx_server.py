"""HTTP-адаптер gigaam-mlx для DAVINCI_RESOLVE_MCP_TRANSCRIPTION_HTTP_PROVIDERS.

Запуск:
    python adapters/gigaam_mlx_server.py --port 8001 --model-type rnnt

Конфигурация MCP-сервера (через ~/.zshrc):
    DAVINCI_RESOLVE_MCP_TRANSCRIPTION_HTTP_PROVIDERS='[{
      "id": "gigaam-mlx",
      "label": "GigaAM MLX",
      "base_url": "http://127.0.0.1:8001",
      "request_body": {"model_type": "rnnt"},
      "response_field": "segments"
    }]'

Здоровье:  GET /health -> {"status": "ok"}
Транскрипция: POST /stt -> {"audio": "/path/file.wav"}
              <- {"segments": [{"start": 0.0, "end": 1.5, "text": "..."}]}
"""

import argparse
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

model = None
tokenizer = None
model_type_default = "ctc"
repo_id_default = None


class TranscribeRequest(BaseModel):
    audio: str
    model_type: str | None = None
    model: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model, tokenizer
    from gigaam_mlx import load_model

    print(f"Loading GigaAM MLX model (type={model_type_default})...", flush=True)
    model, tokenizer = load_model(
        model_type=model_type_default, repo_id=repo_id_default
    )
    print("Model loaded.", flush=True)
    yield


app = FastAPI(title="GigaAM MLX", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/stt")
async def transcribe(req: TranscribeRequest):
    from gigaam_mlx import transcribe_file

    effective_type = req.model_type or model_type_default

    if not os.path.isfile(req.audio):
        raise HTTPException(400, f"File not found: {req.audio}")

    if not os.path.getsize(req.audio):
        raise HTTPException(400, f"File is empty: {req.audio}")

    segments = transcribe_file(
        req.audio,
        model=model,
        tokenizer=tokenizer,
        model_type=effective_type,
        verbose=False,
    )
    return {"segments": segments}


def main():
    global model_type_default, repo_id_default

    parser = argparse.ArgumentParser(
        description="GigaAM MLX HTTP adapter for DaVinci Resolve MCP"
    )
    parser.add_argument("--port", type=int, default=8001, help="Listen port")
    parser.add_argument(
        "--model-type",
        choices=["ctc", "rnnt"],
        default="ctc",
        help="Model variant: ctc (fast) or rnnt (higher quality)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="HF repo ID or local model path (auto-selected if omitted)",
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="Listen address (default: 127.0.0.1)"
    )
    args = parser.parse_args()

    model_type_default = args.model_type
    repo_id_default = args.model

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
