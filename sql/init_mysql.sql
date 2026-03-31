CREATE DATABASE IF NOT EXISTS chilemei DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE chilemei;

CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    wechat_openid VARCHAR(100) UNIQUE NULL,
    wechat_unionid VARCHAR(100) UNIQUE NULL,
    username VARCHAR(50) NULL UNIQUE,
    email VARCHAR(120) NULL UNIQUE,
    password_hash VARCHAR(255) NULL,
    nickname VARCHAR(50) NOT NULL,
    bio VARCHAR(255) NULL,
    avatar_url VARCHAR(255) NULL,
    is_private TINYINT(1) NOT NULL DEFAULT 0,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS food (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(120) NOT NULL,
    location VARCHAR(255) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    image_dir VARCHAR(255) NULL COMMENT 'Relative media dir, e.g. food/12',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_food_name_location (name, location),
    INDEX idx_food_name (name),
    INDEX idx_food_location (location)
);

CREATE TABLE IF NOT EXISTS food_records (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    food_id BIGINT NOT NULL,
    sentiment ENUM('like', 'dislike') NOT NULL,
    rating_level TINYINT NOT NULL COMMENT '5:顶级, 4:夯, 3:人上人, 2:NPC, 1:拉完了',
    review_text TEXT NULL,
    image_filename VARCHAR(255) NULL COMMENT 'Only stores filename; final URL is built from food.image_dir + filename',
    uploaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_food_records_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT fk_food_records_food FOREIGN KEY (food_id) REFERENCES food(id) ON DELETE RESTRICT,
    INDEX idx_food_records_user_id (user_id),
    INDEX idx_food_records_food_id (food_id),
    INDEX idx_food_records_uploaded_at (uploaded_at),
    INDEX idx_user_food_time (user_id, food_id, uploaded_at)
);

CREATE TABLE IF NOT EXISTS user_food_stats (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    food_id BIGINT NOT NULL,
    like_count INT NOT NULL DEFAULT 0,
    dislike_count INT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_user_food_stats_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT fk_user_food_stats_food FOREIGN KEY (food_id) REFERENCES food(id) ON DELETE RESTRICT,
    UNIQUE KEY uk_user_food_stats_user_food (user_id, food_id),
    INDEX idx_user_food_stats_user_id (user_id),
    INDEX idx_user_food_stats_food_id (food_id)
);

CREATE TABLE IF NOT EXISTS comments (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    food_record_id BIGINT NOT NULL,
    content TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_comments_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT fk_comments_record FOREIGN KEY (food_record_id) REFERENCES food_records(id) ON DELETE CASCADE,
    INDEX idx_comments_user_id (user_id),
    INDEX idx_comments_record_id (food_record_id)
);
