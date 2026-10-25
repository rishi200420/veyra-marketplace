VEYRA — MILESTONE 11: RETURNS, REFUNDS & CANCELLATIONS

Files updated:
- backend/app/main.py
- src/Admin.tsx
- src/App.tsx

Features:
- Signed-in customers can request cancellation while an order is awaiting payment, confirmed, or processing (before dispatch).
- Signed-in customers can request a return only after the order is marked delivered.
- Founder and Manager can review requests from Admin > Returns & cancellations.
- Cancellation approval releases reserved variant stock and cancels the order parcels.
- Return requests support approval, marking the return received, refund-pending and manually-refunded tracking.
- Refund fields are workflow records only; this milestone does not move money or call a payment provider.
- Open duplicate requests of the same type for one order are prevented.

IMPORTANT SAFE APPLY:
1. Back up backend/app/main.py, src/Admin.tsx and src/App.tsx.
2. Replace only those three source files.
3. Do NOT replace backend/.env, root .env.local, backend/veyra.db, backend/uploads, or node_modules.
4. Restart the backend and Vite frontend.
5. Run a test order through mock checkout and test cancellation/return rules before relying on this for real customers.

The archive intentionally excludes .env files, the local SQLite database, uploaded product photos, and node_modules.
