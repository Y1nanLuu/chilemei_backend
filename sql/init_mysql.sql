CREATE DATABASE IF NOT EXISTS chilemei DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE chilemei;

CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    nickname VARCHAR(50) NOT NULL,
    bio VARCHAR(255) NULL,
    avatar_url VARCHAR(255) NULL,
    school_name VARCHAR(100) NULL,
    is_private TINYINT(1) NOT NULL DEFAULT 0,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS food_records (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    food_name VARCHAR(120) NOT NULL,
    dining_category ENUM('on_campus', 'off_campus') NOT NULL,
    canteen_name VARCHAR(120) NULL,
    floor VARCHAR(50) NULL,
    window_name VARCHAR(120) NULL,
    store_name VARCHAR(120) NULL,
    address VARCHAR(255) NULL,
    price DECIMAL(10, 2) NOT NULL,
    sentiment ENUM('like', 'dislike') NOT NULL,
    rating_level ENUM('夯', '顶级', '人上人', 'NPC', '拉完了') NOT NULL,
    review_text TEXT NULL,
    image_url VARCHAR(255) NULL,
    tags VARCHAR(255) NULL,
    visited_at DATE NOT NULL,
    is_public TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_food_records_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_food_records_user_id (user_id),
    INDEX idx_food_records_food_name (food_name),
    INDEX idx_food_records_visited_at (visited_at)
);

CREATE TABLE IF NOT EXISTS food_reactions (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    food_record_id BIGINT NOT NULL,
    reaction_type ENUM('like', 'dislike', 'want_to_eat') NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_food_reactions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_food_reactions_record FOREIGN KEY (food_record_id) REFERENCES food_records(id) ON DELETE CASCADE,
    UNIQUE KEY uk_food_reactions_user_record_type (user_id, food_record_id, reaction_type),
    INDEX idx_food_reactions_record_id (food_record_id)
);

CREATE TABLE IF NOT EXISTS comments (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    food_record_id BIGINT NOT NULL,
    content TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_comments_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_comments_record FOREIGN KEY (food_record_id) REFERENCES food_records(id) ON DELETE CASCADE,
    INDEX idx_comments_record_id (food_record_id)
);
