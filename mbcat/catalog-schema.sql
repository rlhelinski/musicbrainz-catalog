-- This file contains the schema to represent user data
CREATE TABLE releases(
    id TEXT PRIMARY KEY,
    meta BLOB,
    sortstring TEXT,
    artist TEXT,
    title TEXT,
    date TEXT,
    country TEXT,
    label TEXT,
    catno TEXT,
    barcode TEXT,
    asin TEXT,
    format TEXT,
    sortformat TEXT,
    metatime FLOAT,
    count INT DEFAULT 1,
    comment TEXT,
    rating INT DEFAULT 0);

CREATE TABLE added_dates(
    date FLOAT,
    release TEXT);

CREATE TABLE listened_dates(
    date FLOAT,
    release TEXT,
    FOREIGN KEY(release) REFERENCES releases(id)
    ON UPDATE CASCADE ON DELETE CASCADE);

CREATE TABLE purchases (
    date FLOAT,
    price FLOAT,
    vendor TEXT,
    release TEXT,
    FOREIGN KEY(release) REFERENCES releases(id)
    ON DELETE CASCADE ON UPDATE CASCADE);

-- checkout, checkin (lent out, returned) tables
CREATE TABLE checkout_events (
    borrower TEXT,
    date FLOAT,
    release TEXT,
    FOREIGN KEY(release) REFERENCES releases(id)
    ON DELETE CASCADE ON UPDATE CASCADE);

CREATE TABLE checkin_events (
    date FLOAT,
    release TEXT,
    FOREIGN KEY(release) REFERENCES releases(id)
    ON DELETE CASCADE ON UPDATE CASCADE);

-- Tables for referencing digital copies
CREATE TABLE digital_roots (
    id TEXT PRIMARY KEY);

CREATE TABLE digital_root_locals (
    root_id TEXT,
    root_path TEXT,
    host_id INT,
    host_name TEXT,
    PRIMARY KEY (root_id, host_id),
    FOREIGN KEY (root_id) REFERENCES digital_roots(id)
        ON DELETE CASCADE ON UPDATE CASCADE);

CREATE TABLE digital (
    root TEXT,
    path TEXT,
    release TEXT,
    format TEXT,
    PRIMARY KEY (root, path),
    FOREIGN KEY(root) REFERENCES digital_roots(id)
    ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY(release) REFERENCES releases(id)
    ON DELETE CASCADE ON UPDATE CASCADE);

-- Indexes for speed (it's all about performance...)
CREATE UNIQUE INDEX release_id ON releases(id);
CREATE INDEX release_sortstring ON releases(sortstring);
CREATE INDEX release_catno ON releases(catno);
CREATE INDEX release_barcode ON releases(barcode);
CREATE INDEX release_asin ON releases(asin);
