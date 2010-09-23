
CREATE TABLE usersip_tmp AS SELECT * FROM usersip;

DROP TABLE usersip;
CREATE TABLE usersip (
 id integer unsigned,
 name varchar(40) NOT NULL,
 type varchar(6) NOT NULL,
 username varchar(80),
 secret varchar(80) NOT NULL DEFAULT '',
 md5secret varchar(32) NOT NULL DEFAULT '',
 context varchar(39),
 language varchar(20),
 accountcode varchar(20),
 amaflags varchar(13) NOT NULL DEFAULT 'default',
 allowtransfer tinyint(1),
 fromuser varchar(80),
 fromdomain varchar(255),
 mailbox varchar(80),
 subscribemwi tinyint(1) NOT NULL DEFAULT 1,
 buggymwi tinyint(1),
 "call-limit" tinyint unsigned NOT NULL DEFAULT 0,
 callerid varchar(160),
 fullname varchar(80),
 cid_number varchar(80),
 maxcallbitrate smallint unsigned,
 insecure varchar(11),
 nat varchar(5),
 canreinvite varchar(12),
 promiscredir tinyint(1),
 usereqphone tinyint(1),
 videosupport tinyint(1),
 trustrpid tinyint(1),
 sendrpid tinyint(1),
 allowsubscribe tinyint(1),
 allowoverlap tinyint(1),
 dtmfmode varchar(7),
 rfc2833compensate tinyint(1),
 qualify varchar(4),
 g726nonstandard tinyint(1),
 disallow varchar(100),
 allow varchar(100),
 autoframing tinyint(1),
 mohinterpret varchar(80),
 mohsuggest varchar(80),
 useclientcode tinyint(1),
 progressinband varchar(5),
 t38pt_udptl tinyint(1),
 t38pt_rtp tinyint(1),
 t38pt_tcp tinyint(1),
 t38pt_usertpsource tinyint(1),
 rtptimeout tinyint unsigned,
 rtpholdtimeout tinyint unsigned,
 rtpkeepalive tinyint unsigned,
 deny varchar(31),
 permit varchar(31),
 defaultip varchar(255),
 callgroup varchar(180),
 pickupgroup varchar(180),
 setvar varchar(100) NOT NULL DEFAULT '',
 host varchar(255) NOT NULL DEFAULT 'dynamic',
 port smallint unsigned,
 regexten varchar(80),
 subscribecontext varchar(80),
 fullcontact varchar(255),
 vmexten varchar(40),
 callingpres tinyint(1),
 ipaddr varchar(255) NOT NULL DEFAULT '',
 regseconds integer unsigned NOT NULL DEFAULT 0,
 regserver varchar(20),
 lastms varchar(15) NOT NULL DEFAULT '',
 protocol char(3) NOT NULL DEFAULT 'sip',
 category varchar(5) NOT NULL,
 outboundproxy varchar(1024),
 commented tinyint(1) NOT NULL DEFAULT 0,
 PRIMARY KEY(id)
);

CREATE INDEX usersip__idx__mailbox      ON usersip(mailbox);
CREATE INDEX usersip__idx__protocol     ON usersip(protocol);
CREATE INDEX usersip__idx__category     ON usersip(category);
CREATE INDEX usersip__idx__commented    ON usersip(commented);
CREATE INDEX usersip__idx__host_port    ON usersip(host,port);
CREATE INDEX usersip__idx__ipaddr_port  ON usersip(ipaddr,port);
CREATE INDEX usersip__idx__lastms       ON usersip(lastms);
CREATE UNIQUE INDEX usersip__uidx__name ON usersip(name);

INSERT INTO usersip SELECT
 id,
 name,
 type,
 username,
 secret,
 md5secret,
 context,
 language,
 accountcode,
 amaflags,
 allowtransfer,
 fromuser,
 fromdomain,
 mailbox,
 subscribemwi,
 buggymwi,
 "call-limit",
 callerid,
 fullname,
 cid_number,
 maxcallbitrate,
 insecure,
 nat,
 canreinvite,
 promiscredir,
 usereqphone,
 videosupport,
 trustrpid,
 sendrpid,
 allowsubscribe,
 allowoverlap,
 dtmfmode,
 rfc2833compensate,
 qualify,
 g726nonstandard,
 disallow,
 allow,
 autoframing,
 mohinterpret,
 mohsuggest,
 useclientcode,
 progressinband,
 t38pt_udptl,
 t38pt_rtp,
 t38pt_tcp,
 t38pt_usertpsource,
 rtptimeout,
 rtpholdtimeout,
 rtpkeepalive,
 deny,
 permit,
 defaultip,
 callgroup,
 pickupgroup,
 setvar,
 host,
 port,
 regexten,
 subscribecontext,
 fullcontact,
 vmexten,
 callingpres,
 ipaddr,
 regseconds,
 regserver,
 lastms,
 protocol,
 category,
 NULL,
 commented
FROM usersip_tmp;
DROP TABLE usersip_tmp;

UPDATE OR IGNORE usersip SET
  language   = 'fr_FR'
WHERE
  language != 'en' AND
  language NOT NULL;

UPDATE OR IGNORE usersip SET
  language  = 'en_US'
WHERE
  language  = 'en';

