# 本地以图搜图服务

这是一个基于 FastAPI、Qdrant 和 SigLIP2 图像模型构建的本地图片相似度检索服务。

项目用于在本地完成图片向量化、向量索引构建和相似图片检索。服务可以在 CPU 上运行，但高吞吐场景建议使用 NVIDIA GPU。本地开发环境包含 RTX 5090 显卡，并已用于 660,434 张图片规模的向量索引。

## 功能

- 通过图片查询相似图片。
- 使用 `google/siglip2-so400m-patch14-384` 生成图片向量。
- 使用 Qdrant 存储和检索向量。
- 提供 FastAPI 接口，包含健康检查、统计、入库、检索和错误记录接口。
- 支持内存队列，也可以通过 Redis 配置持久化队列。
- 使用本地 SQLite 保存失败记录，便于排查和重试。
- 提供 Windows 本地启动脚本。

## 架构

```text
图片文件 / API 调用
        |
        v
FastAPI 服务
        |
        v
SigLIP2 图片向量模型
        |
        v
Qdrant 向量集合
        |
        v
Top-K 相似图片结果
```

图片处理、模型推理和向量检索都在本地完成，服务本身不依赖远程图片识别 API。

## 目录结构

```text
app/
  api/                 FastAPI 接口和数据结构
  core/                配置和队列逻辑
  services/            模型、向量库、错误记录和后台任务
  utils/               图片编码解码工具
config/                Qdrant 本地配置
scripts/               Qdrant 启动和停止脚本
examples/              API 调用示例
requirements.txt       Python 依赖
.env.example           配置模板
```

以下本地运行文件不会提交到仓库：

- 原始图片数据
- Qdrant 运行数据和快照
- 日志
- Python 虚拟环境
- 便携 Python 运行时
- 本地模型缓存
- 临时文件

## 模型配置

默认模型：

https://huggingface.co/google/siglip2-so400m-patch14-384

本仓库不上传模型权重。默认配置会让 Transformers 从 Hugging Face 下载模型，并缓存在本地：

```env
MODEL_NAME=google/siglip2-so400m-patch14-384
MODEL_LOCAL_FILES_ONLY=false
```

如果你已经提前下载了模型，也可以改成本地路径：

```env
MODEL_NAME=models/google_siglip2-so400m-patch14-384
MODEL_LOCAL_FILES_ONLY=true
```

大模型文件不建议直接用普通 Git 提交。如果确实需要把 `*.safetensors`、`*.bin`、`*.pt`、`*.pth`、`*.onnx` 等文件放到 GitHub，需要先配置 Git LFS，并确认账号的 LFS 单文件大小、存储和流量限制。

## 环境要求

- Python 3.10 或更高版本。
- 本地 Qdrant 服务。
- 如需 GPU 推理，需要 NVIDIA 显卡驱动和支持 CUDA 的 PyTorch。
- 足够的磁盘空间用于向量库、日志和模型缓存。

当 `DEVICE=cuda` 且 PyTorch 能识别显卡时，服务会使用 CUDA。需要强制 CPU 时，可以设置：

```env
DEVICE=cpu
```

## 快速开始

1. 创建本地配置：

```powershell
copy .env.example .env
```

2. 安装依赖：

```powershell
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
```

3. 启动服务：

```powershell
start.bat
```

4. 打开接口文档：

```text
http://127.0.0.1:4568/docs
```

## 配置项

服务会读取环境变量或 `.env` 文件。

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `INSTANCE_NAME` | `local-image-search` | 服务实例名称。 |
| `QDRANT_URL` | `http://127.0.0.1:6335` | Qdrant HTTP 地址。 |
| `QDRANT_GRPC_PORT` | `6336` | Qdrant gRPC 端口。 |
| `QDRANT_PREFER_GRPC` | `true` | 向量操作优先使用 gRPC。 |
| `QDRANT_COLLECTION` | `local_image_search_images` | Qdrant 向量集合名称。 |
| `REDIS_URL` | 空 | 可选 Redis 地址。 |
| `REDIS_QUEUE_KEY` | `image_search:local:task_queue` | Redis 队列键名。 |
| `MODEL_NAME` | `google/siglip2-so400m-patch14-384` | Hugging Face 模型名或本地模型路径。 |
| `MODEL_LOCAL_FILES_ONLY` | `false` | 是否只加载本地模型文件。 |
| `DEVICE` | `cuda` | 推理设备，通常为 `cuda` 或 `cpu`。 |
| `BATCH_SIZE` | `64` | 批量入库的推理批大小。 |
| `HOST` | `127.0.0.1` | API 监听地址。 |
| `PORT` | `4568` | API 端口。 |

## API 示例

健康检查：

```powershell
curl http://127.0.0.1:4568/health
```

查看状态：

```powershell
curl http://127.0.0.1:4568/api/stats
```

用一张图片检索相似结果：

```powershell
$imageBase64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\images\query.jpg"))
$body = @{ base64 = $imageBase64; top_k = 20 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:4568/api/search" -ContentType "application/json" -Body $body
```

提交一张图片进入索引队列：

```powershell
$imageBase64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\images\image-000001.jpg"))
$body = @{
  id = "image-000001"
  base64 = $imageBase64
  url = "C:\images\image-000001.jpg"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:4568/api/images/ingest" -ContentType "application/json" -Body $body
```

也可以使用示例脚本：

```powershell
python examples\ingest_image.py C:\images\image-000001.jpg --id image-000001
python examples\search_image.py C:\images\query.jpg --top-k 20
```

## 数据流程

1. 服务读取本地图片路径或 API 提交的图片内容。
2. SigLIP2 模型将图片转换为归一化向量。
3. Qdrant 保存图片向量和对应元数据。
4. 检索时，查询图片会先转换为向量，再从 Qdrant 返回最相似的结果。
5. 处理失败的记录会写入本地错误库，便于后续查看和重试。

大规模索引建议把 Qdrant 数据放在 SSD 上，并使用 GPU 执行向量生成。

## 常用操作

前台启动：

```powershell
start.bat
```

后台启动：

```powershell
start_service_background.bat
```

停止服务：

```powershell
stop.bat
```

运行日志位于 `logs/` 目录。

## 常见问题

没有使用 GPU：

- 确认 `.env` 中 `DEVICE=cuda`。
- 执行 `python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"` 检查 PyTorch 是否能识别显卡。
- 确认安装的 PyTorch 与本机 NVIDIA 驱动兼容。

Qdrant 集合为空：

- 确认 `QDRANT_COLLECTION` 是当前要使用的集合名。
- 确认 Qdrant 使用的是预期的数据目录。
- 查看 `logs/qdrant-server.stderr.log` 和 `/api/stats`。

模型加载失败：

- 默认配置会从 Hugging Face 下载模型，请确认网络可以访问 Hugging Face。
- 如果使用本地模型目录，确认 `MODEL_NAME` 路径正确。
- 检查磁盘空间和模型目录读取权限。

检索没有结果：

- 确认图片已经完成入库。
- 确认查询图片格式正常，推荐 JPG、PNG、WEBP、BMP 或 TIFF。
- 确认 Qdrant 可以通过 `QDRANT_URL` 访问。
