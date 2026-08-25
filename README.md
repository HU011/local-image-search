# Local Image Search

Local image similarity search service built with FastAPI, Qdrant, and a SigLIP2 vision model.

The project is designed for fully local image embedding, vector indexing, and nearest-neighbor search. It can run on CPU, but the intended high-throughput setup uses an NVIDIA GPU. The local development environment for this project includes an RTX 5090 GPU and has been used with an index of 660,434 images.

## Features

- Image-to-image similarity search from a local file or API upload.
- GPU-accelerated embedding with `google/siglip2-so400m-patch14-384`.
- Qdrant vector database for approximate nearest-neighbor search.
- FastAPI service with health, stats, ingest, and search endpoints.
- Optional Redis queue configuration for asynchronous workloads.
- Local SQLite error store for failed or skipped image records.
- Windows startup scripts for local service operation.

## Architecture

```text
image file / API client
        |
        v
FastAPI service
        |
        v
SigLIP2 embedding model
        |
        v
Qdrant vector collection
        |
        v
top-k similar image results
```

All image processing, model inference, and vector search run locally. The service does not require sending image data to a remote API.

## Repository Layout

```text
app/
  api/                 FastAPI routes
  core/                environment and runtime settings
  services/            embedding, vector database, queue, and error-store logic
config/                local Qdrant configuration
scripts/               helper scripts for Qdrant startup and shutdown
models/                optional local model cache, not committed to Git
examples/              minimal API usage examples
requirements.txt       Python package dependencies
.env.example           configuration template
```

Runtime data is intentionally excluded from Git:

- raw image collections
- Qdrant storage and snapshots
- logs
- local virtual environments
- embedded Python runtimes
- temporary caches

## Model

The default model is `google/siglip2-so400m-patch14-384`.

Model page:

- https://huggingface.co/google/siglip2-so400m-patch14-384

The repository does not commit local model weights. By default, Transformers downloads the model from Hugging Face and caches it locally:

```env
MODEL_NAME=google/siglip2-so400m-patch14-384
MODEL_LOCAL_FILES_ONLY=false
```

If the model has already been downloaded to a local directory, point the service at that path:

```env
MODEL_NAME=models/google_siglip2-so400m-patch14-384
MODEL_LOCAL_FILES_ONLY=true
```

Large model files such as `*.safetensors` should not be committed with normal Git. If a project intentionally stores them in GitHub, configure Git LFS first and check the target account's LFS file-size and billing limits.

## Requirements

- Python 3.10 or newer.
- Qdrant local server.
- NVIDIA driver and CUDA-capable PyTorch build for GPU inference.
- Sufficient disk space for vector storage and model files.

The service automatically uses CUDA when `DEVICE=cuda` and PyTorch can access the GPU. If CUDA is unavailable, set `DEVICE=cpu`.

## Quick Start

1. Create a local configuration file:

```powershell
copy .env.example .env
```

2. Install dependencies:

```powershell
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
```

3. Start the local service:

```powershell
start.bat
```

4. Open the API documentation:

```text
http://127.0.0.1:4568/docs
```

## Configuration

The service reads settings from environment variables or `.env`.

| Variable | Default | Description |
| --- | --- | --- |
| `INSTANCE_NAME` | `local-image-search` | Human-readable service instance name. |
| `QDRANT_URL` | `http://127.0.0.1:6335` | Qdrant HTTP endpoint. |
| `QDRANT_GRPC_PORT` | `6336` | Qdrant gRPC port. |
| `QDRANT_PREFER_GRPC` | `true` | Prefer gRPC for vector operations. |
| `QDRANT_COLLECTION` | `local_image_search_images` | Vector collection name. |
| `REDIS_URL` | empty | Optional Redis connection URL. |
| `REDIS_QUEUE_KEY` | `image_search:local:task_queue` | Optional queue key. |
| `MODEL_NAME` | `google/siglip2-so400m-patch14-384` | Hugging Face model id or local model path. |
| `MODEL_LOCAL_FILES_ONLY` | `false` | Load only local model files when set to true. |
| `DEVICE` | `cuda` | Inference device, usually `cuda` or `cpu`. |
| `BATCH_SIZE` | `64` | Embedding batch size. |
| `HOST` | `127.0.0.1` | API bind host. |
| `PORT` | `4568` | API port. |

## API Examples

Health check:

```powershell
curl http://127.0.0.1:4568/health
```

Service stats:

```powershell
curl http://127.0.0.1:4568/api/stats
```

Search by image:

```powershell
$imageBase64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\images\query.jpg"))
$body = @{ base64 = $imageBase64; top_k = 20 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:4568/api/search" -ContentType "application/json" -Body $body
```

Queue one image for indexing:

```powershell
$imageBase64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\images\image-000001.jpg"))
$body = @{
  id = "image-000001"
  base64 = $imageBase64
  url = "C:\images\image-000001.jpg"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:4568/api/images/ingest" -ContentType "application/json" -Body $body
```

The same calls are available as small Python examples:

```powershell
python examples\ingest_image.py C:\images\image-000001.jpg --id image-000001
python examples\search_image.py C:\images\query.jpg --top-k 20
```

## Local Data Lifecycle

1. Images are read from local paths or local API uploads.
2. The embedding service converts images into normalized vectors.
3. Qdrant stores vectors and payload metadata.
4. Search requests embed the query image and return the nearest stored vectors.
5. Failed records are written to the local error store for inspection and retry.

For a large local index, keep Qdrant storage on a fast SSD and use GPU inference for embedding throughput.

## Operations

Start foreground service:

```powershell
start.bat
```

Start background service:

```powershell
start_service_background.bat
```

Stop Qdrant helper process:

```powershell
stop.bat
```

Runtime logs are written under `logs/`.

## Troubleshooting

CUDA is not being used:

- Confirm that PyTorch sees the GPU with `python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"`.
- Confirm `DEVICE=cuda` in `.env`.
- Install a PyTorch build compatible with the installed NVIDIA driver.

Qdrant collection is empty:

- Confirm `QDRANT_COLLECTION` matches the intended local collection.
- Confirm Qdrant is using the expected storage directory.
- Check `logs/qdrant.log` and the API `/stats` endpoint.

Model cannot load:

- If using local weights, confirm `MODEL_NAME` points to the local model directory.
- If downloading from Hugging Face, set `MODEL_LOCAL_FILES_ONLY=false`.
- Check disk space and read permissions for the model directory.

Search returns no results:

- Confirm images have been indexed.
- Confirm query images are valid JPG, PNG, WEBP, BMP, or TIFF files.
- Confirm Qdrant is reachable at `QDRANT_URL`.

## Public Repository Notes

Before publishing:

- Review staged files with `git status --short`.
- Keep runtime data out of Git.
- Use Git LFS for large model files.
- Keep dataset-specific names, private logs, credentials, and local machine paths out of committed files.
