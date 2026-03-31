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
- 上传阶段后端只接收二进制图片文件，不要求同时传 `food_id`、`food_name`、`location`、`price`。
- 图片会先保存到临时目录 `media/temp/`。
- 接口返回的 `image_url` 仅用于前端上传成功后的页面预览。
- 后续创建记录时，前端只需要把 `image_filename` 传给 `POST /foods`；后端会在创建记录时把该图片归档到 `media/food/<food_id>/`。
- 如果用户在正式提交记录前更换图片或取消发布，前端应调用 `DELETE /foods/upload-image?image_filename=...` 删除旧的临时图片。

响应示例：

```json
{
  "image_dir": "temp",
  "image_filename": "3d9f0e4a9f1b4d8f8d3f1a2b3c4d5e6f.jpg",
  "image_url": "/media/temp/3d9f0e4a9f1b4d8f8d3f1a2b3c4d5e6f.jpg",
  "stored_path": "temp/3d9f0e4a9f1b4d8f8d3f1a2b3c4d5e6f.jpg",
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
        const imageFilename = data.image_filename;

        wx.request({
          url: 'http://127.0.0.1:8000/api/v1/foods',
          method: 'POST',
          header: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          data: {
            food_id: 12,
            sentiment: 'like',
            rating_level: 5,
            review_text: '好吃',
            image_filename: imageFilename,
          },
        });
      },
    });
  },
});
```

展示时直接渲染：

```html
<image src="{{previewImageUrl}}" mode="aspectFill" />
```

删除临时图片接口：`DELETE /foods/upload-image?image_filename=3d9f0e4a9f1b4d8f8d3f1a2b3c4d5e6f.jpg`

说明：
- 该接口用于清理还未正式提交记录时留在 `media/temp/` 下的旧图片。
- 前端在用户更换准备上传的图片，或取消本次发布时，应先删除上一张临时图片。

## 5. 新建食物记录

`POST /foods`

说明：
- 创建记录时，`food_id` 和 `food` 二选一。
- 如果传 `food_id`，后端直接绑定已存在的食物。
- 如果传 `food`，后端会先按 `name + location` 查找食物；若不存在，则先创建新的 `food`，再创建 `record`。
- `food` 在业务语义上由 `id` 唯一标识，也由 `name + location` 唯一标识。
- `sentiment` 和 `rating_level` 是本次记录的用户评价。
- `rating_level` 使用 `1-5` 数字。
- `image_filename` 应该传图片上传接口返回的文件名。`image_url` 仅用于上传成功后的前端预览。

配套搜索建议接口：

`GET /foods/search?keyword=xxx&limit=10`

说明：
- 前端输入食物名称时，可调用该接口获取同名或近似名称的已存在食物列表。
- 用户选择已存在食物后，可直接使用返回的 `id/name/location/price/image_dir` 进行自动填充。
- 如果用户选择“新建食物”，则前端继续提交完整 `food` 对象即可。

使用已存在食物创建记录示例：

```json
{
  "food_id": 12,
  "sentiment": "like",
  "rating_level": 5,
  "review_text": "????????",
  "image_filename": "3d9f0e4a9f1b4d8f8d3f1a2b3c4d5e6f.jpg"
}
```

使用新食物创建记录示例：

```json
{
  "food": {
    "name": "?????",
    "location": "?????",
    "price": 18.50
  },
  "sentiment": "like",
  "rating_level": 5,
  "review_text": "????????",
  "image_filename": "3d9f0e4a9f1b4d8f8d3f1a2b3c4d5e6f.jpg"
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
- `POST /foods/records/{record_id}/reuse`（返回复用草稿，不直接创建新记录）

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
- 榜单接口现在返回和首页推荐一致的 `food card` 结构，前端可以复用同一套卡片组件。
- 榜单中的 `score` 为该食物在当前 `scope + period` 过滤结果下，所有记录 `rating_level` 的平均分。
- 榜单中的 `like_count`、`dislike_count` 也都基于当前 `scope + period` 的记录范围分别统计。
- 榜单中的 `cover_image_url` 会从 `media/food/<food_id>/` 目录中随机选择一张图片。
- 点击榜单卡片后，可继续调用 `GET /foods/{food_id}/detail` 获取详情页数据。

响应字段说明：
- `food_id`：食物 ID
- `name`：食物名称
- `location`：地点
- `price`：价格
- `score`：当前统计范围内 `rating_level` 平均分，保留两位小数
- `like_count`：当前统计范围内 `sentiment=like` 的记录数
- `dislike_count`：当前统计范围内 `sentiment=dislike` 的记录数
- `cover_image_url`：食物卡片封面图

## 10. 推荐

- `GET /foods/recommendations/daily`
- `GET /foods/recommendations/personalized`
- `GET /foods/{food_id}/detail`

说明：
- 推荐接口现在以 `food` 为单位返回，而不是以 `record` 为单位。
- 首页卡片返回 `food_id/name/location/price/score/like_count/dislike_count/cover_image_url`。
- `cover_image_url` 会从 `media/food/<food_id>/` 目录中随机选择一张图片。
- 详情接口返回该食物的全部图片 `image_urls`，前端可用于左右滑动展示。
- 详情接口还会返回一个可展示的 `description`（最近一条非空评价）以及聚合后的 `comments`。

## 11. 评论

- `POST /foods/records/{record_id}/comments`
- `GET /foods/records/{record_id}/comments`

## 12. 年度报告

`GET /reports/annual/{year}`

## 13. 路由语义说明

- `food_id`：食物实体 ID，用于榜单、互动统计、聚合分析。
- `record_id`：用户某次打卡记录 ID，用于评论、编辑、删除、获取复用草稿。
- 前端可以先上传图片文件，拿到 `image_filename` 和临时 `image_url`；随后创建记录时只传 `image_filename`，正式展示地址由 `food.image_dir + image_filename` 组合得到。


