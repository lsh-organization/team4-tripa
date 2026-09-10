SET FOREIGN_KEY_CHECKS = 0;

drop table if exists TRAVEL;
drop table if exists MEMBER;
drop table if exists SCHEDULE;
drop table if exists PLACE;
drop table if exists PAY;
drop table if exists CATEGORIES;
drop table if exists SCHEDULE_PLACES;

SET FOREIGN_KEY_CHECKS = 1;


create table MEMBER(

    M_ID int not null auto_increment,
    ID varchar(30),
    PWD varchar(30),
    NICKNAME varchar(30),
    NAME varchar(30),

    constraint MEMBER_PK primary key(M_ID)

);


create table TRAVEL(

    T_ID INT not null auto_increment,
    M_ID int,
    T_DAY DATE,
    T_PLACE VARCHAR(100),
    T_TITLE VARCHAR(100),
    T_WAY VARCHAR(30),
    T_START DATE,
    T_END DATE,

    constraint TRAVEL_PK primary key(T_ID)

);

alter table TRAVEL
add constraint TRAVEL_MEMBER_FK
foreign key(M_ID)
references MEMBER(M_ID)
on delete cascade;


create table PLACE(

    P_ID INT not null auto_increment,
    T_ID INT,
    P_NAME VARCHAR(100),
    P_ADDR VARCHAR(100),
    P_LAT DECIMAL(10,7),
    P_LON DECIMAL(10,7),
    P_KIND VARCHAR(100),

    constraint PLACE_PK primary key(P_ID)

);

alter table PLACE
add constraint PLACE_TRAVEL_FK
foreign key(T_ID)
references TRAVEL(T_ID)
on delete cascade;


-- =========================
-- 일정 테이블
-- =========================

create table SCHEDULE(

    S_ID INT not null auto_increment,
    S_DAY DATE,
    T_ID INT,

    constraint SCHEDULE_PK primary key(S_ID)

);

alter table SCHEDULE
add constraint SCHEDULE_TRAVEL_FK
foreign key(T_ID)
references TRAVEL(T_ID)
on delete cascade;


create table PAY(

    PAY_ID INT NOT NULL auto_increment,
    PAY_CONTENT VARCHAR(100),
    PAY_PAY INT,
    S_ID INT,

    constraint PAY_PK primary key(PAY_ID)

);

alter table PAY
add constraint PAY_SCHEDULE_FK
foreign key(S_ID)
references SCHEDULE(S_ID)
on delete cascade;


create table CATEGORIES(

    C_ID INT NOT NULL auto_increment,
    C_NAME VARCHAR(100),
    P_ID INT,

    constraint CATEGORIES_PK primary key(C_ID)

);

alter table CATEGORIES
add constraint CATEGORIES_PLACE_FK
foreign key(P_ID)
references PLACE(P_ID)
on delete cascade;


-- =========================
-- 일정 장소 테이블
-- =========================

create table SCHEDULE_PLACES(

    SP_ID INT NOT NULL auto_increment,
    S_ID INT,
    P_ID INT,

    VISIT_ORDER INT,

    STAY_TIME INT,
    ARRIVAL_TIME TIME,
    START_TIME TIME,

    constraint SCHEDULE_PLACES_PK primary key(SP_ID)

);

alter table SCHEDULE_PLACES
add constraint SCHEDULE_PLACES_SCHEDULE_FK
foreign key(S_ID)
references SCHEDULE(S_ID)
on delete cascade;


alter table SCHEDULE_PLACES
add constraint SCHEDULE_PLACES_PLACE_FK
foreign key(P_ID)
references PLACE(P_ID)
on delete cascade;