# 接口说明

基础前缀：`/api/v1`

认证方式：除登录相关接口外，其余接口都需要 `Authorization: Bearer <token>`。

## 1. 认证说明

正式业务方案应使用微信登录，不建议把当前的用户名密码注册登录当成小程序正式协议。

当前状态：
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/reset-password`
- 这三组接口仅作为开发期占位实现，方便本地联调。

正式建议方案：
- 新增 `POST /auth/wechat-login`
- 前端上传微信登录返回的 `code`
- 后端调用微信 `code2Session`
- 根据 `openid` / `unionid` 查找或创建用户
- 生成并返回业务 JWT

建议的微信登录请求体：

```json
{
  "code": "wx-login-code"
}
```

建议的微信登录响应体：

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "nickname": "未命名用户",
    "avatar_url": null
  }
}
```

说明：
- `users.wechat_openid` 和 `users.wechat_unionid` 已在数据库层预留。
- 如果项目准备上线微信小程序，认证模块应优先改造为微信登录。

## 2. 开发期占位注册

`POST /auth/register`

请求体示例：

```json
{
  "username": "alice",
  "email": "alice@example.com",
  "password": "123456",
  "nickname": "Alice"
}
```

响应示例：

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

## 3. 开发期占位登录

`POST /auth/login`

```json
{
  "username": "alice",
  "password": "123456"
}
```

## 4. 当前用户信息

`GET /users/me`

`PUT /users/me`

```json
{
  "nickname": "Alice Chen",
  "bio": "喜欢探店",
  "avatar_url": "https://example.com/avatar.jpg"
}
```

`PUT /users/me/privacy`

```json
{
  "is_private": true
}
```

## 5. 新建食物记录

`POST /foods`

说明：
- `food` 是食物基础信息。
- `sentiment` 和 `rating_level` 是本次记录的用户评价。
- 如果库里已经存在相同 `name + location + price` 的食物，会复用已有 `food`。

请求体示例：

```json
{
  "food": {
    "name": "红烧牛肉面",
    "location": "一食堂二楼",
    "price": 18.50,
    "image_url": "https://example.com/food.jpg"
  },
  "sentiment": "like",
  "rating_level": "顶级",
  "review_text": "汤很浓，面也劲道",
  "image_url": "https://example.com/record.jpg"
}
```

响应核心字段：

```json
{
  "id": 1,
  "user_id": 2,
  "food_id": 10,
  "food": {
    "id": 10,
    "name": "红烧牛肉面",
    "location": "一食堂二楼",
    "price": 18.50,
    "image_url": "https://example.com/food.jpg"
  },
  "sentiment": "like",
  "rating_level": "顶级",
  "review_text": "汤很浓，面也劲道",
  "image_url": "https://example.com/record.jpg",
  "uploaded_at": "2026-03-26T11:00:00"
}
```

## 6. 查询记录列表

`GET /foods`

可选查询参数：
- `food_name`
- `location`
- `sentiment`
- `mine_only`
- `start_time`
- `end_time`

示例：

`GET /foods?food_name=牛肉面&mine_only=true`

## 7. 查询/修改/删除单条记录

`GET /foods/records/{record_id}`

`PUT /foods/records/{record_id}`

可更新字段示例：

```json
{
  "food": {
    "location": "一食堂三楼"
  },
  "sentiment": "dislike",
  "rating_level": "NPC",
  "review_text": "这次有点咸"
}
```

`DELETE /foods/records/{record_id}`

`POST /foods/records/{record_id}/reuse`

说明：基于历史记录复制出一条新的用户记录，新记录会复用原 `food_id`。

## 8. 食物互动统计

`POST /foods/{food_id}/reactions`

说明：
- 这是对食物维度的累计互动，不是对单条记录互动。
- 写入或更新 `user_food_stats`。
- 当前只支持 `like` / `dislike`。

请求体示例：

```json
{
  "reaction_type": "like"
}
```

响应示例：

```json
{
  "user_id": 2,
  "food_id": 10,
  "like_count": 3,
  "dislike_count": 1
}
```

## 9. 榜单

`GET /foods/rankings`

可选查询参数：
- `period`: `daily | weekly | all`
- `scope`: `global | mine`

返回示例：

```json
[
  {
    "food_id": 10,
    "food_name": "红烧牛肉面",
    "location": "一食堂二楼",
    "price": 18.50,
    "like_count": 12,
    "dislike_count": 2,
    "score": 10
  }
]
```

## 10. 推荐

`GET /foods/recommendations/daily`

说明：优先返回最近 24 小时内的最新可见记录。

`GET /foods/recommendations/personalized`

说明：基于当前用户喜欢过的食物位置做简单个性化推荐。

## 11. 评论

`POST /foods/records/{record_id}/comments`

```json
{
  "content": "这个我也吃过，确实不错"
}
```

`GET /foods/records/{record_id}/comments`

## 12. 年度报告

`GET /reports/annual/{year}`

示例：

`GET /reports/annual/2026`

返回字段说明：
- `total_records`: 年内记录总数
- `total_spend`: 年内总消费
- `average_spend`: 平均每次消费
- `total_like_records`: 标记为 like 的记录数
- `total_dislike_records`: 标记为 dislike 的记录数
- `top_foods`: 最常记录的食物 Top 5
- `top_locations`: 最常去的位置 Top 5
- `monthly_spend`: 月度消费统计
- `title_tags`: 自动生成的趣味标签

## 13. 路由语义说明

- `food_id`：食物实体 ID，用于榜单、互动统计、聚合分析。
- `record_id`：用户某次打卡记录 ID，用于评论、编辑、删除、复用。
- 如果前端页面是在展示“某次分享内容”，优先使用 `record_id`。
- 如果前端页面是在展示“某种食物的总体热度”，优先使用 `food_id`。
