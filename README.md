# Chilemei Backend

Backend for the Chilemei mini-program, built with `FastAPI + SQLAlchemy + MySQL`.

The image flow is now aligned with WeChat Cloud Hosting and object storage:

- The frontend uploads images directly to `media/tmp/`
- When a record is submitted, the frontend sends only `image_filename`
- The backend moves the object from `media/tmp/{image_filename}` to `media/food/{food_id}/{image_filename}`
- The database stores:
  - `food.image_dir`, for example `food/12`
  - `food_records.image_filename`, for example `1719999999999-abcd1234.jpg`
- The frontend renders images with the `image_url` returned by the backend

## Quick Start

Install dependencies:

```bash
pip install -r requirements.txt
```

Initialize MySQL:

```sql
source sql/init_mysql.sql;
```

Copy `.env.example` to `.env`, fill in the values, then start the server:

```bash
uvicorn app.main:app --reload
```

## Important Environment Variables

- `WECHAT_APP_ID`
- `WECHAT_APP_SECRET`
- `COS_BUCKET`
- `COS_REGION`
- `COS_PUBLIC_DOMAIN`
- `COS_SECRET_ID`
- `COS_SECRET_KEY`
- `COS_SESSION_TOKEN` (optional)

## Authentication

Production login endpoint:

- `POST /api/v1/auth/wechat-login`

Flow:

1. The mini-program gets a WeChat login `code`
2. The backend calls `code2Session`
3. The backend finds or creates a user with `openid / unionid`
4. The backend returns an application JWT

## Image Workflow

The current responsibility split is:

1. The frontend uploads the image to WeChat cloud storage under `media/tmp/`
2. The frontend keeps the returned `image_filename`
3. The frontend submits `POST /api/v1/foods` or `PUT /api/v1/foods/records/{record_id}` with `image_filename`
4. The backend resolves the target `food_id` and moves the object into `media/food/{food_id}/`
5. The backend returns `image_url`
6. The frontend renders `<image src="{{item.image_url}}">`

Important notes:

- Temporary image deletion no longer uses a backend HTTP endpoint
- The frontend should call `wx.cloud.deleteFile` directly
- Temporary image deletion uses `fileID`
- Formal record submission uses `image_filename`

## Main Endpoints

- `POST /api/v1/auth/wechat-login`
- `GET /api/v1/users/me`
- `PUT /api/v1/users/me`
- `PUT /api/v1/users/me/privacy`
- `GET /api/v1/foods/search`
- `POST /api/v1/foods`
- `GET /api/v1/foods`
- `GET /api/v1/foods/recommendations/daily`
- `GET /api/v1/foods/recommendations/personalized`
- `GET /api/v1/foods/{food_id}/detail`
- `GET /api/v1/foods/rankings`
- `GET /api/v1/foods/records/{record_id}`
- `PUT /api/v1/foods/records/{record_id}`
- `DELETE /api/v1/foods/records/{record_id}`
- `POST /api/v1/foods/records/{record_id}/reuse`
- `POST /api/v1/foods/{food_id}/reactions`
- `POST /api/v1/foods/records/{record_id}/comments`
- `GET /api/v1/foods/records/{record_id}/comments`
- `GET /api/v1/reports/annual/{year}`

See `docs/api_reference.md` for concrete request and response examples.
