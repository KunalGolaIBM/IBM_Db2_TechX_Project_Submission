-- =============================================================================
-- IBM Db2 Relational Schema DDL
-- Project: AI-Powered Recipe & Ingredient Waste Optimizer
-- Target: IBM Db2 Community Edition (Docker) / Db2 on Cloud
-- =============================================================================

-- 1. Master Ingredient Catalogue
CREATE TABLE INGREDIENTS (
    ingredient_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    canonical_name VARCHAR(100) NOT NULL UNIQUE,
    category VARCHAR(50) NOT NULL,
    default_unit VARCHAR(20),
    aliases VARCHAR(500),
    shelf_life_days INT DEFAULT 7,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Household Inventory (Pantry / Fridge Stock)
CREATE TABLE USER_INVENTORY (
    inventory_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    household_id VARCHAR(50) NOT NULL,
    ingredient_id INT NOT NULL,
    quantity DECIMAL(10,2) NOT NULL,
    unit VARCHAR(20) NOT NULL,
    purchase_date DATE,
    expiry_date DATE,
    storage_location VARCHAR(30) DEFAULT 'fridge',
    status VARCHAR(20) DEFAULT 'available',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_inv_ingredient FOREIGN KEY (ingredient_id) REFERENCES INGREDIENTS(ingredient_id) ON DELETE CASCADE,
    CONSTRAINT chk_inv_qty CHECK (quantity >= 0)
);

-- 3. Recipe Master Catalogue
CREATE TABLE RECIPES (
    recipe_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    description VARCHAR(1000),
    cuisine VARCHAR(50),
    prep_minutes INT DEFAULT 15,
    cook_minutes INT DEFAULT 20,
    servings INT DEFAULT 2,
    instructions_json CLOB NOT NULL,
    dietary_tags VARCHAR(250),
    source_name VARCHAR(100) DEFAULT 'Curated Home Kitchen',
    source_url VARCHAR(255),
    license_notes VARCHAR(255) DEFAULT 'CC-BY-4.0',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Recipe Ingredient Mapping
CREATE TABLE RECIPE_INGREDIENTS (
    recipe_id INT NOT NULL,
    ingredient_id INT NOT NULL,
    quantity DECIMAL(10,2),
    unit VARCHAR(20),
    is_optional SMALLINT DEFAULT 0,
    PRIMARY KEY (recipe_id, ingredient_id),
    CONSTRAINT fk_ri_recipe FOREIGN KEY (recipe_id) REFERENCES RECIPES(recipe_id) ON DELETE CASCADE,
    CONSTRAINT fk_ri_ingredient FOREIGN KEY (ingredient_id) REFERENCES INGREDIENTS(ingredient_id) ON DELETE CASCADE
);

-- 5. Recipe Embeddings Store
CREATE TABLE RECIPE_EMBEDDINGS (
    recipe_id INT NOT NULL PRIMARY KEY,
    embedding_vector CLOB NOT NULL,
    embedding_model VARCHAR(100) NOT NULL,
    embedding_dimension INT NOT NULL,
    embedded_text_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_re_recipe FOREIGN KEY (recipe_id) REFERENCES RECIPES(recipe_id) ON DELETE CASCADE
);

-- 6. Cooking Confirmation & Consumption History
CREATE TABLE COOKING_HISTORY (
    history_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    household_id VARCHAR(50) NOT NULL,
    recipe_id INT NOT NULL,
    servings_prepared INT DEFAULT 2,
    cooked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ch_recipe FOREIGN KEY (recipe_id) REFERENCES RECIPES(recipe_id)
);

-- 7. Inventory Audit Event Ledger
CREATE TABLE INVENTORY_EVENTS (
    event_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    household_id VARCHAR(50) NOT NULL,
    ingredient_id INT NOT NULL,
    event_type VARCHAR(30) NOT NULL,
    quantity_delta DECIMAL(10,2) NOT NULL,
    unit VARCHAR(20) NOT NULL,
    reason VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ie_ingredient FOREIGN KEY (ingredient_id) REFERENCES INGREDIENTS(ingredient_id)
);

-- Indexes for optimal querying and joining
CREATE INDEX idx_inv_household ON USER_INVENTORY(household_id, status);
CREATE INDEX idx_inv_expiry ON USER_INVENTORY(expiry_date);
CREATE INDEX idx_ri_recipe ON RECIPE_INGREDIENTS(recipe_id);
CREATE INDEX idx_ri_ingredient ON RECIPE_INGREDIENTS(ingredient_id);
CREATE INDEX idx_ie_household ON INVENTORY_EVENTS(household_id);
