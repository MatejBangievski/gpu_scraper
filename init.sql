create table store
(
    id          serial
        primary key,
    name        varchar not null
        unique,
    website_url text
);

create table component
(
    id   serial
        primary key,
    type varchar(255) not null
);

create table gpu
(
    component_id integer not null
        primary key
        references component
            on delete cascade,
    manufacturer varchar(100),
    brand        varchar(100),
    model        varchar(100),
    vram         integer,
    unique (manufacturer, brand, model, vram)
);

create table product_listing
(
    id           serial
        primary key,
    component_id integer                 not null
        references component
            on delete cascade,
    store_id     integer                 not null
        references store
            on delete cascade,
    price        numeric(10, 2)          not null,
    club_price   numeric(10, 2),
    available    boolean                 not null,
    description  text                    not null,
    url          text                    not null,
    img_url      text,
    last_updated timestamp default now() not null,
    unique (component_id, store_id, url)
);

create index idx_gpu_model on gpu (model);