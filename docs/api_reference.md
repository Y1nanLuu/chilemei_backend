# API Reference

Base prefix: `/api/v1`

All endpoints except login require:

```http
Authorization: Bearer <token>
```

## 1. WeChat Login

`POST /auth/wechat-login`

Request body:

```json
{
  "code": "wx-login-code"
}
```

Response example:

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

## 2. Image and Record Submission Flow

Image upload does not go through a backend binary upload endpoint anymore.

Frontend flow:

1. Upload the image directly to WeChat cloud storage under `media/tmp/`
2. Keep the returned `image_filename`
3. Submit `POST /foods` or `PUT /foods/records/{record_id}` with `image_filename`
4. If the user cancels or replaces the temporary image, call `wx.cloud.deleteFile`

Responsibility boundary:

- Formal record submission to the backend uses `image_filename`
- Temporary image deletion uses `wx.cloud.deleteFile`
- Temporary image deletion passes `fileID`, not `image_filename`
- The backend does not provide a separate temporary-image deletion HTTP endpoint

After receiving `image_filename`, the backend will:

1. Resolve the final `food_id`
2. Move the object from `media/tmp/{image_filename}` to `media/food/{food_id}/{image_filename}`
3. Store:
   - `food.image_dir = food/{food_id}`
   - `food_records.image_filename = {image_filename}`
4. Return a public `image_url`

## 3. Create Food Record

`POST /foods`

Rules:

- `food_id` and `food` are mutually exclusive
- If `food_id` is provided, the backend attaches the record to an existing food
- If `food` is provided, the backend finds or creates a food by `name + location`
- `image_filename` must be the filename produced by the frontend upload step
- The backend does not accept binary image data, `image_url`, or `fileID`

Example using an existing food:

```json
{
  "food_id": 12,
  "sentiment": "like",
  "rating_level": 5,
  "review_text": "Very tasty",
  "image_filename": "1719999999999-abcd1234.jpg"
}
```

Example creating a new food and a new record:

```json
{
  "food": {
    "name": "Braised Beef Noodles",
    "location": "Canteen 1, Floor 2",
    "price": 18.5
  },
  "sentiment": "like",
  "rating_level": 5,
  "review_text": "Very tasty",
  "image_filename": "1719999999999-abcd1234.jpg"
}
```

Response example:

```json
{
  "id": 101,
  "user_id": 1,
  "food_id": 12,
  "food": {
    "id": 12,
    "name": "Braised Beef Noodles",
    "location": "Canteen 1, Floor 2",
    "price": 18.5,
    "image_dir": "food/12"
  },
  "sentiment": "like",
  "rating_level": 5,
  "review_text": "Very tasty",
  "image_filename": "1719999999999-abcd1234.jpg",
  "image_url": "https://chilemei-240951-4-1328995507.sh.run.tcloudbase.com/media/food/12/1719999999999-abcd1234.jpg",
  "uploaded_at": "2026-04-01T10:00:00+08:00",
  "like_count": 0,
  "dislike_count": 0,
  "created_at": "2026-04-01T10:00:00+08:00",
  "updated_at": "2026-04-01T10:00:00+08:00"
}
```

## 4. Search Foods

`GET /foods/search?keyword=noodles&limit=10`

Returns food base information that the frontend can use for auto-fill.

## 5. List Records

`GET /foods`

Optional query parameters:

- `food_name`
- `location`
- `sentiment`
- `mine_only`
- `start_time`
- `end_time`

## 6. Single Record Endpoints

- `GET /foods/records/{record_id}`
- `PUT /foods/records/{record_id}`
- `DELETE /foods/records/{record_id}`
- `POST /foods/records/{record_id}/reuse`

If a new `image_filename` is provided during update, the backend applies the same archive rule.

## 7. Food Reactions

`POST /foods/{food_id}/reactions`

## 8. Recommendations, Rankings, and Detail

- `GET /foods/recommendations/daily`
- `GET /foods/recommendations/personalized`
- `GET /foods/rankings`
- `GET /foods/{food_id}/detail`

Image fields:

- `image_url`: image for a specific record
- `cover_image_url`: cover image for a food card
- `image_urls`: image list for the food detail page

These URLs are built from `food.image_dir + image_filename`.

## 9. Comments

- `POST /foods/records/{record_id}/comments`
- `GET /foods/records/{record_id}/comments`

## 10. Annual Report

`GET /reports/annual/{year}`
