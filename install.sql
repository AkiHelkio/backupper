drop table backup;
drop table folder;
PRAGMA foreign_keys=on;

create table backup(
    backup_id    integer primary key,
    backup_name  varchar,
    backup_sizemb  integer,
    backup_date  date
);
create table folder(
    folder_id    integer,
    folder_name  varchar,
    folder_sizemb  integer,
    folder_backupid  integer,
    -- Add reference to main table. Each backup consists of multiple folders
    constraint fk_backup
      foreign key(folder_backupid)
      references backup(backup_id)
      on delete cascade
);
-- tests:
insert into backup
(backup_id, backup_name, backup_sizemb, backup_date)
values
(1,'dude.tar.gz',32131,'2017-01-01'),
(2,'dude.tar.gz',33345,'2017-01-02')
;

insert into folder
(folder_id, folder_name, folder_sizemb, folder_backupid)
values
(1, 'asiakirjat', 12000, 1),
(2, 'tärkeät', 10031, 1),
(3, 'lataukset', 10100, 1),
(4, 'asiakirjat', 12000, 2),
(5, 'tärkeät', 10031, 2),
(6, 'lataukset', 10100, 2)
;

select * from backup;
select * from folder;
delete from backup where backup_id = 1;
select * from backup;
select * from folder;


