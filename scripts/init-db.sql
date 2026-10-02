-- Database initialization script
-- This runs when PostgreSQL container starts

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create database user if not exists (handled by POSTGRES_USER env var)
-- Additional setup can be added here if needed