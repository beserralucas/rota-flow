PRAGMA foreign_keys = ON;

CREATE TABLE employees (
    employee_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    supervisor_name TEXT,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE stores (
    store_code TEXT PRIMARY KEY,
    store_name TEXT NOT NULL,
    city TEXT,
    uf TEXT,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE assignments (
    employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
    store_code TEXT NOT NULL REFERENCES stores(store_code),
    active INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (employee_id, store_code)
);

CREATE TABLE submissions (
    submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
    week_start TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('PENDENTE_APROVACAO','APROVADA','REPROVADA')),
    submitted_at TEXT NOT NULL,
    reviewed_by TEXT,
    reviewed_at TEXT,
    review_comment TEXT
);

CREATE TABLE visits (
    visit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER NOT NULL REFERENCES submissions(submission_id) ON DELETE CASCADE,
    store_code TEXT NOT NULL REFERENCES stores(store_code),
    visit_date TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(submission_id, store_code, visit_date)
);
