-- Update the password to match MB_DB_PASS in metabase.env
CREATE USER metabase WITH PASSWORD 'CHANGE_ME';
CREATE DATABASE metabase OWNER metabase;
