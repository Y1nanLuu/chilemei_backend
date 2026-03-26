# 接口说明

基础前缀：`/api/v1`

认证方式：除登录相关接口外，其余接口都需要 `Authorization: Bearer <token>`。

## 1. 微信登录（正式可用）

`POST /auth/wechat-login`

说明：
- 这是当前小程序应该使用的正式登录接口。
- 前端需先调用微信登录能力拿到 `code`。
- 后端会调用微信 `code2Session` 换取 `openid/unionid`。
- 后端会基于 `openid/unionid` 查找或创建用户，然后返回业务 JWT。

请求体示例：

```json
{
  "code": "wx-login-code"
}
```

响应示例：

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "nickname": "WeChatUser8f3a21",
    "avatar_url": null,
    "is_new_user": true
  }
}
```

可能的错误：
- `500`: 没有配置 `WECHAT_APP_ID / WECHAT_APP_SECRET`
- `502`: 后端调微信接口失败
- `400`: 微信返回错误码或没有返回 `openid`

相关环境变量：
- `WECHAT_APP_ID`
- `WECHAT_APP_SECRET`
- `WECHAT_CODE2SESSION_URL`

## 2. 开发期占位认证接口

以下接口仍然保留，但只建议用于本地联调或后端自测：

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/reset-password`

`POST /auth/register` 示例：

```json
{
  "username": "alice",
  "email": "alice@example.com",
  "password": "123456",
  "nickname": "Alice"
}
```

`POST /auth/login` 示例：

```json
{
  "username": "alice",
  "password": "123456"
}
```

## 3. 当前用户信息

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

## 4. 新建食物记录

`POST /foods`

说明：
- `food` 是食物基础信息。
- `sentiment` 和 `rating_level` 是本次记录的用户评价。
- `rating_level` 现在传 `1-5` 的数字，不再使用中文字符串。

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
  "rating_level": 5,
  "review_text": "汤很浓，面也劲道",
  "image_url": "https://example.com/record.jpg"
}
```

## 5. 查询记录列表

`GET /foods`

可选查询参数：
- `food_name`
- `location`
- `sentiment`
- `mine_only`
- `start_time`
- `end_time`

## 6. 查询/修改/删除单条记录

- `GET /foods/records/{record_id}`
- `PUT /foods/records/{record_id}`
- `DELETE /foods/records/{record_id}`
- `POST /foods/records/{record_id}/reuse`

## 7. 食物互动统计

`POST /foods/{food_id}/reactions`

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

## 8. 榜单

`GET /foods/rankings`

可选查询参数：
- `period`: `daily | weekly | all`
- `scope`: `global | mine`

## 9. 推荐

- `GET /foods/recommendations/daily`
- `GET /foods/recommendations/personalized`

## 10. 评论

- `POST /foods/records/{record_id}/comments`
- `GET /foods/records/{record_id}/comments`

## 11. 年度报告

`GET /reports/annual/{year}`

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

## 12. 路由语义说明

- `food_id`：食物实体 ID，用于榜单、互动统计、聚合分析。
- `record_id`：用户某次打卡记录 ID，用于评论、编辑、删除、复用。
- 如果前端页面是在展示“某次分享内容”，优先使用 `record_id`。
- 如果前端页面是在展示“某种食物的总体热度”，优先使用 `food_id`。
