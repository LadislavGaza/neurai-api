CREATE TABLE example (
    id SERIAL PRIMARY KEY NOT NULL,
    name VARCHAR NOT NULL
);

INSERT INTO example (name) VALUES ('Hello world');
