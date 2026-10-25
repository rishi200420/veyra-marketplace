# VEYRA API

## Setup — Windows PowerShell

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Set a long, unique `ADMIN_API_TOKEN` in `.env`, then run `uvicorn app.main:app --reload`.
API docs: `http://127.0.0.1:8000/docs`.

Endpoints: `GET /health`, `GET /api/v1/brands`, `GET /api/v1/products` (q/category/brand_id/min_price/max_price/sort filters), `GET /api/v1/products/{id}`, `POST /api/v1/orders` (unpaid demo only), `GET /api/v1/admin/brands`, `POST /api/v1/admin/brands`, `PATCH /api/v1/admin/brands/{id}`, `GET /api/v1/admin/products`, `POST /api/v1/admin/products`, `PATCH /api/v1/admin/products/{id}`, `GET /api/v1/admin/orders`. Admin endpoints require `X-Admin-Token` and remain disabled until the environment token is changed.

SQLite is used by default and demo catalogue rows are seeded at first startup. This is a development foundation, not a production commerce backend. Customer authentication, payment verification/webhooks, robust concurrent stock reservation, shipping-carrier integration, notifications, returns/refunds execution, full staff RBAC, and security review remain to be implemented. Demo orders are unpaid; stock is not deducted.


## Product image uploads (development)

Admin users can upload JPG/JPEG or PNG files through `POST /api/v1/admin/uploads/images` using multipart form field `files` and the `X-Admin-Token` header. Each image is limited to 8 MB, with up to 12 images per request. Files are stored under `backend/uploads/` by default and served at `/uploads/<generated-filename>`. Uploaded URLs must then be saved to a product using the existing `images` field. Install the added `python-multipart` dependency with `pip install -r requirements.txt`. Keep the uploads directory on persistent storage; for production, use private/object storage with appropriate access controls and backups.

## Customer accounts (Milestone 8)
Set `CUSTOMER_TOKEN_SECRET` in `backend/.env` to a unique random secret of at least 32 characters. Customer registration/login endpoints are `/api/v1/auth/register` and `/api/v1/auth/login`; authenticated profile operations use `/api/v1/auth/me`, and account order history uses `/api/v1/account/orders`. Customer passwords are PBKDF2-HMAC-SHA256 hashed and sessions expire after 7 days. Keep `.env` private. This is still a development feature and needs production security review before launch.


## Milestone 9 mock checkout
The API supports local-only mock payment outcomes at `POST /api/v1/orders/{order_id}/mock-payment` with `success`, `failed`, or `cancelled`. This never processes real money. COD is controlled by admin-only `GET/PATCH /api/v1/admin/settings` and defaults OFF; the public checkout configuration is available at `GET /api/v1/checkout/config`. Keep COD disabled until courier arrangements are finalized.


## Milestone 10 — order management and fulfilment (development)
- Admin order list supports manual order-status updates and separate status updates for each brand parcel.
- Each brand parcel stores its own shipment tracking reference, allowing independent labels to dispatch separately.
- Updating a parcel recalculates the parent order status from the remaining non-cancelled parcels: delivered when all active parcels are delivered, otherwise the furthest active fulfilment stage. If all parcels are cancelled, the parent order is cancelled.
- Cancelling an order/parcel releases reserved variant stock in the local database. Test cancellation and inventory carefully before any real use.
- This is manual tracking only: no courier API, live tracking events, customer notifications, or carrier-label generation is connected. Payment status must not be inferred from an order's fulfilment status.


## Milestone 12 — email notifications (development)
Email notifications are disabled by default. To enable them, set `EMAIL_NOTIFICATIONS_ENABLED=true` in `backend/.env`, then configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_FROM_NAME`, and `SMTP_USE_TLS`. Port 465 uses SMTP-over-SSL; other ports use STARTTLS when enabled. Never commit `.env` or share mail credentials.

The backend sends customer emails for order receipt, mock checkout outcomes, order status changes, brand-parcel status/tracking updates, return/cancellation request creation, and return/cancellation decisions. Delivery errors are logged by error type only and do not undo the order update. Notifications are plain text. Mock payment and manual refund emails explicitly state that no money was automatically moved.

Admin-only endpoints: `GET /api/v1/admin/notifications/status` reports whether email is enabled/configured; `POST /api/v1/admin/notifications/test` accepts `{"email":"your-address@example.com"}` and sends a test email. Both require the current admin session in the `X-Admin-Token` header. Test delivery in development before relying on these emails. Email delivery depends on your SMTP provider, sender verification and network access.
