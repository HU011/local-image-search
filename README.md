# 本地以图搜图服务

这是一个基于 FastAPI、Qdrant 和 SigLIP2 图像模型构建的本地图片相似度检索服务。

项目用于在本地完成图片向量化、向量索引构建和相似图片检索。服务可以在 CPU 上运行，但高吞吐场景建议使用 NVIDIA GPU。本地开发环境包含 RTX 5090 显卡，并已用于 660,434 张图片规模的向量索引。

## 功能

- Web 可视化页面上传图片并搜索相似结果。
- 支持本地图片批量导入索引。
- 支持外部图片 URL 导入索引，由后端下载，避免浏览器跨域限制。
- 使用 `google/siglip2-so400m-patch14-384` 生成图片向量。
- 使用 Qdrant 存储和检索向量。
- 提供本地 HTTP 路由，包含健康检查、统计、入库、检索和错误记录。
- 支持内存队列，也可以通过 Redis 配置持久化队列。
- 使用本地 SQLite 保存失败记录，便于排查和重试。
- 提供 Windows 本地启动脚本。

## Web 页面

启动服务后，可以直接打开 Web 工作台：

```text
http://127.0.0.1:4568/
```

页面功能：

- 上传一张查询图片进行相似度搜索。
- 设置返回数量和相似度阈值。
- 查看相似结果、相似度、图片 ID 和图片来源。
- 选择多张本地图片导入索引。
- 粘贴多行外部图片 URL 导入索引。
- 查看当前网页操作产生的搜索、导入和错误日志。
- 查看索引数量、队列数量和失败数量。

如果需要在局域网内访问，请在 `.env` 中把监听地址改为：

```env
HOST=0.0.0.0
PORT=4568
```

然后局域网内其他设备访问：

```text
http://服务主机IP:4568/
```

## 架构

```text
Web 页面 / 本地调用
        |
        v
FastAPI 本地服务
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

图片处理、模型推理和向量检索都在本地完成。服务本身不依赖远程图片识别 API。

## 目录结构

```text
app/
  api/                 本地 HTTP 路由和数据结构
  core/                配置和队列逻辑
  services/            模型、向量库、错误记录和后台任务
  utils/               图片编码解码工具
web/                   可视化以图搜图页面
config/                Qdrant 本地配置
scripts/               Qdrant 启动和停止脚本
examples/              本地服务调用示例
requirements.txt       Python 依赖
.env.example           配置模板
```

## 仓库没有上传的内容

本仓库只保留公开代码、配置模板、Web 页面和调用示例，不上传运行时大文件和业务数据。

### 1. 模型权重没有上传

模型权重指的是模型参数文件，例如本地开发环境中的：

```text
models/google_siglip2-so400m-patch14-384/model.safetensors
```

该文件体积约 4GB 以上。普通 GitHub 仓库不适合直接提交这类大文件，GitHub 对普通 Git 文件和 Git LFS 文件都有大小、存储和流量限制。

因此本项目默认通过 Hugging Face 下载模型：

```env
MODEL_NAME=google/siglip2-so400m-patch14-384
MODEL_LOCAL_FILES_ONLY=false
```

模型页面：

```text
https://huggingface.co/google/siglip2-so400m-patch14-384
```

如果已经提前下载了模型，也可以改为本地路径：

```env
MODEL_NAME=models/google_siglip2-so400m-patch14-384
MODEL_LOCAL_FILES_ONLY=true
```

### 2. 示例图片和索引数据没有上传

示例图片、采购图片、商品图片、价格、供应商、库存等内容通常属于具体业务数据，不适合放在公开仓库。

另外，Qdrant 的向量索引和快照文件也会随着图片数量快速变大。对于几十万张图片规模，索引文件可能达到数 GB。公开仓库只提供导入和检索代码，索引数据应由使用者在本地根据自己的图片重新生成。

被排除的典型目录：

```text
data/
models/
logs/
venv/
tools/qdrant/
```

### 3. Qdrant 运行程序没有上传

`tools/qdrant/` 属于本地运行依赖，未提交到仓库。使用时可以自行安装 Qdrant，或把 Qdrant 可执行文件放到本地对应目录。

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

4. 打开 Web 页面：

```text
http://127.0.0.1:4568/
```

5. 打开本地 API 文档：

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
| `HOST` | `127.0.0.1` | API 监听地址。局域网访问可设为 `0.0.0.0`。 |
| `PORT` | `4568` | API 端口。 |

## 本地服务调用示例

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

1. 服务读取本地图片路径、Web 上传图片或外部图片 URL。
2. SigLIP2 模型将图片转换为归一化向量。
3. Qdrant 保存图片向量和对应元数据。
4. 检索时，查询图片会先转换为向量，再从 Qdrant 返回最相似的结果。
5. 处理失败的记录会写入本地错误库，便于后续查看和重试。

大规模索引建议把 Qdrant 数据放在 SSD 上，并使用 GPU 执行向量生成。

## 应用案例：多供应商采购平台的同 EAN 低价匹配

在多供应商采购平台中，同一个 EAN/ENA 码可能对应多个供应商、不同报价、库存数量、包装规格和仓库。传统表格匹配主要依赖条码或文本字段，遇到图片相似但标题不一致、字段缺失、供应商命名不统一等情况时，容易漏掉可比价商品。

本项目可以作为采购比价流程中的本地图片检索模块：

1. 将各供应商商品图片导入本地向量索引。
2. 使用待采购商品图片进行相似度搜索。
3. 返回视觉上最相似的一组候选商品。
4. 业务系统再结合 EAN/ENA 码、价格、库存、包装数、仓库和供应商优先级进行二次筛选。
5. 最终辅助定位同码或相似商品中的低价可采购项。

该方案适合在局域网内部署。图片向量化、索引构建和检索都在本地完成，避免把采购图片和商品数据发送到外部识别服务。

## 商品参数映射的接入方法

当前公开版为了保持通用，只返回以下搜索结果字段：

```json
{
  "id": "image-000001",
  "url": "https://example.com/image.jpg",
  "score": 0.9821,
  "rank": 1
}
```

如果要接入多供应商采购平台，需要在图片入库时把商品参数作为 `metadata` 写入向量库，并在搜索结果中返回。推荐的数据结构如下：

```json
{
  "id": "image-000001",
  "base64": "data:image/jpeg;base64,...",
  "url": "https://example.com/image.jpg",
  "metadata": {
    "ean": "8414926111177",
    "title": "商品名称",
    "supplier": "供应商 A",
    "price": 4.32,
    "currency": "EUR",
    "stock": 282,
    "package_count": 1,
    "box_count": 1,
    "warehouse": "仓库 A",
    "sku": "SKU-001"
  }
}
```

代码接入位置：

1. 在 `app/api/schemas.py` 的 `ImageIngestRequest` 中增加 `metadata` 字段。
2. 在 `app/core/queue.py` 的 `IngestTask` 中增加 `metadata` 字段，保证队列能传递商品参数。
3. 在 `app/services/vector_db.py` 的 `upsert_vectors` 中把 `metadata` 写入 Qdrant payload。
4. 在 `app/services/vector_db.py` 的 `search` 和 `search_batch` 中把 payload 里的商品参数返回给前端。
5. 在 `app/api/schemas.py` 的 `SearchResult` 中增加 `metadata` 字段。
6. 在 `web/app.js` 和 `web/index.html` 中展示 EAN/ENA、价格、供应商、库存、包装数、仓库等字段。

推荐的 Qdrant payload 结构：

```json
{
  "id": "image-000001",
  "url": "https://example.com/image.jpg",
  "instance": "local-image-search",
  "metadata": {
    "ean": "8414926111177",
    "title": "商品名称",
    "supplier": "供应商 A",
    "price": 4.32,
    "currency": "EUR",
    "stock": 282,
    "package_count": 1,
    "box_count": 1,
    "warehouse": "仓库 A",
    "sku": "SKU-001"
  }
}
```

有了商品数据后，接入流程如下：

1. 从现有采购平台导出商品表，至少包含图片地址、图片 ID、EAN/ENA、价格、供应商和库存。
2. 使用图片 ID 作为稳定主键，确保同一商品重复导入时覆盖同一个向量点。
3. 把图片内容和商品参数一起提交到入库路由。
4. 搜图返回相似候选后，业务系统按 EAN/ENA 相同、价格最低、库存可用、供应商优先级等规则筛选。
5. 前端页面展示相似图片和对应商品参数，供人工复核或后续自动下单流程使用。

如果商品数据存放在独立数据库中，也可以只把 `id`、`url` 写入 Qdrant，搜索返回 `id` 后再由业务系统根据 `id` 查询商品详情。这种方式能减少向量库 payload 体积，也更方便复用现有商品数据库。

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
