# API Reference

Base prefix: `/api/v1`

All endpoints except login require:

```http
Authorization: Bearer <token>
```

## 1. WeChat Login

`POST /auth/wechat-login`

## 2. User Profile and Preferences

`GET /users/me`

Response now includes preference fields:

```json
{
  "id": 1,
  "username": "alice",
  "email": "alice@example.com",
  "nickname": "Alice",
  "bio": "爱吃面食",
  "avatar_url": null,
  "is_private": false,
  "taste_preferences": ["川菜", "面食", "酸辣"],
  "taboo_list": ["香菜", "内脏"],
  "spicy_level": 4,
  "created_at": "2026-04-01T10:00:00+08:00"
}
```

`PUT /users/me`

Only updates base profile fields:
- `nickname`
- `bio`
- `avatar_url`

`PUT /users/me/preferences`

Request body:

```json
{
  "taste_preferences": ["川菜", "面食", "酸辣"],
  "taboo_list": ["香菜", "内脏"],
  "spicy_level": 4
}
```

Response body:

```json
{
  "taste_preferences": ["川菜", "面食", "酸辣"],
  "taboo_list": ["香菜", "内脏"],
  "spicy_level": 4
}
```

Validation rules:
- `spicy_level` must be an integer in `0-5`
- `taste_preferences` and `taboo_list` are trimmed and deduplicated automatically
- empty arrays are allowed

`PUT /users/me/privacy`

Updates only `is_private`.

## 3. Image and Record Submission Flow

Image upload does not go through a backend binary upload endpoint anymore.

## 4. Create Food Record

`POST /foods`

## 5. Search Foods

`GET /foods/search?keyword=noodles&limit=10`

## 6. List Records

`GET /foods`

## 7. Single Record Endpoints

- `GET /foods/records/{record_id}`
- `PUT /foods/records/{record_id}`
- `DELETE /foods/records/{record_id}`
- `POST /foods/records/{record_id}/reuse`

## 8. Recommendations, Rankings, and Detail

- `GET /foods/recommendations/daily`
- `GET /foods/recommendations/personalized`
- `GET /foods/rankings`
- `GET /foods/{food_id}/detail`

`GET /foods/recommendations/personalized` now incorporates user profile features:
- `taste_preferences`
- `taboo_list`
- `spicy_level`

## 9. Comments

- `POST /foods/records/{record_id}/comments`
- `GET /foods/records/{record_id}/comments`

## 10. Annual Report

`GET /reports/annual/{year}`
