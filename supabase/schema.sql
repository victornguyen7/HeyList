-- HeyList schema. Run once in the Supabase SQL editor (Dashboard > SQL Editor > New query > Run).
-- Safe to run again: every statement is "if not exists" or "on conflict do nothing".
--
-- Money is integer cents everywhere (decision 22).
-- Row level security is on with no policies, so only the backend's secret key can read or write.
-- The browser never talks to Supabase; it goes through the FastAPI backend.

-- A list. Its id is the share link: anyone who has it can view, check, and claim (decision 6).
create table if not exists lists (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  -- The list type History groups spending by: groceries, trip, home, party, other.
  kind text not null default 'other' check (kind in ('groceries', 'trip', 'home', 'party', 'other')),
  budget_cents integer check (budget_cents >= 0),
  created_at timestamptz not null default now(),
  -- Set when the list is finished; a finished list shows in History.
  finished_at timestamptz
);

-- The people on a list. No accounts: a person is a name, plus an email once they settle up.
create table if not exists members (
  id uuid primary key default gen_random_uuid(),
  list_id uuid not null references lists (id) on delete cascade,
  name text not null,
  -- Where a PayPal invoice is sent. Only needed for settle-up.
  email text,
  created_at timestamptz not null default now(),
  unique (list_id, name)
);

-- A scanned receipt. The image is in the "receipts" storage bucket at image_path.
create table if not exists receipts (
  id uuid primary key default gen_random_uuid(),
  list_id uuid not null references lists (id) on delete cascade,
  -- Who paid.
  member_id uuid references members (id) on delete set null,
  image_path text not null,
  total_cents integer check (total_cents >= 0),
  -- Every line Textract read, with the list item the AI proposed for it, until the person confirms:
  -- [{"text": "2% MILK 1GAL", "priceCents": 429, "confidence": 98.1, "lowConfidence": false, "itemId": "<uuid>" | null}, ...]
  lines jsonb not null default '[]',
  -- Receipt lines that matched no list item: [{"name": "...", "priceCents": 123}, ...]
  extras jsonb not null default '[]',
  -- Set when the person confirmed the matches and the items were checked off. Null means proposals only.
  confirmed_at timestamptz,
  created_at timestamptz not null default now()
);

-- A PayPal order. Stored when it is created, so the capture knows which items it paid for.
-- A COMPLETED order is the proof its items were bought (decision 8).
create table if not exists orders (
  -- The PayPal order ID.
  id text primary key,
  list_id uuid not null references lists (id) on delete cascade,
  -- Who paid.
  member_id uuid references members (id) on delete set null,
  item_ids uuid[] not null,
  -- What PayPal charges for each item, all units: {"<item id>": cents}. Fixed when the order is created,
  -- so a quantity or price changed while the buyer is on PayPal doesn't change what is recorded as paid.
  prices jsonb not null default '{}',
  -- The total the server computed and sent to PayPal.
  total_cents integer not null check (total_cents > 0),
  status text not null default 'CREATED',
  created_at timestamptz not null default now(),
  captured_at timestamptz
);

create table if not exists items (
  id uuid primary key default gen_random_uuid(),
  list_id uuid not null references lists (id) on delete cascade,
  name text not null,
  position integer not null default 0,
  -- How many to buy; PayPal Checkout charges est_price_cents x quantity.
  quantity integer not null default 1 check (quantity between 1 and 99),
  -- The estimate (from the LLM or typed in). This is what PayPal Checkout charges.
  est_price_cents integer check (est_price_cents >= 0),
  -- What was actually paid for all of them, from the receipt or the captured order.
  price_cents integer check (price_cents >= 0),
  -- Who said they will buy it.
  claimed_by uuid references members (id) on delete set null,
  -- Who checked it off (and paid, when there is a price).
  bought_by uuid references members (id) on delete set null,
  checked_at timestamptz,
  -- The proof: at most one of these is set.
  receipt_id uuid references receipts (id) on delete set null,
  order_id text references orders (id) on delete set null,
  created_at timestamptz not null default now(),
  constraint items_one_proof check (receipt_id is null or order_id is null)
);

-- A PayPal invoice sent for settle-up: debtor owes creditor amount_cents.
create table if not exists invoices (
  -- The PayPal invoice ID.
  id text primary key,
  list_id uuid not null references lists (id) on delete cascade,
  debtor_id uuid references members (id) on delete set null,
  creditor_id uuid references members (id) on delete set null,
  amount_cents integer not null check (amount_cents > 0),
  -- PayPal's invoice status: DRAFT, SENT, PAID, CANCELLED, ...
  status text not null,
  -- The page where the debtor pays.
  pay_url text,
  created_at timestamptz not null default now()
);

create index if not exists items_list_id on items (list_id);
create index if not exists receipts_list_id on receipts (list_id);
create index if not exists orders_list_id on orders (list_id);
create index if not exists invoices_list_id on invoices (list_id);

alter table lists enable row level security;
alter table members enable row level security;
alter table receipts enable row level security;
alter table orders enable row level security;
alter table items enable row level security;
alter table invoices enable row level security;

-- Private bucket for receipt photos. The backend uploads and serves them; there is no public URL.
insert into storage.buckets (id, name, public)
values ('receipts', 'receipts', false)
on conflict (id) do nothing;

-- Upgrades for a database created from an older version of this file ("if not exists" above skips existing tables).
alter table items add column if not exists quantity integer not null default 1 check (quantity between 1 and 99);
alter table items drop constraint if exists items_one_proof;
alter table items add constraint items_one_proof check (receipt_id is null or order_id is null);
alter table lists drop constraint if exists lists_kind_check;
alter table lists add constraint lists_kind_check check (kind in ('groceries', 'trip', 'home', 'party', 'other'));
alter table receipts add column if not exists lines jsonb not null default '[]';
alter table receipts add column if not exists confirmed_at timestamptz;
alter table orders add column if not exists prices jsonb not null default '{}';
-- unique (list_id, name) already indexes members by list_id.
drop index if exists members_list_id;
