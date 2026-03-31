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
- `WECHAT_CODE2SESSION_URL`
- `MEDIA_DIR`
- `FOOD_UPLOAD_DIR`
- `MEDIA_URL_PREFIX`

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

### 图片上传

- `POST /api/v1/foods/upload-image`
  - 小程序通过 `wx.uploadFile` 上传图片
  - 后端先将图片保存到临时目录 `media/temp/`，创建记录时再归档到 `media/food/<food_id>/`
  - 后端返回可以直接展示的 `image_url`

上传成功后，前端保留返回的临时 `image_url` 用于预览；真正创建或修改记录时只传 `image_filename`。如果用户更换图片或取消发布，应调用 `DELETE /api/v1/foods/upload-image?image_filename=...` 删除旧的临时图片。

### 食物与记录

- `POST /api/v1/foods`
  - 新建一条用户打卡记录；支持直接传 `food_id` 绑定已有食物，或传 `food` 让后端按 `name + location` 查找/创建食物
- `GET /api/v1/foods/search`
  - 按食物名称搜索已存在食物，供前端下拉选择，并自动填充地点/价格等信息
- `GET /api/v1/foods`
  - 查询记录列表，支持按食物名、位置、评价倾向、时间范围筛选
- `GET /api/v1/foods/records/{record_id}`
- `PUT /api/v1/foods/records/{record_id}`
- `DELETE /api/v1/foods/records/{record_id}`
- `POST /api/v1/foods/records/{record_id}/reuse`
  - 返回复用草稿数据，供前端预填创建表单，不再直接创建一条重复记录

### 食物互动统计

- `POST /api/v1/foods/{food_id}/reactions`
  - 累计当前用户对该食物的 like/dislike 次数，写入 `user_food_stats`
- `GET /api/v1/foods/rankings`
  - 榜单按 `food` 聚合，不再按单条 `record` 聚合

### 推荐

- `GET /api/v1/foods/recommendations/daily`
  - 首页按 `food` 返回单个推荐卡片，包含 `food_id`、名称、位置、价格、评分、喜欢/劝退统计和随机封面图
- `GET /api/v1/foods/recommendations/personalized`
  - 首页按 `food` 返回个性化推荐列表，而不是按单条 `record` 返回
- `GET /api/v1/foods/{food_id}/detail`
  - 返回食物详情、全部图片、最近描述和聚合评论，供详情页使用

### 评论

- `POST /api/v1/foods/records/{record_id}/comments`
- `GET /api/v1/foods/records/{record_id}/comments`

### 报告

- `GET /api/v1/reports/annual/{year}`

## 图片上传流程

1. 小程序选择相册或拍照后，先调用 `/api/v1/foods/upload-image`
2. 后端先把图片保存到临时目录，返回 `image_filename` 和临时 `image_url`
3. 小程序调用 `POST /api/v1/foods` 或 `PUT /api/v1/foods/records/{record_id}`
4. 创建记录时请求体里只传入 `image_filename`
5. 前端展示时直接使用 `<image src="{{item.image_url}}">`

## 重要说明

- `food_id` 表示食物本体，适用于互动统计、榜单、聚合分析。
- `record_id` 表示某个用户对某个食物的一次具体记录，适用于修改、删除、评论、获取复用草稿。
- `POST /api/v1/foods` 的请求体支持 `food_id` 或 `food` 二选一；传 `food` 时，后端会按 `name + location` 做“食物存在则复用，不存在则创建”。
- `rating_level` 使用 1-5 数字表示评分。
- 年度报告当前基于 `food_records.uploaded_at` 统计。
- `users` 表里已经预留了 `wechat_openid` 和 `wechat_unionid` 字段，认证体系应优先围绕这两个字段设计。

## 接口文档

更详细的字段说明和示例请求见：
[docs/api_reference.md](/e:/Projects/chilemei_backend/docs/api_reference.md)
