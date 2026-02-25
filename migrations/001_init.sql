-- CLIENTS (TENANTS)
CREATE TABLE clients (
    id SERIAL PRIMARY KEY,

    name TEXT NOT NULL,
    address TEXT,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,

    customer_type TEXT CHECK (
        customer_type IN ('private', 'business', 'public')
    ) NOT NULL,

    subscription_plan TEXT NOT NULL,

    billing_cycle TEXT CHECK (
        billing_cycle IN ('monthly', 'yearly')
    ) NOT NULL,

    next_billing_date DATE NOT NULL,

    password_hash TEXT NOT NULL,

    is_active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- USERS
CREATE TABLE users (
    id SERIAL PRIMARY KEY,

    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,

    email TEXT NOT NULL,
    password_hash TEXT NOT NULL,

    role TEXT CHECK (
        role IN ('super_admin', 'admin', 'member')
    ) NOT NULL,

    is_active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CAMERAS
CREATE TABLE cameras (
    id SERIAL PRIMARY KEY,

    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,

    name TEXT NOT NULL,
    rtsp_url TEXT NOT NULL,

    is_active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- USER_CAMERAS (MANY-TO-MANY)
CREATE TABLE user_cameras (
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    camera_id INTEGER REFERENCES cameras(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, camera_id)
);
