-- =========================================================
-- TRIPA / SHERPA MariaDB Table Creation Script
-- 지금까지 구현된 기능 기준
-- =========================================================

SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS pay;
DROP TABLE IF EXISTS schedule_places;
DROP TABLE IF EXISTS travel_category;
DROP TABLE IF EXISTS travel_day_plan;
DROP TABLE IF EXISTS schedule;
DROP TABLE IF EXISTS place;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS travel;
DROP TABLE IF EXISTS member;

SET FOREIGN_KEY_CHECKS = 1;


-- =========================================================
-- MEMBER
-- =========================================================

CREATE TABLE member (

    M_ID INT NOT NULL AUTO_INCREMENT,
    ID VARCHAR(100) NOT NULL,
    PWD VARCHAR(255) NOT NULL,
    NICKNAME VARCHAR(30) NOT NULL,
    NAME VARCHAR(30) NOT NULL,

    CONSTRAINT MEMBER_PK
        PRIMARY KEY (M_ID),

    CONSTRAINT UQ_MEMBER_ID
        UNIQUE (ID)

) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;


-- =========================================================
-- TRAVEL
--
-- T_BUDGET          : 여행 총 예산
-- START_*           : 첫날 출발지 / 좌표
-- ACCOMMODATION_*   : 숙소 / 좌표
-- CHECKIN_TIME      : 첫날 체크인 시간
-- =========================================================

CREATE TABLE travel (

    T_ID INT NOT NULL AUTO_INCREMENT,
    M_ID INT NOT NULL,

    T_DAY DATE,
    T_PLACE VARCHAR(100) NOT NULL,
    T_TITLE VARCHAR(100) NOT NULL,
    T_WAY VARCHAR(30),

    T_START DATE NOT NULL,
    T_END DATE NOT NULL,

    T_BUDGET INT NOT NULL DEFAULT 100000,

    START_PLACE VARCHAR(200),
    START_ADDR VARCHAR(255),
    START_LAT DECIMAL(10,7),
    START_LON DECIMAL(10,7),
    START_TIME TIME,

    ACCOMMODATION VARCHAR(200),
    ACCOMMODATION_LAT DECIMAL(10,7),
    ACCOMMODATION_LON DECIMAL(10,7),

    CHECKIN_TIME TIME,

    CONSTRAINT TRAVEL_PK
        PRIMARY KEY (T_ID),

    CONSTRAINT TRAVEL_MEMBER_FK
        FOREIGN KEY (M_ID)
        REFERENCES member(M_ID)
        ON DELETE CASCADE

) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

-- =========================================================
-- TRAVEL_DAY_PLAN
--
-- 여행 날짜별 숙소 / 출발시간 / 숙소 도착시간
--
-- PLAN_DATE          : 여행 날짜
-- ACCOMMODATION_*    : 해당 날짜 일정 종료 숙소
-- ARRIVAL_TIME       : 해당 날짜 숙소 도착 목표 시간
-- DEPARTURE_TIME     : 해당 날짜 일정 출발 시간
--
-- DAY 1 출발시간은 TRAVEL.START_TIME 사용
-- DAY 2 이후는 DEPARTURE_TIME 사용
-- 마지막 날은 숙소 정보가 NULL일 수 있음
-- =========================================================

CREATE TABLE travel_day_plan (

    TDP_ID INT NOT NULL AUTO_INCREMENT,
    T_ID INT NOT NULL,

    PLAN_DATE DATE NOT NULL,

    ACCOMMODATION_NAME VARCHAR(200),
    ACCOMMODATION_ADDR VARCHAR(255),

    ACCOMMODATION_LAT DECIMAL(10,7),
    ACCOMMODATION_LON DECIMAL(10,7),

    ARRIVAL_TIME TIME,
    DEPARTURE_TIME TIME,

    CONSTRAINT TRAVEL_DAY_PLAN_PK
        PRIMARY KEY (TDP_ID),

    CONSTRAINT TRAVEL_DAY_PLAN_TRAVEL_FK
        FOREIGN KEY (T_ID)
        REFERENCES travel(T_ID)
        ON DELETE CASCADE,

    CONSTRAINT UQ_TRAVEL_DAY_PLAN
        UNIQUE (T_ID, PLAN_DATE)

) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

-- =========================================================
-- PLACE
--
-- P_IMAGE : 장소 검색 결과 이미지 URL 저장
-- =========================================================

CREATE TABLE place (

    P_ID INT NOT NULL AUTO_INCREMENT,
    T_ID INT NOT NULL,

    P_NAME VARCHAR(100) NOT NULL,
    P_ADDR VARCHAR(255),

    P_LAT DECIMAL(10,7),
    P_LON DECIMAL(10,7),

    P_KIND VARCHAR(100),
    P_IMAGE TEXT,

    CONSTRAINT PLACE_PK
        PRIMARY KEY (P_ID),

    CONSTRAINT PLACE_TRAVEL_FK
        FOREIGN KEY (T_ID)
        REFERENCES travel(T_ID)
        ON DELETE CASCADE

) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;


-- =========================================================
-- CATEGORIES
--
-- PLACE와 직접 연결하지 않음.
-- 여행과의 관계는 TRAVEL_CATEGORY가 담당.
-- =========================================================

CREATE TABLE categories (

    C_ID INT NOT NULL AUTO_INCREMENT,
    C_NAME VARCHAR(100) NOT NULL,

    CONSTRAINT CATEGORIES_PK
        PRIMARY KEY (C_ID),

    CONSTRAINT UQ_CATEGORY_NAME
        UNIQUE (C_NAME)

) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;


-- =========================================================
-- TRAVEL_CATEGORY
--
-- 여행 하나에 여러 개의 여행 컨셉을 선택하기 위한 연결 테이블
-- TRAVEL N : M CATEGORIES
-- =========================================================

CREATE TABLE travel_category (

    TC_ID INT NOT NULL AUTO_INCREMENT,
    T_ID INT NOT NULL,
    C_ID INT NOT NULL,

    CONSTRAINT TRAVEL_CATEGORY_PK
        PRIMARY KEY (TC_ID),

    CONSTRAINT TRAVEL_CATEGORY_TRAVEL_FK
        FOREIGN KEY (T_ID)
        REFERENCES travel(T_ID)
        ON DELETE CASCADE,

    CONSTRAINT TRAVEL_CATEGORY_CATEGORY_FK
        FOREIGN KEY (C_ID)
        REFERENCES categories(C_ID)
        ON DELETE CASCADE,

    CONSTRAINT UQ_TRAVEL_CATEGORY
        UNIQUE (T_ID, C_ID)

) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;


-- =========================================================
-- SCHEDULE
--
-- 여행 날짜별 DAY 일정
-- 한 여행에서 동일 날짜의 Schedule 중복 방지
-- =========================================================

CREATE TABLE schedule (

    S_ID INT NOT NULL AUTO_INCREMENT,
    S_DAY DATE NOT NULL,
    T_ID INT NOT NULL,

    CONSTRAINT SCHEDULE_PK
        PRIMARY KEY (S_ID),

    CONSTRAINT SCHEDULE_TRAVEL_FK
        FOREIGN KEY (T_ID)
        REFERENCES travel(T_ID)
        ON DELETE CASCADE,

    CONSTRAINT UQ_SCHEDULE_TRAVEL_DAY
        UNIQUE (T_ID, S_DAY)

) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;


-- =========================================================
-- SCHEDULE_PLACES
--
-- VISIT_ORDER : DAY 안에서 방문 순서
-- STAY_TIME   : 체류 시간(분)
-- ARRIVAL_TIME: 도착 시간
-- START_TIME  : 해당 장소에서 출발하는 시간
-- TRAVEL_TIME : 이전 장소에서 현재 장소까지 이동 시간(분)
-- =========================================================

CREATE TABLE schedule_places (

    SP_ID INT NOT NULL AUTO_INCREMENT,
    S_ID INT NOT NULL,
    P_ID INT NOT NULL,

    VISIT_ORDER INT NOT NULL,

    STAY_TIME INT,
    ARRIVAL_TIME TIME,
    START_TIME TIME,
    TRAVEL_TIME INT,

    CONSTRAINT SCHEDULE_PLACES_PK
        PRIMARY KEY (SP_ID),

    CONSTRAINT SCHEDULE_PLACES_SCHEDULE_FK
        FOREIGN KEY (S_ID)
        REFERENCES schedule(S_ID)
        ON DELETE CASCADE,

    CONSTRAINT SCHEDULE_PLACES_PLACE_FK
        FOREIGN KEY (P_ID)
        REFERENCES place(P_ID)
        ON DELETE CASCADE

) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;


-- =========================================================
-- PAY
--
-- P_ID는 NULL 가능:
-- 특정 장소와 연결되지 않은 여행 비용도 저장 가능
-- =========================================================

CREATE TABLE pay (

    PAY_ID INT NOT NULL AUTO_INCREMENT,
    PAY_CONTENT VARCHAR(255),
    PAY_PAY INT NOT NULL DEFAULT 0,

    S_ID INT NOT NULL,
    P_ID INT,

    CONSTRAINT PAY_PK
        PRIMARY KEY (PAY_ID),

    CONSTRAINT PAY_SCHEDULE_FK
        FOREIGN KEY (S_ID)
        REFERENCES schedule(S_ID)
        ON DELETE CASCADE,

    CONSTRAINT PAY_PLACE_FK
        FOREIGN KEY (P_ID)
        REFERENCES place(P_ID)
        ON DELETE SET NULL

) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;


-- =========================================================
-- 기본 여행 카테고리
-- =========================================================

INSERT INTO categories (C_NAME)
VALUES
    ('쇼핑'),
    ('역사'),
    ('전통문화'),
    ('랜드마크'),
    ('카페'),
    ('공원'),
    ('음식'),
    ('자연'),
    ('바다');


-- =========================================================
-- 생성 확인
-- =========================================================

SHOW TABLES;
