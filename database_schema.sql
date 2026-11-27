-- CORA creates these tables automatically. This file is provided for inspection/reference.
CREATE TABLE IF NOT EXISTS memories (id BIGSERIAL PRIMARY KEY, content TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW(), category TEXT NOT NULL DEFAULT 'general', updated_at TIMESTAMPTZ);
CREATE TABLE IF NOT EXISTS conversation_history (id BIGSERIAL PRIMARY KEY, role TEXT NOT NULL CHECK(role IN ('user','assistant')), content TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW());
CREATE TABLE IF NOT EXISTS tasks (id BIGSERIAL PRIMARY KEY, title TEXT NOT NULL, details TEXT NOT NULL DEFAULT '', due_at TEXT, completed BOOLEAN NOT NULL DEFAULT FALSE, created_at TIMESTAMPTZ DEFAULT NOW());
CREATE TABLE IF NOT EXISTS builder_projects (name TEXT PRIMARY KEY, created_at TIMESTAMPTZ DEFAULT NOW());
CREATE TABLE IF NOT EXISTS builder_files (project_name TEXT NOT NULL REFERENCES builder_projects(name) ON DELETE CASCADE, path TEXT NOT NULL, content TEXT NOT NULL, updated_at TIMESTAMPTZ DEFAULT NOW(), PRIMARY KEY(project_name, path));
CREATE TABLE IF NOT EXISTS builder_backups (id BIGSERIAL PRIMARY KEY, project_name TEXT NOT NULL, path TEXT NOT NULL, content TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW());
CREATE TABLE IF NOT EXISTS cora_notes (id BIGSERIAL PRIMARY KEY, filename TEXT NOT NULL, content TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW());
-- Phase 1: created/upgraded automatically on first use.
CREATE TABLE IF NOT EXISTS cora_agent_tasks (id BIGSERIAL PRIMARY KEY, goal TEXT NOT NULL, status TEXT NOT NULL, plan TEXT NOT NULL DEFAULT '[]', log TEXT NOT NULL DEFAULT '[]', result TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
