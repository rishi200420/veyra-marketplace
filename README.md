# VEYRA — Multi-Brand Fashion Marketplace (Development MVP)

VEYRA is a curated marketplace concept for independent men's fashion labels. Each brand keeps its own identity and owns/fulfils its stock; the platform provides a unified discovery and customer experience.

**Working name:** VEYRA is provisional; trademark, domain and social-handle checks remain pending. **Demo data:** product names, brands, SKUs, prices and stock are illustrative. Images use external Unsplash URLs and must be reviewed/licensed before production.

## Requirements
- Node.js 20+ recommended
- Python 3.11+
- VS Code recommended

## Run frontend
From the project root: `npm install`, then `npm run dev`. Open the Vite URL shown, usually `http://localhost:5173`. Run `npm run build` to check the frontend build. The storefront attempts to load the API catalogue first and uses local demo products if the API is unavailable.

## Run backend
Open a second terminal:
```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```
Edit `backend/.env` and set both `ADMIN_API_TOKEN` and `CUSTOMER_TOKEN_SECRET` to unique random secrets (the customer secret must be at least 32 characters). Keep `.env` private. Then run `uvicorn app.main:app --reload`. API docs: `http://127.0.0.1:8001/docs`. SQLite is used by default.

## Included
- Responsive premium editorial storefront
- Search, category filtering, independent-label filtering, price caps, sorting, persistent saved pieces, and a persistent demo bag
- Product detail modal with size selection, quantity selection, save-for-later, and size guide message
- Bag quantity controls, size-aware bag lines, remove actions, subtotal calculation, and empty states
- FastAPI API with SQLAlchemy models for brands, products, parent orders and brand suborders
- Local SQLite database and illustrative seed data
- Public product/brand endpoints and admin-token-protected endpoints
- Demo order endpoint that groups items by brand and can link an order to the authenticated customer
- Milestone 8 customer registration/sign-in with PBKDF2 password hashing, signed 7-day bearer tokens, profile/address/favourites persistence, and account-scoped order history

## Not production-ready
This is a runnable development foundation, not a complete live marketplace. It does not yet include payment verification, production-grade session revocation/rate limiting, real shipping integration, notifications, operational returns/refunds, complete staff RBAC or deployment hardening. The order endpoint creates unpaid demo orders only. Do not use it for real transactions.

## Shopping experience update
The latest update adds a product details panel, size selection, quantity controls, saved pieces that persist in local browser storage, a size-aware shopping bag that persists in local browser storage, label and price filters, and clearer product-detail actions. Sizes and stock displayed in this prototype are illustrative; stock is not yet enforced at checkout.

## Customer accounts (Milestone 8 — development)
- Register and sign in with email/password; passwords are hashed using PBKDF2-HMAC-SHA256.
- Customer sessions use signed bearer tokens that expire after 7 days. Set `CUSTOMER_TOKEN_SECRET` to a unique random secret of at least 32 characters.
- Profile name, phone, saved addresses and favourites are stored in the backend for signed-in customers.
- Signed-in checkout links orders to the customer account; `GET /api/v1/account/orders` returns only that account's orders. Guest checkout remains available, but guest orders do not appear in account history.
- Customer login is separate from admin token authentication. This remains a development implementation and needs rate limiting, email verification, password reset, session revocation, security review and HTTPS before production.

## Next milestones
Verified payment webhooks, shipment tracking and returns workflows must be completed before any public launch.


## Men's-only catalogue correction
Sample storefront and backend seed images were changed to menswear-oriented imagery for this men's-only marketplace. Product names/prices remain illustrative. Verify image suitability and licensing before production.


## Customer experience milestone (development)
- Added a real size-guide modal with a general men's size table (fit differs by independent brand).
- Added an account information panel; actual authentication is not yet connected.
- Added a checkout form for contact and shipping details, address validation, delivery option selection, order summary, and a local demo order confirmation.
- Added customer information panels for shipping, returns, contact, privacy and terms.
- The demo checkout intentionally does **not** charge a payment method, submit personal data to a server, reserve inventory, email a receipt, or create a fulfilment/shipping request. Do not use it for real orders.
- Shipping fees, estimated delivery and return policy copy are placeholders and must be confirmed with participating labels before production.


## Customer order history milestone
- Added a customer-facing Orders entry and order-history drawer.
- Demo orders are stored in browser local storage and survive page refreshes on the same browser/device.
- Each order shows reference, timestamp, items, sizes, quantities, delivery area and demo total.
- Order status is explicitly marked as a demo receipt. Real fulfilment, carrier tracking, server persistence and account-linked order history are not connected.


## Customer profile milestone
- Added editable customer profile details (name, email, mobile).
- Added saved delivery addresses with label, street, city, state and 6-digit PIN validation.
- Customers can review and remove saved addresses and navigate to order history.
- Profile/address data persists in local browser storage only. There is no account authentication, server sync, encryption guarantee or cross-device access in this prototype; do not use real sensitive customer data.

## Customer journey milestone — saved checkout addresses and order journey
- Checkout now pre-fills profile contact details and the first saved delivery address when available.
- Customers can select another saved address or switch back to entering a new address.
- Order history includes the delivery address, expandable order details, a clearly labelled illustrative status timeline, and brand-specific parcel previews.
- Tracking remains a demo preview only: no carrier, dispatch events, or live shipment tracking are connected.
- Saved profile, addresses, bag, wishlist, and demo orders remain local to the browser; this is not authenticated account storage.

## Customer discovery milestone — recently viewed
- Added a recently viewed section after the main catalogue so shoppers can return to products they opened earlier.
- Recently viewed product IDs persist in browser local storage and are limited to the six most recent unique items.
- Customers can clear this local viewing history at any time.
- This is device-local convenience only; it is not synced to an authenticated account.

## Customer quality and resilience milestone
- Added a neutral local SVG fallback for product thumbnails and detail/cart/order images when a catalogue image URL is missing or fails to load.
- Mobile navigation now closes after a section is selected.
- Empty search/filter results now include a direct reset action.
- Added visible keyboard-focus outlines and disabled-button styling for improved accessibility.
- Clarified that newsletter signup is a local demo and does not subscribe the visitor to a mailing provider.
- Build/browser verification is still pending because dependency installation timed out in the development environment.


## Accessibility and modal interaction milestone
- Added Escape-key handling to close the active customer panel/modal, including search and mobile navigation.
- Prevented background page scrolling while customer dialogs and drawers are open, restoring the prior scroll setting when closed.
- Added dialog semantics and accessible labels to shopping bag, saved pieces and order history drawers, plus labels for close controls.
- This is a front-end usability improvement; full focus trapping/restoration and automated accessibility testing remain to be completed during QA.
- Corrected the customer-information modal heading expression found during static syntax checking.


## Customer accessibility QA milestone
- Added initial focus placement inside the top-most open customer dialog/drawer.
- Added keyboard Tab / Shift+Tab focus trapping while a dialog is open, including a safe fallback when no focusable controls are available.
- Restores focus to the previously focused element when the dialog closes or a nested dialog is opened/closed.
- Dependency installation was attempted but timed out in this environment. A full Vite production build, browser-based interaction tests, and automated accessibility audit remain unverified and must be run where npm dependencies can be installed.


### Multi-image product gallery milestone
Product details now support a gallery with selectable thumbnails, previous/next controls, and an image counter. `Product.images` is an optional ordered array of image URLs; `image` remains the primary/legacy URL used for catalogue cards, bag, and orders. API products include `images`, and the protected admin product create/PATCH endpoints accept `images` (up to 12 URLs). Gallery URLs are stored in a new `product_images` table, preserving existing SQLite product rows when `create_all` runs. For existing records without gallery rows, the API returns `[image]`. Images are illustrative until brand-approved product photography is provided. No fake alternate angles are generated.


### Product image gallery

Product records support an `images` array (up to 12 image URLs). The customer product-detail view displays the primary image, previous/next controls, a position counter, and selectable thumbnails when multiple unique image URLs are present. The demo catalogue includes additional illustrative menswear image URLs; replace these with approved, product-specific photography before launch.


## Customer product photography audit (demo catalogue)

- Corrected obvious category mismatches in the seeded demo catalogue: trouser products now use trouser-category image URLs, and the Essential Cotton Tee no longer uses a suit/model image as its primary photo.
- Tee galleries use tee-category image URLs; shirt and outerwear galleries retain category-oriented image URLs. Duplicate URLs are deduplicated by the gallery component.
- When the API returns only its single seeded image for one of the eight demo products, the customer UI prefers the curated local demo gallery. Products with a real multi-image API gallery continue to use API-provided images.
- Remote Unsplash assets could not be fetched for visual verification in this environment. These remain illustrative stock/demo images, not approved product photography or guaranteed alternate views of the exact same garment. Before launch, replace them with label-approved images and test that each URL loads.

## Milestone 4: customer shopping experience polish
- Added a mobile-only persistent purchase bar to the product detail view. It mirrors the selected quantity's total and uses the same size validation and add-to-bag handler as the main product action.
- Improved small-screen modal sizing with dynamic viewport units and safe-area spacing for product details, checkout, account/policy dialogs and drawers.
- Increased touch target sizes for size and quantity controls on mobile and refined the product gallery image area for narrow screens.
- Product image URLs remain illustrative remote Unsplash photography. They must be checked and replaced with approved, product-specific photographs before launch; the app cannot infer whether a remote photo depicts the exact SKU/colour/fit.
- Checkout, order status, newsletter and policy content remain prototype experiences. Real payments, shipping, live tracking and operational policies must be connected/approved before launch.

## Milestone 5 — Admin dashboard (development)

- Customer storefront remains at `/`.
- Admin workspace is at `/admin` and uses the FastAPI backend.
- Configure `ADMIN_API_TOKEN` to a strong, unique secret in `backend/.env`; the default `dev-only-change-me` is intentionally rejected by admin endpoints.
- Admin signs in by entering that token. It is held in `sessionStorage` for the current browser tab and sent as `X-Admin-Token` to protected API endpoints.
- Product management supports create/edit, publication toggle, price, category, colour, SKU, total stock, description and up to 12 hosted image URLs.
- Label management supports adding labels and viewing existing labels. Orders show backend orders and brand suborders.
- Image URLs are supported in this milestone; binary file uploads, per-colour/per-size stock variants, staff user accounts/RBAC and production-grade identity provider are not yet implemented.
- Customer demo orders stored in browser localStorage do not automatically appear in the backend admin order list. Only API-created backend orders are listed.

For local development, create `backend/.env` using `.env.example`, set a strong `ADMIN_API_TOKEN`, then start the API and frontend. Never use the development token in production.


### Direct product image uploads

The admin product editor supports multi-file JPG/JPEG and PNG uploads (up to 12 images per product, 8 MB each). The backend stores files under `backend/uploads/`, saves image paths with the product, and serves them to the admin and storefront. Install backend dependencies after updating: `pip install -r requirements.txt`. For local development, keep `VITE_API_BASE_URL=http://127.0.0.1:8001` in the root `.env.local` if the API runs on port 8001.

## Milestone 6 — colour/size variants and inventory

- Admin product editor includes a colour/size inventory matrix. The default apparel sizes are XS, S, M, L, XL and XXL; add rows for each sellable colour-size combination.
- Every variant has its own unique SKU and non-negative stock quantity. The product stock total is calculated from the variants.
- Upload colour-specific gallery images from the image input beneath a variant row. Images are stored by the backend and attached to all rows of that colour; save the product to persist the association.
- Public product APIs return the `variants` array with colour, size, SKU, stock and images. The storefront lets customers choose colour and size, changes the gallery for the selected colour, disables out-of-stock sizes, and limits quantity to available stock.
- Existing catalogue products are backfilled with XS–XXL variant records on startup. Since historical size-level stock was not recorded, the existing total is preserved at size M and other sizes start at zero; review and distribute actual inventory in the admin dashboard.
- Variant data is stored in the `product_variants` SQLite table. Back up `backend/veyra.db` and `backend/uploads/` together.

### Test notes

Backend API tests should cover create/update, unique variant SKUs, duplicate colour-size rejection, stock aggregation and public API persistence. Run `npm run build` in the user's local environment to confirm the TypeScript build after installing dependencies.


## Combined Milestone 7–10 — Order operations, fulfilment and reporting

Implemented in this development build:
- Customer checkout now submits order lines to the FastAPI backend with product ID, variant ID, colour, size, quantity, contact and shipping details.
- Backend validates the exact colour/size variant and available quantity, creates the order and brand-specific suborders, and reserves variant stock in one database transaction.
- Cancelled orders release reserved stock; cancelled orders cannot be reopened.
- Admin order workspace supports order status updates, per-brand parcel status updates and tracking references.
- Admin overview includes stock-on-hand, low-stock alerts, unpaid-order counts and delivered order value (clearly labelled as not payment-reconciled revenue).
- Existing SQLite databases receive additive columns for order contact/shipping details on startup.

### Important launch limitations
This is still a development workflow, not a production checkout. Payment is not connected or verified by a provider; admin status changes are manual and are not proof of payment. There is no customer authentication/verified account system or customer-owned server-side order history yet. No real carrier integration, label purchase, webhook reconciliation, email/SMS notifications, refund workflow, or production security review is included. Do not accept live payments or real orders until those are implemented and tested.

### Testing
The backend API was exercised against a temporary SQLite database: health and catalogue endpoints responded, an order was created against a specific stocked variant, stock decreased by one, admin cancellation restored the reserved stock, and the admin report endpoint responded. Frontend production build could not be confirmed in this environment because dependency installation timed out.


## Milestone 7 — Order management and stock reservation

- Storefront checkout submits order lines to the FastAPI backend, including the selected product variant, colour, size, and quantity.
- The backend validates active products and exact variant availability before creating the order. Variant stock is reserved in the database; insufficient stock is rejected.
- Express delivery fee (₹149 in this development build) is calculated server-side and included in the order total. Brand parcel subtotals remain based on merchandise lines.
- Orders and brand-specific suborders are persisted in SQLite and are visible in the admin Orders & parcels workspace.
- Admin order cancellation releases reserved stock. Cancelling an individual brand parcel also releases its stock; later cancelling the parent order will not release that parcel twice.
- Payment gateway/webhooks and carrier integrations remain unconnected. These are development orders and must not be treated as paid orders.

### Milestone 7 verification

Backend integration checks passed against a temporary SQLite database: order creation persisted, express delivery fee was included, variant stock was reserved, invalid quantities were rejected, and cancelling an order restored stock. A frontend production build could not be confirmed in this environment because `npm install` timed out; run `npm install` and `npm run build` locally to verify the frontend bundle.

## Milestone 9 — Checkout and mock payment workflow

- Checkout remains in development/mock mode; no payment gateway credentials or bank account are needed.
- The checkout offers a local simulation for successful, failed, and cancelled online payment outcomes. This is **not a real payment** and must not be presented as proof of money received.
- Mock success changes the order to `confirmed` and marks it `paid_demo`; failure marks it `failed_demo`; cancellation cancels the order and restores reserved variant stock.
- Admin dashboard → **Settings** includes a persistent COD toggle. It defaults to **OFF**. Keep it OFF until courier collection, remittance, fees, and returns are agreed. Turning the toggle on stores the configuration, but COD courier integration is not implemented.
- Razorpay is not connected. Integrate and verify a real gateway only after business and banking setup is ready.

### New development endpoints
- `GET /api/v1/checkout/config` — public mock payment mode and COD availability.
- `GET /api/v1/admin/settings` — read checkout settings (admin token required).
- `PATCH /api/v1/admin/settings` with `{"cod_enabled": false}` — update COD toggle (admin token required).
- `POST /api/v1/orders/{order_id}/mock-payment` with `{"outcome":"success"}`, `{"outcome":"failed"}`, or `{"outcome":"cancelled"}` — simulate a payment outcome. No money is taken.

The storefront is still a development prototype. Do not enable COD or accept real orders until payment, courier, refund, security, and legal workflows are implemented and tested.


## Milestone 10 — Order management & fulfilment
The admin Orders tab supports order-level status changes and independent status/tracking updates for each brand-specific parcel. Parent order status is recalculated when a parcel changes, which is important when multiple independent labels ship one customer order separately. Tracking references are manually entered; courier integrations and customer notifications are not connected. Continue using mock checkout only.


## Milestone 12 — email notifications (development)
Customer email notifications are optional and disabled by default. Configure SMTP variables in `backend/.env` using `backend/.env.example` as a reference. Events include order receipt, mock checkout result, order status, brand parcel/tracking updates, and return/cancellation request updates. Use the admin notification status and test endpoints in `/docs` to validate SMTP before relying on delivery. This does not connect a payment gateway or move money.
