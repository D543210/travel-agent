# HelloAgents智能旅行助手 🌍✈️

基于HelloAgents框架构建的智能旅行规划助手,集成高德地图MCP服务,提供个性化的旅行计划生成。

## ✨ 功能特点

- 🤖 **AI驱动的旅行规划**: 基于HelloAgents框架的SimpleAgent,智能生成详细的多日旅程
- 🗺️ **高德地图集成**: 通过MCP协议接入高德地图服务,支持景点搜索、路线规划、天气查询
- 🧠 **受控工具选择**: 决策Agent可选择补搜景点、预查路线或结束；后端校验参数并限制额外工具调用次数
- ⏱️ **行程可行性校验**: 用真实路线核算每日耗时；超时后允许一次受限修正，再次校验地点与时间
- 🎨 **现代化前端**: Vue3 + TypeScript + Vite,响应式设计,流畅的用户体验
- 📱 **完整功能**: 包含住宿、交通、餐饮和景点游览时间推荐

## 🏗️ 技术栈

### 后端
- **框架**: HelloAgents (基于SimpleAgent)
- **API**: FastAPI
- **MCP工具**: amap-mcp-server (高德地图)
- **LLM**: 支持多种LLM提供商(OpenAI, DeepSeek等)

### 前端
- **框架**: Vue 3 + TypeScript
- **构建工具**: Vite
- **UI组件库**: Ant Design Vue
- **地图服务**: 高德地图 JavaScript API
- **HTTP客户端**: Axios

## 📁 项目结构

```
helloagents-trip-planner/
├── backend/                    # 后端服务
│   ├── app/
│   │   ├── agents/            # Agent实现
│   │   │   ├── trip_planner_agent.py
│   │   │   └── tool_decision.py
│   │   ├── api/               # FastAPI路由
│   │   │   ├── main.py
│   │   │   └── routes/
│   │   │       ├── trip.py
│   │   │       └── map.py
│   │   ├── services/          # 服务层
│   │   │   ├── amap_service.py
│   │   │   └── llm_service.py
│   │   ├── models/            # 数据模型
│   │   │   └── schemas.py
│   │   └── config.py          # 配置管理
│   ├── requirements.txt
│   ├── .env.example
│   ├── tests/                 # 后端自动化测试
│   └── .gitignore
├── frontend/                   # 前端应用
│   ├── src/
│   │   ├── components/        # Vue组件
│   │   ├── services/          # API服务
│   │   ├── types/             # TypeScript类型
│   │   └── views/             # 页面视图
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

## 🚀 快速开始

### 前提条件

- Python 3.10+
- Node.js 16+
- 高德地图API密钥 (Web服务API和Web端(JS API))
- LLM API密钥 (OpenAI/DeepSeek等)

### 后端安装

1. 进入后端目录
```bash
cd backend
```

2. 创建虚拟环境
```bash
python -m venv venv
```

Windows PowerShell激活虚拟环境：
```powershell
.\venv\Scripts\Activate.ps1
```

Linux/macOS激活虚拟环境：
```bash
source venv/bin/activate
```

3. 安装依赖
```bash
pip install -r requirements.txt
```

启动后端前保持虚拟环境已激活，并运行 `uvx --version` 确认高德MCP服务所需的 `uvx` 在当前 `PATH` 中。

4. 配置环境变量
```bash
cp .env.example .env
# 编辑.env文件,填入你的API密钥
```

5. 启动后端服务
```bash
uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端安装

1. 进入前端目录
```bash
cd frontend
```

2. 安装依赖
```bash
npm install
```

3. 配置环境变量
```bash
# 创建.env文件, 填入高德地图Web API Key 和 Web端JS API Key
cp .env.example .env
```

4. 启动开发服务器
```bash
npm run dev
```

5. 打开浏览器访问 `http://localhost:5173`

## 📝 使用指南

1. 在首页填写旅行信息:
   - 目的地城市
   - 旅行日期和天数
   - 交通方式偏好
   - 住宿偏好
   - 旅行风格标签

2. 点击"生成旅行计划"按钮

3. 系统将:
   - 由后端先查询高德景点和天气；决策Agent可选择补搜景点或预查路线
   - 由景点、酒店、餐厅和行程规划Agent分别筛选或编排数据
   - 由后端查询真实路线,校验地点ID、日期、餐饮、预算和单日总耗时
   - 行程超时则反馈耗时明细,允许规划Agent修正一次并重新校验
   - 将通过校验的行程返回给前端

4. 查看结果:
   - 每日详细行程
   - 景点信息与地图标记
   - 交通路线规划
   - 天气预报
   - 餐饮推荐

## 🔧 核心实现

### 当前工作流与工具调用边界

`MultiAgentTripPlanner.plan_trip()`在后端编排整体流程。`AmapService`封装高德地图调用,负责获取真实POI、天气和路线。工具决策Agent先阅读候选景点与天气摘要,选择 `search_more`（补搜景点）、`check_route`（预查两处候选景点间路线）或 `finish`。后端校验JSON动作和POI ID,最多执行2次额外工具调用；Agent不直接持有或任意调用MCP工具。补搜结果进入景点候选池,预查路线作为景点筛选参考。

随后,景点、酒店、餐厅和行程规划4个`SimpleAgent`处理各自阶段。后端校验模型输出结构,并用高德返回的POI字段回填地点信息。初始搜索、天气、酒店和餐厅查询仍由固定流程触发；模型只在上述受控动作范围内选择额外调用。POI搜索、天气、步行和驾车路线通过高德MCP工具访问；公共交通路线及其地址解析通过高德HTTP API访问。当前使用的MCP工具包括:

- `maps_text_search`: 搜索POI
- `maps_search_detail`: 获取POI详情
- `maps_weather`: 查询天气
- `maps_direction_walking_by_address`: 步行路线规划
- `maps_direction_driving_by_address`: 驾车路线规划

### 时间校验与修正

每天至少安排2个景点,路线按“酒店 → 景点 → 酒店”查询。路线齐全时,后端计算“景点停留 + 真实路线 + 三餐预留”,与 `DAILY_AVAILABLE_MINUTES` 比较。首次超时会把各项耗时反馈给规划Agent,最多修正一次；首稿使用景点筛选Agent建议的停留时间,修正时每个景点最多缩短原建议的20%,通常不得低于90分钟。修正后的POI、停留时间、路线和预算仍由后端校验；不合格则返回错误,不会自动提高每日上限。若路线数据不完整,响应会标记降级,并提示无法完整校验时间可行性。

当前`POST /api/trip/plan`仍同步生成行程。数据库中的任务表和Redis环境尚未接入这条请求流程,也尚未实现跨任务的用户记忆。

### 后端测试

在 `backend` 目录激活虚拟环境后运行 `python -m pytest -q`。测试覆盖受控工具调用、错误输出、真实POI约束和超时修正；真实模型和地图请求仍需单独验证。

## 📄 API文档

启动后端服务后,访问 `http://localhost:8000/docs` 查看完整的API文档。

主要端点:
- `POST /api/trip/plan` - 生成旅行计划
- `GET /api/map/poi` - 搜索POI
- `GET /api/map/weather` - 查询天气
- `POST /api/map/route` - 规划路线

## 🤝 贡献指南

欢迎提交Pull Request或Issue!

## 📜 开源协议

CC BY-NC-SA 4.0

## 🙏 致谢

- [HelloAgents](https://github.com/datawhalechina/Hello-Agents) - 智能体教程
- [HelloAgents框架](https://github.com/jjyaoao/HelloAgents) - 智能体框架
- [高德地图开放平台](https://lbs.amap.com/) - 地图服务
- [amap-mcp-server](https://github.com/sugarforever/amap-mcp-server) - 高德地图MCP服务器

---

**HelloAgents智能旅行助手** - 让旅行计划变得简单而智能 🌈
