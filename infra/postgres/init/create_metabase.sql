-- Update the password to match MB_DB_PASS in metabase.env
CREATE USER metabase WITH PASSWORD 'Black17998~';
CREATE DATABASE metabase OWNER metabase;
