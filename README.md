# 吃了没后端

基于 `FastAPI + SQLAlchemy + MySQL` 的校园美食记录后端，当前已经切换到新的数据模型：

- `users`：用户信息
- `food`：食物基础信息
- `food_records`：用户对食物的一次打卡/评价记录
- `user_food_stats`：同一用户对同一食物的累计点赞/点踩统计
- `comments`：挂在具体 `food_record` 上的评论

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
如果要使用微信登录，还需配置：

- `WECHAT_APP_ID`
- `WECHAT_APP_SECRET`
- `WECHAT_CODE2SESSION_URL`（可选，默认即微信官方 `code2Session` 地址）

4. 启动服务

```bash
uvicorn app.main:app --reload
```

启动后访问：

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/health`

## 当前接口结构

### 认证

正式可用的小程序登录接口：

- `POST /api/v1/auth/wechat-login`
  - 前端上传微信登录 `code`
  - 后端调用微信 `code2Session`
  - 后端根据 `openid/unionid` 查找或创建用户
  - 后端返回业务 JWT 和用户信息

仍保留但仅用于开发期联调的占位接口：

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/reset-password`

### 用户

- `GET /api/v1/users/me`
- `PUT /api/v1/users/me`
- `PUT /api/v1/users/me/privacy`

### 食物与记录

- `POST /api/v1/foods`
  - 新建一条用户打卡记录；如果食物不存在会自动创建 `food`
- `GET /api/v1/foods`
  - 查询记录列表，支持按食物名、位置、评价倾向、时间范围筛选
- `GET /api/v1/foods/records/{record_id}`
- `PUT /api/v1/foods/records/{record_id}`
- `DELETE /api/v1/foods/records/{record_id}`
- `POST /api/v1/foods/records/{record_id}/reuse`

### 食物互动统计

- `POST /api/v1/foods/{food_id}/reactions`
  - 累计当前用户对该食物的 like/dislike 次数，写入 `user_food_stats`
- `GET /api/v1/foods/rankings`
  - 榜单按 `food` 聚合，不再按单条 `record` 聚合

### 推荐

- `GET /api/v1/foods/recommendations/daily`
- `GET /api/v1/foods/recommendations/personalized`

### 评论

- `POST /api/v1/foods/records/{record_id}/comments`
- `GET /api/v1/foods/records/{record_id}/comments`

### 报告

- `GET /api/v1/reports/annual/{year}`

## 重要说明

- `food_id` 表示食物本体，适用于互动统计、榜单、聚合分析。
- `record_id` 表示某个用户对某个食物的一次具体记录，适用于修改、删除、评论、复用。
- `POST /api/v1/foods` 的请求体里包含 `food` 对象和记录字段，后端会自动做“食物存在则复用，不存在则创建”。
- 年度报告当前基于 `food_records.uploaded_at` 统计。
- 图片上传这一版仍先使用 `image_url` 字段承接，方便前端联调；后续可以换成对象存储。
- `users` 表里已经预留了 `wechat_openid` 和 `wechat_unionid` 字段，认证体系应优先围绕这两个字段设计。

## 接口文档

更详细的字段说明和示例请求见：
[docs/api_reference.md](/e:/Projects/chilemei_backend/docs/api_reference.md)
