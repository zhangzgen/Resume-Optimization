# Resume Optimizer Agent

一个可运行的简历优化 Agent Web 应用。用户输入简历、目标岗位 JD 和补充关注点后，系统会调用 DeepSeek 大模型生成一份流式的 Markdown 诊断报告，并在同一轮任务中输出可下载的优化后简历。

项目目标是满足以下交付要求：

- 支持 Docker 构建和启动
- 仓库根目录包含 `Dockerfile`
- 提供 `docker-compose.yml`
- `README.md` 可独立指导面试官完成启动和基本验收
- LLM API Key 只通过环境变量配置，不在代码中硬编码

## 1. 功能概览

- 支持两种简历输入方式
  - 粘贴简历文本
  - 上传简历文件：`txt`、`md`、`pdf`
- 支持输入目标职位 JD
- 支持填写补充信息
  - 例如：优先强调 ToB 项目、AI 应用交付、量化结果、面试侧重点
- 左侧流式输出诊断报告
  - Markdown 格式
  - 含综合匹配度评分、匹配亮点、主要缺口、具体优化建议、面试策略提示
- 右侧提供优化后简历下载
  - 当前界面默认提供 `Markdown` 下载
  - 后端保留 `TXT` 导出接口
- 提供健康检查接口：`/healthz`

## 2. 技术栈

- Python 3.11
- FastAPI
- Jinja2
- Uvicorn
- DeepSeek API
- Docker / Docker Compose

## 3. 项目结构

```text
.
├── app
│   ├── agent.py              # Agent 提示词与调用编排
│   ├── config.py             # 环境变量配置
│   ├── exporters.py          # Markdown/TXT 导出
│   ├── file_handlers.py      # TXT/MD/PDF 简历解析
│   ├── llm.py                # DeepSeek API 调用
│   ├── main.py               # FastAPI 路由与流式接口
│   ├── models.py             # 数据模型
│   ├── storage.py            # 内存会话存储
│   ├── static
│   │   ├── app.js            # 前端交互与 SSE 消费
│   │   └── styles.css        # 页面样式
│   └── templates
│       └── index.html        # 页面模板
├── tests
│   ├── test_app_routes.py
│   └── test_exporters.py
├── .dockerignore
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── requirements.txt
└── README.md
```

## 4. 环境要求

### 本地运行

- Python 3.11 或更高版本

### Docker 运行

- Docker
- Docker Compose Plugin

## 5. 环境变量配置

项目通过环境变量读取 DeepSeek 配置。请不要把真实 API Key 写入代码、模板、脚本或提交到 GitHub。

先复制示例文件：

```bash
cp .env.example .env
```

然后编辑 `.env`：

```dotenv
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
LLM_TIMEOUT=60
APP_HOST=0.0.0.0
APP_PORT=8000
```

### 环境变量说明

| 变量名 | 是否必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `DEEPSEEK_API_KEY` | 是 | 无 | DeepSeek API Key |
| `DEEPSEEK_BASE_URL` | 否 | `https://api.deepseek.com` | DeepSeek API Base URL |
| `DEEPSEEK_MODEL` | 否 | `deepseek-chat` | 调用模型名 |
| `LLM_TIMEOUT` | 否 | `60` | 接口超时时间，单位秒 |
| `APP_HOST` | 否 | `0.0.0.0` | Web 服务监听地址 |
| `APP_PORT` | 否 | `8000` | Web 服务监听端口 |

### 安全说明

- API Key 只通过环境变量读取，代码中不包含硬编码密钥
- `.env` 已加入 `.gitignore`
- `.env` 已加入 `.dockerignore`
- 不要把带真实 Key 的 `.env` 上传到 GitHub

## 6. 本地开发启动

### 方式一：使用 `venv + pip`

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 方式二：直接通过环境变量启动

```bash
export DEEPSEEK_API_KEY=your_deepseek_api_key
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 7. 使用 Docker 构建与启动

### 方式一：使用 Docker

#### 1. 构建镜像

```bash
docker build -t resume-optimizer-agent:latest .
```

#### 2. 启动容器

```bash
docker run --rm \
  -p 8000:8000 \
  --env-file .env \
  resume-optimizer-agent:latest
```

如果你想修改容器内部端口，也可以覆盖环境变量：

```bash
docker run --rm \
  -p 9000:9000 \
  --env-file .env \
  -e APP_PORT=9000 \
  resume-optimizer-agent:latest
```

### 方式二：使用 Docker Compose

#### 1. 构建并启动

```bash
docker compose up --build
```

#### 2. 后台运行

```bash
docker compose up --build -d
```

#### 3. 停止服务

```bash
docker compose down
```

## 8. 访问地址

默认启动后访问：

- 应用首页：[http://localhost:8000](http://localhost:8000)
- 健康检查：[http://localhost:8000/healthz](http://localhost:8000/healthz)

如果你自定义了 `APP_PORT`，请把 URL 中的端口一起替换。

## 9. 使用说明

### 页面操作流程

1. 打开首页
2. 通过下方按钮录入输入信息
   - `上传简历`：上传 `txt`、`md` 或 `pdf`
   - `粘贴简历`：直接粘贴简历文本
   - `JD 信息`：粘贴目标岗位职责与要求
3. 在长输入框中填写 `补充信息`
   - 例如“优先突出 AI 项目交付结果和业务指标”
4. 点击 `开始优化`
5. 左侧查看流式生成的 Markdown 诊断报告
6. 任务完成后，在右侧结果栏点击 `下载 Markdown`

### 当前交互说明

- 当前实现采用单次执行流程
  - 一次点击会连续完成“诊断报告生成”和“优化后简历生成”
- 左侧不展示优化后简历正文
  - 生成完成后通过右侧结果栏下载

## 10. 面试官验收指引

面试官可以只按照本节完成基本验收。

### Step 1：准备环境变量

```bash
cp .env.example .env
```

将 `DEEPSEEK_API_KEY` 替换为真实值。

### Step 2：启动服务

推荐直接使用 Docker Compose：

```bash
docker compose up --build
```

### Step 3：检查服务是否存活

浏览器访问：

[http://localhost:8000/healthz](http://localhost:8000/healthz)

如果返回 `ok`，说明服务启动正常。

### Step 4：打开应用

浏览器访问：

[http://localhost:8000](http://localhost:8000)

### Step 5：完成一次基础验收

可以使用任意简历与 JD，也可以用下面这组最小示例。

#### 示例简历

```text
3 年 Python 后端开发经验，参与 AI 应用和数据平台建设。
负责 FastAPI 服务开发、模型接口接入、日志监控与线上问题排查。
参与跨团队协作，推动需求上线和版本交付。
```

#### 示例 JD

```text
招聘 AI 应用后端工程师。
要求熟悉 Python、FastAPI、LLM 应用集成、接口设计与跨团队协作。
有 AI 产品交付经验者优先。
```

#### 预期结果

- 左侧可以看到流式输出的诊断报告
- 诊断报告包含匹配评分、亮点、缺口、优化建议
- 右侧结果栏在完成后出现可点击的 `下载 Markdown` 按钮
- 下载文件中包含：
  - 原始简历
  - 目标 JD
  - 匹配分析报告
  - 优化后的简历

## 11. API 与页面说明

### 页面路由

- `GET /`
  - 首页
- `GET /healthz`
  - 健康检查
- `GET /export/{session_id}/md`
  - 导出 Markdown
- `GET /export/{session_id}/txt`
  - 导出 TXT

### 流式接口

- `POST /api/optimize-stream`

请求字段：

- `resume_text`
- `resume_file`
- `job_description`
- `focus_notes`

流式事件类型：

- `session`
- `status`
- `stage_start`
- `stage_delta`
- `stage_done`
- `export_ready`
- `error`

## 12. 测试

运行单元测试：

```bash
python3 -m unittest discover -s tests
```

## 13. 常见问题

### 1. 页面提示没有配置 `DEEPSEEK_API_KEY`

说明应用没有读取到环境变量。请检查：

- `.env` 文件是否存在
- `DEEPSEEK_API_KEY` 是否已填写真实值
- Docker 启动时是否带了 `--env-file .env`

### 2. PDF 上传后没有解析出内容

当前实现会提取 PDF 中可识别的文本内容。如果 PDF 是扫描件或图片型 PDF，可能无法正确解析，建议直接粘贴简历文本。

### 3. Docker 构建慢

首次构建需要拉取 Python 基础镜像并安装依赖。后续构建通常会更快。

## 14. 交付检查清单

- [x] 仓库根目录包含 `Dockerfile`
- [x] 仓库根目录包含 `docker-compose.yml`
- [x] `README.md` 说明了环境变量配置
- [x] `README.md` 说明了如何构建镜像
- [x] `README.md` 说明了如何启动服务
- [x] `README.md` 说明了如何访问和使用应用
- [x] API Key 通过环境变量读取
- [x] `.env` 未纳入 Git 提交
