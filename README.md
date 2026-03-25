# 吃了没后端

基于 `FastAPI + SQLAlchemy + MySQL` 实现的校园美食记录与年度报告后端，覆盖项目计划书里的核心后端能力：

- 用户注册、登录、修改密码、个人资料、隐私设置
- 美食记录新增、查询、修改、删除、历史复用
- 赞、踩、想吃互动与评论
- 每日推荐、个性化推荐、日榜、周榜、总榜
- 年度报告统计接口

## 目录结构

```text
app/
  api/          # 路由和依赖
  core/         # 配置和安全
  db/           # 数据库连接
  models/       # SQLAlchemy 模型
  schemas/      # Pydantic 模型
  services/     # 推荐和报告逻辑
  utils/        # 通用工具
  main.py       # 应用入口
sql/
  init_mysql.sql
```

## 快速启动

1. 安装依赖

```bash
pip install -r requirements.txt
```

2. 初始化 MySQL 数据库

```sql
source sql/init_mysql.sql;
```

3. 配置环境变量

将 `.env.example` 复制为 `.env`，再按你的 MySQL 账号修改连接信息。

4. 启动服务

```bash
uvicorn app.main:app --reload
```

启动后访问：

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/health`

## 已实现接口

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/reset-password`
- `GET /api/v1/users/me`
- `PUT /api/v1/users/me`
- `PUT /api/v1/users/me/privacy`
- `POST /api/v1/foods`
- `GET /api/v1/foods`
- `GET /api/v1/foods/{food_id}`
- `PUT /api/v1/foods/{food_id}`
- `DELETE /api/v1/foods/{food_id}`
- `POST /api/v1/foods/{food_id}/reuse`
- `POST /api/v1/foods/{food_id}/reactions`
- `POST /api/v1/foods/{food_id}/comments`
- `GET /api/v1/foods/{food_id}/comments`
- `GET /api/v1/foods/recommendations/daily`
- `GET /api/v1/foods/recommendations/personalized`
- `GET /api/v1/foods/rankings`
- `GET /api/v1/reports/annual/{year}`

## 当前实现说明

- 图片上传这一版先用 `image_url` 字段承接，方便前端先联调；后续可接对象存储。
- 个性化推荐当前是基础标签匹配版，后续可扩展协同过滤和召回排序。
- 年度报告当前返回结构化 JSON，图片版和 PDF 导出适合后续做成独立导出服务。
