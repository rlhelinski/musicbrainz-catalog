-- This file drops and creates the tables for information derived from
-- the MusicBrainz webservice XML metadata.
DROP TABLE IF EXISTS words;
CREATE TABLE words (
    word TEXT, release TEXT,
    FOREIGN KEY(release) REFERENCES releases(id)
    ON DELETE CASCADE ON UPDATE CASCADE);

DROP TABLE IF EXISTS media;
CREATE TABLE media (
    id TEXT PRIMARY KEY,
    position INTEGER,
    format TEXT,
    release TEXT,
    FOREIGN KEY(release) REFERENCES releases(id)
    ON DELETE CASCADE ON UPDATE CASCADE);

DROP TABLE IF EXISTS medium_recordings;
CREATE TABLE medium_recordings (
    recording TEXT,
    position INTEGER,
    medium TEXT,
    FOREIGN KEY(medium) REFERENCES media(id)
    ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (recording) REFERENCES recordings(id)
    ON DELETE CASCADE ON UPDATE CASCADE);

DROP TABLE IF EXISTS trackwords;
CREATE TABLE trackwords (
    trackword TEXT, recording TEXT,
    FOREIGN KEY(recording) REFERENCES recordings(id)
    ON DELETE CASCADE ON UPDATE CASCADE);

DROP TABLE IF EXISTS discids;
CREATE TABLE discids (
    id TEXT,
    sectors INTEGER,
    medium TEXT,
    FOREIGN KEY(medium) REFERENCES media(id)
    ON DELETE CASCADE ON UPDATE CASCADE);

-- Indexes for speed (it's all about performance...)
DROP INDEX IF EXISTS word_index;
CREATE INDEX word_index ON words (word);

DROP INDEX IF EXISTS trackword_index;
CREATE INDEX trackword_index ON trackwords (trackword);

DROP INDEX IF EXISTS digital_releases;
CREATE INDEX digital_releases ON digital(release);
