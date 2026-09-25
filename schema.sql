-- Run in SSMS as an admin. Replace the two passwords before running.
CREATE DATABASE AIJobMarket;
GO
USE AIJobMarket;
GO

CREATE TABLE dbo.jobs (
    job_id               INT IDENTITY(1,1) PRIMARY KEY,
    job_title            NVARCHAR(200) NOT NULL,
    role_category        NVARCHAR(50)  NULL,
    company              NVARCHAR(200) NULL,
    location             NVARCHAR(100) NULL,
    work_mode            NVARCHAR(20)  NULL CHECK (work_mode IN ('remote','hybrid','onsite')),
    seniority            NVARCHAR(20)  NULL CHECK (seniority IN ('junior','mid','senior')),
    experience_years_min INT NULL,
    experience_years_max INT NULL,
    language_required    NVARCHAR(20)  NULL,
    salary_min_mxn       INT NULL,
    salary_max_mxn       INT NULL,
    description          NVARCHAR(MAX) NOT NULL,
    submitted_at         DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);

CREATE TABLE dbo.job_skills (
    job_id INT NOT NULL REFERENCES dbo.jobs(job_id) ON DELETE CASCADE,
    skill  NVARCHAR(100) NOT NULL,
    PRIMARY KEY (job_id, skill)
);
GO

-- Chatbot: read only
CREATE LOGIN rag_reader WITH PASSWORD = 'CHANGE-ME-reader';
CREATE USER rag_reader FOR LOGIN rag_reader;
GRANT SELECT ON dbo.jobs TO rag_reader;
GRANT SELECT ON dbo.job_skills TO rag_reader;

-- n8n pipeline: insert only
CREATE LOGIN n8n_writer WITH PASSWORD = 'CHANGE-ME-writer';
CREATE USER n8n_writer FOR LOGIN n8n_writer;
GRANT SELECT, INSERT ON dbo.jobs TO n8n_writer;
GRANT SELECT, INSERT ON dbo.job_skills TO n8n_writer;
