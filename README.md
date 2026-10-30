# Multi-Company ERP (Odoo 18)

Three companies (A: laptops, B: furniture, C: groceries) buy, sell, invoice and collect payment on their own products.

## Layout (same idea as Express: routes -> services -> models)

- `controllers/main.py`: REST routes. Turns HTTP into Python and back. No business rules.
- `services/`: all business rules (`stock.py`, `sale.py`, `purchase.py`, `invoice.py`).
- `models/`: fields, computed fields and constraints only. The form buttons call the services.
- `security/`: the five roles, access rights and company rules.
- `views/`: the screens.

## The six business logics

1. **Company isolation**: users only see their own company's records. `security/security.xml`, one record rule per model.
2. **Sales confirm**: blocked if stock is short, otherwise stock goes out. `services/sale.py`, `confirm`.
3. **Stock ledger**: quantity is the sum of stock moves, never typed in. `models/product.py`, `quantity`.
4. **Purchase receive**: adds stock once per order. `services/purchase.py`, `receive`.
5. **Invoice**: a confirmed sale creates one invoice. `services/sale.py`, `confirm`, plus unique `sale_id`.
6. **Payment**: reduces the amount due, and zero due means paid. `models/invoice.py`, `_compute_amounts`.

## The five roles

- **Sales**: creates and confirms sale orders, sees products and invoices.
- **Purchase**: creates purchase orders, sees products.
- **Warehouse**: receives purchase orders, sees products and stock moves.
- **Accountant**: sees sale orders and invoices, records payments.
- **Admin**: everything above, plus manages products.

## REST API

Send `Authorization: Bearer <API key>`. Create a key in Odoo under your avatar > Preferences > Account Security > New API Key (turn on Developer mode if you do not see it).
Add `?company_id=<id>` to work in one company. Without it you see every company you belong to and new records go to your default company.
Replies are `{"data": ...}` on success and `{"error": "message"}` on failure (400 bad input or business rule, 401 no or wrong key, 403 not allowed, 404 not found).

- `GET /api/products` (Sales, Purchase, Warehouse)
- `GET /api/stock-moves` (Warehouse)
- `GET /api/sales` and `GET /api/sales/<id>` (Sales)
- `POST /api/sales` with `{"customer_id": 7, "lines": [{"product_id": 1, "quantity": 4}]}` (Sales)
- `POST /api/sales/<id>/confirm` (Sales)
- `GET /api/purchases` (Purchase, Warehouse)
- `POST /api/purchases` with `{"vendor_id": 8, "lines": [{"product_id": 1, "quantity": 10}]}` (Purchase)
- `POST /api/purchases/<id>/receive` (Warehouse)
- `GET /api/invoices` and `GET /api/invoices/<id>` (Accountant, Sales)
- `POST /api/invoices/<id>/payments` with `{"amount": 1000}` (Accountant)

Example:

    curl -H "Authorization: Bearer $KEY" "http://localhost:8069/api/products?company_id=2"

## Run with Docker (database included)

    docker compose up -d

Open http://localhost:8069 and log in as `admin` / `admin`. This starts PostgreSQL 16 and Odoo 18 together. The database `erp` is created on the first run and its data lives in the Docker volume `my_module_pgdata`.

- Upgrade after changing code: `docker compose run --rm odoo odoo -d erp -u my_module --stop-after-init` then `docker compose restart odoo`
- Run the tests: `docker compose run --rm odoo odoo -d testdb -i my_module --test-tags /my_module --stop-after-init`, then `docker compose exec db psql -U odoo -d postgres -c "DROP DATABASE testdb"`
- Look inside the database: `docker compose exec db psql -U odoo -d erp`
- Stop: `docker compose stop`. Delete everything including the data: `docker compose down -v`

## Install without Docker

    python3 odoo-bin -d mydb --addons-path=addons,/path/to/parent/of/my_module -i my_module

Installing creates Company A, B and C and gives the `admin` user all three companies and the Admin role. Each company starts with one product at stock 0, so the first step is always a purchase.

## Run the tests

    python3 odoo-bin -d testdb --addons-path=addons,/path/to/parent/of/my_module -i my_module --test-tags /my_module --stop-after-init
