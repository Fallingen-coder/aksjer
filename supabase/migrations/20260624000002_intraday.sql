CREATE TABLE IF NOT EXISTS intraday_prices (
    ticker  TEXT NOT NULL,
    ts      TIMESTAMPTZ NOT NULL,
    open    NUMERIC,
    high    NUMERIC,
    low     NUMERIC,
    close   NUMERIC,
    volume  BIGINT,
    PRIMARY KEY (ticker, ts)
);

-- Behold bare siste 7 dager for å holde tabellen liten
CREATE INDEX IF NOT EXISTS intraday_prices_ts_idx ON intraday_prices (ts DESC);
