CREATE EXTENSION IF NOT EXISTS citext;

DO $$ BEGIN
    CREATE TYPE user_role as ENUM ('student', 'faculty', 'vendor', 'resident', 'admin');
EXCEPTION WHEN duplicate_object THEN NULL: END $$;
DO $$ BEGIN
    CREATE TYPE listing_type as ENUM ('product', 'service');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    CREATE TYPE listing_status as ENUM ('active', 'sold', 'hidden');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    CREATE TYPE booking_status as ENUM ('pending', 'accepted', 'declined', 'cancelled', 'completed');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    CREATE TYPE post_status as ENUM ('active', 'flagged', 'removed');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS users (
    id  SERIAL  PRIMARY KEY,
    full_name   VARCHAR(120) NOT NULL,
    email       CITEXT       NOT NULL UNIQUE,
    password_hash   VARCHAR(255)    NOT NULL,
    role            user_role       NOT NULL DEFAULT 'student',
    is_verified     BOOLEAN         NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS categories (
    id          SERIAL  PRIMARY KEY,
    name        VARCHAR(60) NOT NULL
);

CREATE TABLE IF NOT EXISTS locations (
    id      SERIAL      PRIMARY KEY,
    name    VARCHAR(80) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS listings (
    id  SERIAL  PRIMARY KEY,
    owner_id        INTEGER         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category_id     INTEGER         NOT NULL REFERENCES categories(id),
    location_id     INTEGER         REFERENCES locations(id),
    type            listing_type    NOT NULL DEFAULT 'product',
    title           VARCHAR(120)    NOT NULL,
    description     TEXT            NOT NULL DEFAULT '',
    price           NUMERIC(10, 2)  NOT NULL CHECK (price >= 0),
    price_unit      VARCHAR(20)     NOT NULL DEFAULT '',
    condition       VARCHAR(30)     NOT NULL DEFAULT '',
    icon            VARCHAR(8)      NOT NULL DEFAULT '',
    status          listing_status  NOT NULL DEFAULT 'active'
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_listings_category ON listings(category_id);
CREATE INDEX IF NOT EXISTS ix_listings_location ON listings(location_id);
CREATE INDEX IF NOT EXISTS ix_listings_owner ON listings(owner_id);
CREATE INDEX IF NOT EXISTS ix_listings_status ON listings(status);

CREATE TABLE IF NOT EXISTS saved_listings (
    user_id     INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    listing_id  INTEGER     NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, listing_id)
);

CREATE TABLE IF  NOT EXISTS bookings (
    id      SERIAL PRIMARY KEY,
    listing_id      INTEGER     NOT NULL REFERENCES listings(id) ON CASCADE,
    requester_id    INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    preferred_date  DATE, 
    preferred_time  TIME,
    notes           TEXT        NOT NULL DEFAULT '',
    status          booking_status  NOT NULL DEFAULT 'pending',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_bookings_listing ON bookings(listing_id);
CREATE INDEX IF NOT EXISTS ix_bookings_requester ON bookings(requester_id);

CREATE TABLE IF NOT EXISTS conversations (
    id      SERIAL PRIMARY KEY,
    listing_id      INTEGER     REFERENCES listings(id) ON DELETE SET NULL,
    user_a_id       INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE, 
    user_b_id       INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (user_a_id <> user_b_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_conversation_pair
ON conversations (COALESCE(listing_id, 0), LEAST (user_a_id, user_b_id), GREATEST(user_a_id, user_b_id));

CREATE TABLE IF NOT EXISTS messages (
    INDEX       SERIAL      PRIMARY KEY,
    conversation_id         INTEGER         NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    sender_id               INTEGER         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body                    TEXT            NOT NULL CHECK (length(trim(body)) > 0),
    is_read                 BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX IF  NOT EXISTS ix_reviews_listing ON reviews(listing_id);

CREATE TABLE IF NOT EXISTS post_flags (
    id       SERIAL         PRIMARY KEY,
    post_id                 INTEGER         NOT NULL REFERENCES bulletin_post(id) ON DELETE CASCADE,
    reporter_id             INTEGER         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reason                  VARCHAR(265)    NOT NULL DEFAULT '',
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT now(),
    UNIQUE (post_id, reporter_id)
);


-- REFERENCE DATA --

INSERT INTO categories(name, icon) VALUES
('Textbooks'), ('Electronics'), ('Tutoring'), ('Services')
ON CONFLICT (name) DO NOTHING;

INSERT INTO locations(name) VALUES 
('Bellville Campus'), ('District Six Campus'), ('Mowbray Campus'), ('Granger Bay Campus'), ('Wellington Campus')
ON CONFLICT (name) DO NOTHING