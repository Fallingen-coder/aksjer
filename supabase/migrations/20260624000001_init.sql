-- Kurshistorikk
CREATE TABLE IF NOT EXISTS prices (
    ticker      TEXT NOT NULL,
    date        DATE NOT NULL,
    open        NUMERIC,
    high        NUMERIC,
    low         NUMERIC,
    close       NUMERIC,
    volume      BIGINT,
    PRIMARY KEY (ticker, date)
);

-- Papirportefølje
CREATE TABLE IF NOT EXISTS portfolio (
    ticker      TEXT PRIMARY KEY,
    shares      NUMERIC NOT NULL DEFAULT 0,
    avg_cost    NUMERIC NOT NULL DEFAULT 0
);

-- Transaksjonslogg
CREATE TABLE IF NOT EXISTS transactions (
    id          BIGSERIAL PRIMARY KEY,
    ts          TIMESTAMPTZ NOT NULL DEFAULT now(),
    ticker      TEXT NOT NULL,
    action      TEXT NOT NULL CHECK(action IN ('BUY','SELL')),
    shares      NUMERIC NOT NULL,
    price       NUMERIC NOT NULL,
    reason      TEXT
);

-- Nyheter per ticker
CREATE TABLE IF NOT EXISTS news (
    id          BIGSERIAL PRIMARY KEY,
    ticker      TEXT NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    title       TEXT NOT NULL,
    url         TEXT,
    summary     TEXT,
    source      TEXT
);

-- AI-signaler
CREATE TABLE IF NOT EXISTS signals (
    id          BIGSERIAL PRIMARY KEY,
    ts          TIMESTAMPTZ NOT NULL DEFAULT now(),
    ticker      TEXT NOT NULL,
    signal      TEXT NOT NULL CHECK(signal IN ('BUY','SELL','HOLD')),
    confidence  NUMERIC,
    reasoning   TEXT
);

-- Kontantbeholdning (testpott)
CREATE TABLE IF NOT EXISTS cash (
    id          INT PRIMARY KEY DEFAULT 1 CHECK(id = 1),
    amount      NUMERIC NOT NULL
);

INSERT INTO cash (id, amount) VALUES (1, 100000) ON CONFLICT DO NOTHING;
