create table public.retailcrm_orders (
    id bigint generated always as identity primary key,
    retailcrm_order_id bigint,
    retailcrm_external_id text,
    order_number text,
    site text,
    status text,
    order_type text,
    order_method text,

    first_name text,
    last_name text,
    phone text,
    email text,

    city text,
    address_text text,

    total_sum numeric(12,2),
    currency text,

    order_created_at timestamptz,
    order_updated_at timestamptz,
    synced_at timestamptz not null default now(),

    raw_order jsonb not null
);

create unique index uq_retailcrm_orders_order_id
    on public.retailcrm_orders (retailcrm_order_id);

create unique index uq_retailcrm_orders_external_id
    on public.retailcrm_orders (retailcrm_external_id)
    where retailcrm_external_id is not null;

create table public.retailcrm_order_items (
    id bigint generated always as identity primary key,
    retailcrm_order_id bigint not null references public.retailcrm_orders(retailcrm_order_id) on delete cascade,
    line_position integer,
    product_name text,
    quantity numeric(12,3),
    initial_price numeric(12,2),
    raw_item jsonb not null
);

create table public.sync_state (
    source text primary key,
    last_since_id bigint,
    last_sync_at timestamptz
);

insert into public.sync_state(source, last_since_id, last_sync_at)
values ('retailcrm_orders', null, null)
on conflict (source) do nothing;