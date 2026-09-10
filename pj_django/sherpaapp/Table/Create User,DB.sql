mysql -u root -p

drop user if exists 'sherpa'@'localhost';
drop database if exists sherpa_schema;

create user 'sherpa'@'localhost' identified by '1234';
create database sherpa_schema;

grant all privileges on sherpa_schema.* to 'sherpa'@'localhost';
flush privileges;