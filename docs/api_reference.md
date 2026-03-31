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

## 2. 开发期占位认证接口

以下接口仅用于本地联调或后端自测：

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/reset-password`

## 3. 当前用户信息

- `GET /users/me`
- `PUT /users/me`
- `PUT /users/me/privacy`

## 4. 图片上传（小程序先传图再提交记录）

`POST /foods/upload-image`

说明：
- 请使用 `multipart/form-data`。
- 小程序端通过 `wx.uploadFile` 上传。
- 文件字段名必须是 `file`。
- 后端会将图片保存到本地 `media/food_records/` 目录。
- 后端会返回 `image_url`，前端可直接渲染。

响应示例：

```json
{
  "image_url": "http://127.0.0.1:8000/media/food_records/3d9f0e4a9f1b4d8f8d3f1a2b3c4d5e6f.jpg",
  "stored_path": "media/food_records/3d9f0e4a9f1b4d8f8d3f1a2b3c4d5e6f.jpg",
  "original_filename": "lunch.jpg"
}
```

小程序 `wx.uploadFile` 示例：

```javascript
wx.chooseMedia({
  count: 1,
  mediaType: ['image'],
  sourceType: ['album', 'camera'],
  success: (chooseRes) => {
    const tempFilePath = chooseRes.tempFiles[0].tempFilePath;

    wx.uploadFile({
      url: 'http://127.0.0.1:8000/api/v1/foods/upload-image',
      filePath: tempFilePath,
      name: 'file',
      header: {
        Authorization: `Bearer ${token}`,
      },
      success: (uploadRes) => {
        const data = JSON.parse(uploadRes.data);
        const imageUrl = data.image_url;

        wx.request({
          url: 'http://127.0.0.1:8000/api/v1/foods',
          method: 'POST',
          header: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          data: {
            food: {
              name: '?????',
              location: '?????',
              price: 18.5,
              image_url: imageUrl,
            },
            sentiment: 'like',
            rating_level: 5,
            review_text: '????????',
            image_url: imageUrl,
          },
        });
      },
    });
  },
});
```

展示时直接渲染：

```html
<image src="{{item.image_url}}" mode="aspectFill" />
```

## 5. 新建食物记录

`POST /foods`

说明：
- `food` 是食物基础信息。
- `sentiment` 和 `rating_level` 是本次记录的用户评价。
- `rating_level` 使用 `1-5` 数字。
- `image_url` 应该传图片上传接口返回的 URL。

请求体示例：

```json
{
  "food": {
    "name": "?????",
    "location": "?????",
    "price": 18.50,
    "image_url": "http://127.0.0.1:8000/media/food_records/food-cover.jpg"
  },
  "sentiment": "like",
  "rating_level": 5,
  "review_text": "????????",
  "image_url": "http://127.0.0.1:8000/media/food_records/record-photo.jpg"
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

## 7. 查询/修改/删除单条记录

- `GET /foods/records/{record_id}`
- `PUT /foods/records/{record_id}`
- `DELETE /foods/records/{record_id}`
- `POST /foods/records/{record_id}/reuse`

## 8. 食物互动统计

`POST /foods/{food_id}/reactions`

## 9. 榜单

`GET /foods/rankings`

可选查询参数：
- `period`：`daily | weekly | all`，默认 `daily`
- `scope`：`global | mine`，默认 `global`

说明：
- `scope=global` 时，返回全体用户范围内的排行榜统计。
- `scope=mine` 时，返回当前登录用户自己的排行榜统计。
- 排行榜中的 `score` 为该食物在当前 `scope + period` 过滤结果下，所有记录 `rating_level` 的平均分。
- 当有新记录创建、旧记录删除、或记录的 `rating_level` 被修改后，`score` 会随排行榜查询结果实时变化。
- 排行榜中的 `like_count`、`dislike_count` 也都基于当前 `scope + period` 的记录范围分别统计。

响应字段说明：
- `food_id`：食物 ID
- `food_name`：食物名称
- `location`：地点
- `price`：价格
- `like_count`：当前统计范围内 `sentiment=like` 的记录数
- `dislike_count`：当前统计范围内 `sentiment=dislike` 的记录数
- `score`：当前统计范围内 `rating_level` 平均分，保留两位小数

## 10. 推荐

- `GET /foods/recommendations/daily`
- `GET /foods/recommendations/personalized`

## 11. 评论

- `POST /foods/records/{record_id}/comments`
- `GET /foods/records/{record_id}/comments`

## 12. 年度报告

`GET /reports/annual/{year}`

## 13. 路由语义说明

- `food_id`：食物实体 ID，用于榜单、互动统计、聚合分析。
- `record_id`：用户某次打卡记录 ID，用于评论、编辑、删除、复用。
- 前端可以先上传图片获得 `image_url`，再把 `image_url` 传给食物记录相关接口。
