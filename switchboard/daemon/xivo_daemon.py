#!/usr/bin/python
# $Revision$
# $Date$
#
# Authors : Thomas Bernard, Corentin Le Gall, Benoit Thinot, Guillaume Knispel
#           Proformatique
#           67, rue Voltaire
#           92800 PUTEAUX
#           (+33/0)1.41.38.99.60
#           mailto:technique@proformatique.com
#           (C) 2007 Proformatique
#

## \mainpage
# \section section_1 General description of XIVO Daemon
# The XIVO Daemon aims to monitor all the actions taking place into one or
# more Asterisk servers, in order to provide 2 basic customer facilities :
# - a monitoring switchboard;
# - a customer information popup.
#
# This is achieved thanks to 2 mechanisms :
# - one or more connections to the Asterisk Manager Interface (AMI), where
# all the events can be watched;
# - Asterisk AGI's that send informations when a call is issued.
#
# This daemon is able to manage any number of Asterisk's one might wish.
#
# \section section_2 Initializations
#
# - Fetch the phone number lists from the WEB Interface.
#
# \section section_3 Main loop
# The main loop is triggered by a select() on the file descriptors for :
# - the AMI Event sockets (AMIsocks);
# - the UI sockets (UIsock, WEBIsock);
# - the Caller Information Popup sockets (authentication, keepalive and identrequest).
#
# On reception of AMI Events, handle_ami_event() parses the messages to update
# the detailed status of the channels.
#
# For each UI connection, a list of the open UI connections is updated
# (tcpopens_sb or tcpopens_webi according to the kind of connection).
# This list is the one used to broadcast the miscellaneous updates
# (it is up to the UI clients to fetch the initial status with the "hints"
# command).
#
# \section section_6 Monitoring with AMI
#
# The AMI events are the basis for a channel-by-channel status of the phones.
#
# Many AMI events are watched for, but not all of them are handled yet.
# The most useful ones are now : Dial, Link, Hangup, Rename.
# The following ones : Newexten, Newchannel, Newcallerid, Newstate are useful when dealing
# complex situations (when there are Local/ channels and Queues for instance).
#
# \section section_8 Caller Information Popup management
#
# The daemon has 3 other listening sockets :
# - Login - TCP - (the clients connect to it to login)
# - KeepAlive - UDP - (the clients send datagram to it to inform
#                      of their current state)
# - IdentRequest - TCP - offer a service to ask for localization and
#                        state of the clients.
# we use the SocketServer "framework" to implement the "services"
# see http://docs.python.org/lib/module-SocketServer.html
#
# \section section_9 Data Structures
#
# The statuses of all the lines/channels are stored in the multidimensional array/dict "plist",
# which is an array of PhoneList.
#
# plist[astn].normal[phonenum].chann[channel] are objects of the class ChannelStatus.
# - astn is the Asterisk id
# - phonenum is the phone id (SIP/<xx>, IAX2/<yy>, ...)
# - channel is the full channel name as known by Asterisk
#
## \file xivo_daemon.py
# \brief XIVO CTI server
#
## \namespace xivo_daemon
# \brief XIVO CTI server
#

__version__ = "$Revision$ $Date$"
__revision__ = __version__.split()[1]

# debian.org modules
import csv
import string
import ConfigParser
import commands
import encodings.utf_8
import getopt
import md5
import os
import random
import re
import select
import signal
import socket
import SocketServer
import sys
import syslog
import threading
import time
import urllib
import _sre

__alphanums__ = string.uppercase + string.lowercase + string.digits

# fiche
import sendfiche

# XIVO lib-python modules initialization
import xivo.to_path
xivoconffile            = "/etc/asterisk/xivo_daemon.conf"
GETOPT_SHORTOPTS        = 'dc:'
GETOPT_LONGOPTS         = ["debug", "config="]
debug_mode = False
def config_path():
        global xivoconffile, debug_mode
        for opt, arg in getopt.getopt(
				sys.argv[1:],
				GETOPT_SHORTOPTS,
				GETOPT_LONGOPTS
			)[0]:
                if opt == "-c":
                        xivoconffile = arg
		elif opt == "-d":
			debug_mode = True
config_path()

# XIVO lib-python modules imports
import daemonize
from easyslog import *
import anysql
from BackSQL import backmysql
from BackSQL import backsqlite

# XIVO modules
import xivo_ami
import xivo_ldap
import xivo_commandsets

# the first line would be better, but the second one is useful because of freezing needs
# from CommandSets import *
import XivoSimple

DIR_TO_STRING = '>'
DIR_FROM_STRING = '<'
allowed_states = ['available', 'away', 'outtolunch', 'donotdisturb', 'berightback']

DUMMY_DIR = ''
DUMMY_RCHAN = ''
DUMMY_EXTEN = ''
DUMMY_MYNUM = ''
DUMMY_CLID = ''
DUMMY_STATE = ''

# global : userlist
# liste des champs :
#  user :             user name
#  passwd :           password
#  sessionid :        session id generated at connection
#  sessiontimestamp : last time when the client proved itself to be ALIVE :)
#  ip :               ip address of the client (current session)
#  port :             port here the client is listening.
#  state :            cf. allowed_states
# The user identifier will likely be its phone number

PIDFILE = '/var/run/xivo_daemon.pid'
# TODO: command line parameter

BUFSIZE_LARGE = 8192
BUFSIZE_UDP = 2048
BUFSIZE_ANY = 512

SUBSCRIBES_N_PER_UNIT_OF_TIME = 20
SUBSCRIBES_TIME_UNIT_IN_S     = 1

socket.setdefaulttimeout(2)
HISTSEPAR = ';'
XIVO_CLI_WEBI_HEADER = 'XIVO-CLI-WEBI'
REQUIRED_CLIENT_VERSION = 2025
XIVOVERSION = '0.3'
ITEMS_PER_PACKET = 500
USERLIST_LENGTH = 12

# TODO: get it from external configuration.
PDF2FAX = "/usr/bin/xivo_pdf2fax"

# capabilities
CAPA_CUSTINFO    = 1 <<  0
CAPA_PRESENCE    = 1 <<  1
CAPA_HISTORY     = 1 <<  2
CAPA_DIRECTORY   = 1 <<  3
CAPA_DIAL        = 1 <<  4
CAPA_FEATURES    = 1 <<  5
CAPA_PEERS       = 1 <<  6
CAPA_MESSAGE     = 1 <<  7
CAPA_SWITCHBOARD = 1 <<  8
CAPA_AGENTS      = 1 <<  9
CAPA_FAX         = 1 << 10
CAPA_DATABASE    = 1 << 11

# this list shall be defined through more options in WEB Interface
CAPA_ALMOST_ALL = CAPA_CUSTINFO | CAPA_PRESENCE | CAPA_HISTORY  | CAPA_DIRECTORY | \
                  CAPA_DIAL | CAPA_FEATURES | CAPA_PEERS | \
                  CAPA_SWITCHBOARD | CAPA_AGENTS | CAPA_FAX | CAPA_DATABASE

map_capas = {
        'customerinfo'     : CAPA_CUSTINFO,
        'presence'         : CAPA_PRESENCE,
        'history'          : CAPA_HISTORY,
        'directory'        : CAPA_DIRECTORY,
        'dial'             : CAPA_DIAL,
        'features'         : CAPA_FEATURES,
        'peers'            : CAPA_PEERS,
        'instantmessaging' : CAPA_MESSAGE,
        'switchboard'      : CAPA_SWITCHBOARD,
        'agents'           : CAPA_AGENTS,
        'fax'              : CAPA_FAX,
        'database'         : CAPA_DATABASE
        }

# TODO: get these from external configuration.
PATH_SPOOL_ASTERISK     = "/var/spool/asterisk"
PATH_SPOOL_ASTERISK_FAX = PATH_SPOOL_ASTERISK + '/' + "fax"
PATH_SPOOL_ASTERISK_TMP = PATH_SPOOL_ASTERISK + '/' + "tmp"

fullstat_heavies = {}

## \brief Logs actions to a log file, prepending them with a timestamp.
# \param string the string to log
# \return zero
# \sa log_debug
def varlog(syslogprio, string):
        if syslogprio <= SYSLOG_NOTICE:
                syslogf(syslogprio, 'xivo_daemon : ' + string)
        return 0

# reminder :
# LOG_EMERG       0
# LOG_ALERT       1
# LOG_CRIT        2
# LOG_ERR         3
# LOG_WARNING     4
# LOG_NOTICE      5
# LOG_INFO        6
# LOG_DEBUG       7


## \brief Logs all events or status updates to a log file, prepending them with a timestamp.
# \param string the string to log
# \param events log to events file
# \param updatesgui log to gui files
# \return zero
def verboselog(string, events, updatesgui):
        if debug_mode:
                if events and evtfile:
                        evtfile.write(time.strftime('%b %2d %H:%M:%S ', time.localtime()) + string + '\n')
                        evtfile.flush()
                if updatesgui and guifile:
                        guifile.write(time.strftime('%b %2d %H:%M:%S ', time.localtime()) + string + '\n')
                        guifile.flush()
        return 0


## \brief Outputs a string to stdout in no-daemon mode
# and always logs it.
# \param string the string to display and log
# \return the return code of the varlog call
# \sa varlog
def log_debug(syslogprio, string):
        if debug_mode and syslogprio <= SYSLOG_INFO:
                print '#debug# ' + string
        return varlog(syslogprio, string)


"""
Functions related to user-driven requests : history, directory, ...
These functions should not deal with CTI clients directly, however.
"""

## \brief Function that fetches the call history from a database
# \param cfg the asterisk's config
# \param techno technology (SIP/IAX/ZAP/etc...)
# \param phoneid phone id
# \param phonenum the phone number
# \param nlines the number of lines to fetch for the given phone
# \param kind kind of list (ingoing, outgoing, missed calls)
def update_history_call(cfg, techno, phoneid, phonenum, nlines, kind):
        results = []
        if cfg.cdr_db_uri == '':
                log_debug(SYSLOG_WARNING, '%s : no CDR uri defined for this asterisk - see cdr_db_uri parameter' % cfg.astid)
        else:
                try:
                        cursor = cfg.cdr_db_conn.cursor()
                        columns = ('calldate', 'clid', 'src', 'dst', 'dcontext', 'channel', 'dstchannel',
                                   'lastapp', 'lastdata', 'duration', 'billsec', 'disposition', 'amaflags',
                                   'accountcode', 'uniqueid', 'userfield')
                        likestring = '%s/%s-%%' %(techno, phoneid)
                        orderbycalldate = "ORDER BY calldate DESC LIMIT %s" % nlines
                        
                        if kind == "0": # outgoing calls (all)
                                cursor.query("SELECT ${columns} FROM cdr WHERE channel LIKE %s " + orderbycalldate,
                                             columns,
                                             (likestring,))
                        elif kind == "1": # incoming calls (answered)
                                cursor.query("SELECT ${columns} FROM cdr WHERE disposition='ANSWERED' AND dstchannel LIKE %s " + orderbycalldate,
                                             columns,
                                             (likestring,))
                        else: # missed calls (received but not answered)
                                cursor.query("SELECT ${columns} FROM cdr WHERE disposition!='ANSWERED' AND dstchannel LIKE %s " + orderbycalldate,
                                             columns,
                                             (likestring,))
                        results = cursor.fetchall()
                except Exception, exc:
                        log_debug(SYSLOG_ERR, '--- exception --- %s : Connection to DataBase %s failed in History request : %s'
                                  %(cfg.astid, cfg.cdr_db_uri, str(exc)))
        return results


def build_history_string(requester_id, nlines, kind):
        [dummyp, astid_src, dummyx, techno, phoneid, phonenum] = requester_id.split('/')
        if astid_src in configs:
                try:
                        reply = []
                        hist = update_history_call(configs[astid_src], techno, phoneid, phonenum, nlines, kind)
                        for x in hist:
                                try:
                                        ry1 = x[0].isoformat() + HISTSEPAR + x[1].replace('"', '') \
                                              + HISTSEPAR + str(x[10]) + HISTSEPAR + x[11]
                                except:
                                        ry1 = x[0] + HISTSEPAR + x[1].replace('"', '') \
                                              + HISTSEPAR + str(x[10]) + HISTSEPAR + x[11]

                                if kind == '0':
                                        num = x[3].replace('"', '')
                                        sipcid = "SIP/%s" % num
                                        cidname = num
                                        if sipcid in plist[astid_src].normal:
                                                cidname = '%s %s <%s>' %(plist[astid_src].normal[sipcid].calleridfirst,
                                                                         plist[astid_src].normal[sipcid].calleridlast,
                                                                         num)
                                        ry2 = HISTSEPAR + cidname + HISTSEPAR + 'OUT'
                                else:   # display callerid for incoming calls
                                        ry2 = HISTSEPAR + x[1].replace('"', '') + HISTSEPAR + 'IN'

                                reply.append(ry1)
                                reply.append(ry2)
                                reply.append(';')
                        return commandclass.history_srv2clt(reply)
                except Exception, exc:
                        log_debug(SYSLOG_ERR, '--- exception --- (%s) error : history : (client %s) : %s'
                                  %(astid_src, requester_id, str(exc)))
        else:
                return commandclass.dmessage_srv2clt('history KO : no such asterisk id <%s>' % astid_src)


## \brief Builds the full list of customers in order to send them to the requesting client.
# This should be done after a command called "customers".
# \return a string containing the full customers list
# \sa manage_tcp_connection
def build_customers(ctx, searchpatterns):
        searchpattern = ' '.join(searchpatterns)
        if ctx in contexts_cl:
                z = contexts_cl[ctx]
        else:
                log_debug(SYSLOG_WARNING, 'there has been no section defined for context %s : can not proceed directory search' % ctx)
                z = Context()

        fullstatlist = []

        if searchpattern == "":
                return commandclass.directory_srv2clt(z, [])

        dbkind = z.uri.split(":")[0]
        if dbkind == 'ldap':
                selectline = []
                for fname in z.search_matching_fields:
                        if searchpattern == "*":
                                selectline.append("(%s=*)" % fname)
                        else:
                                selectline.append("(%s=*%s*)" %(fname, searchpattern))

                try:
                        ldapid = xivo_ldap.xivo_ldap(z.uri)
                        results = ldapid.getldap("(|%s)" % ''.join(selectline),
                                        z.search_matching_fields)
                        for result in results:
                                result_v = {}
                                for f in z.search_matching_fields:
                                        if f in result[1]:
                                                result_v[f] = result[1][f][0]
                                fullstatlist.append(';'.join(z.result_by_valid_field(result_v)))
                except Exception, exc:
                        log_debug(SYSLOG_ERR, '--- exception --- ldaprequest : %s' % str(exc))

        elif dbkind == 'file' or dbkind == 'http':
                log_debug(SYSLOG_WARNING, 'the URI <%s> is not supported yet for directory search queries' %(dbkind))

        elif dbkind != '':
                if searchpattern == '*':
                        whereline = ''
                else:
                        wl = []
                        for fname in z.search_matching_fields:
                                wl.append("%s REGEXP '%s'" %(fname, searchpattern))
                        whereline = 'WHERE ' + ' OR '.join(wl)

                try:
                        conn = anysql.connect_by_uri(z.uri)
                        cursor = conn.cursor()
                        cursor.query("SELECT ${columns} FROM " + z.sqltable + " " + whereline,
                                     tuple(z.search_matching_fields),
                                     None)
                        results = cursor.fetchall()
                        conn.close()
                        for result in results:
                                result_v = {}
                                n = 0
                                for f in z.search_matching_fields:
                                        result_v[f] = result[n]
                                        n += 1
                                fullstatlist.append(';'.join(z.result_by_valid_field(result_v)))
                except Exception, exc:
                        log_debug(SYSLOG_ERR, '--- exception --- sqlrequest : %s' % str(exc))
        else:
                log_debug(SYSLOG_WARNING, "no database method defined - please fill the dir_db_uri field of the <%s> context" % ctx)

        uniq = {}
        fullstatlist.sort()
        fullstat_body = []
        for fsl in [uniq.setdefault(e,e) for e in fullstatlist if e not in uniq]:
                fullstat_body.append(fsl)
        return commandclass.directory_srv2clt(z, fullstat_body)


## \brief Builds the features reply.
def build_features_get(reqlist):
        context = reqlist[1]
        srcnum = reqlist[2]
        repstr = ''

        cursor = configs[reqlist[0]].userfeatures_db_conn.cursor()
        params = [srcnum, context]
        query = 'SELECT ${columns} FROM userfeatures WHERE number = %s AND context = %s'

        for key in ['enablevoicemail', 'callrecord', 'callfilter', 'enablednd']:
                try:
                        columns = (key,)
                        cursor.query(query, columns, params)
                        results = cursor.fetchall()
                        repstr += "%s;%s:;" %(key, str(results[0][0]))
                except Exception, exc:
                        log_debug(SYSLOG_ERR, '--- exception --- features_get(bool) id=%s key=%s : %s'
                                  %(str(reqlist), key, str(exc)))
                        return commandclass.features_srv2clt('get', 'KO')

        for key in ['unc', 'busy', 'rna']:
                try:
                        columns = ('enable' + key,)
                        cursor.query(query, columns, params)
                        resenable = cursor.fetchall()

                        columns = ('dest' + key,)
                        cursor.query(query, columns, params)
                        resdest = cursor.fetchall()

                        repstr += '%s;%s:%s;' % (key, str(resenable[0][0]), str(resdest[0][0]))

                except Exception, exc:
                        log_debug(SYSLOG_ERR, '--- exception --- features_get(str) id=%s key=%s : %s'
                                  %(str(reqlist), key, str(exc)))
                        return commandclass.features_srv2clt('get', 'KO')

        if len(repstr) == 0:
                repstr = 'KO'
        return commandclass.features_srv2clt('get', repstr)


## \brief Builds the features reply.
def build_features_put(reqlist):
        context = reqlist[1]
        srcnum = reqlist[2]
        try:
                len_reqlist = len(reqlist)
                if len_reqlist >= 4:
                        key = reqlist[3]
                        value = ''
                        if len_reqlist >= 5:
                                value = reqlist[4]
                        query = 'UPDATE userfeatures SET ' + key + ' = %s WHERE number = %s AND context = %s'
                        params = [value, srcnum, context]
                        cursor = configs[reqlist[0]].userfeatures_db_conn.cursor()
                        cursor.query(query, parameters = params)
                        repstr = 'OK'
                        response = commandclass.features_srv2clt('put', '%s;%s;%s;' %(repstr, key, value))
                else:
                        response = commandclass.features_srv2clt('put', 'KO')
        except Exception, exc:
                log_debug(SYSLOG_ERR, '--- exception --- features_put id=%s : %s'
                          %(str(reqlist), str(exc)))
                response = commandclass.features_srv2clt('put', 'KO')
        return response


## \brief Builds the full list of callerIDNames/hints in order to send them to the requesting client.
# This should be done after a command called "callerid".
# \return a string containing the full callerIDs/hints list
# \sa manage_tcp_connection
def build_callerids_hints(icommand):
        kind = icommand.name
        if len(icommand.args) == 0:
                reqid = kind + '-' + ''.join(random.sample(__alphanums__, 10)) + "-" + hex(int(time.time()))
                log_debug(SYSLOG_INFO, 'transaction ID for %s is %s' % (kind, reqid))
                fullstat_heavies[reqid] = []
                if kind == 'phones-list':
                        for astid in configs:
                                plist_n = plist[astid]
                                plist_normal_keys = filter(lambda j: plist_n.normal[j].towatch, plist_n.normal.iterkeys())
                                plist_normal_keys.sort()
                                for phonenum in plist_normal_keys:
                                        phoneinfo = ("ful",
                                                     plist_n.astid,
                                                     plist_n.normal[phonenum].build_basestatus(),
                                                     plist_n.normal[phonenum].build_cidstatus(),
                                                     plist_n.normal[phonenum].build_fullstatlist() + ";")
                                        #    + "groupinfos/technique"
                                        fullstat_heavies[reqid].append(':'.join(phoneinfo))
                elif kind == 'phones-add':
                        for astid in configs:
                                fullstat_heavies[reqid].extend(lstadd[astid])
                elif kind == 'phones-del':
                        for astid in configs:
                                fullstat_heavies[reqid].extend(lstdel[astid])
        else:
                reqid = icommand.args[0]

        if reqid in fullstat_heavies:
                fullstat = []
                nstat = len(fullstat_heavies[reqid])/ITEMS_PER_PACKET
                for j in xrange(ITEMS_PER_PACKET):
                        if len(fullstat_heavies[reqid]) > 0:
                                fullstat.append(fullstat_heavies[reqid].pop())
                if nstat > 0:
                        rtab = '%s=%s;%s' %(kind, reqid, ''.join(fullstat))
                else:
                        del fullstat_heavies[reqid]
                        rtab = '%s=0;%s'  %(kind, ''.join(fullstat))
                        log_debug(SYSLOG_INFO, 'building last packet reply for <%s ...>' %(rtab[0:40]))
                return rtab
        else:
                log_debug(SYSLOG_INFO, 'reqid <%s> not defined for %s reply' %(reqid, kind))
                return ''


"""
Communication with CTI clients
"""

def send_msg_to_cti_client(uinfo, message):
        try:
                if 'tcpmode' in uinfo:
                        conntype = uinfo.get('tcpmode')
                        if conntype:
                                # TCP
                                if 'connection' in uinfo:
                                        mysock = uinfo['connection']
                                        mysock.send(message + '\n')
                                else:
                                        log_debug(SYSLOG_WARNING,
                                                  'no connection field defined for user <%s> (TCP)' % uinfo.get('user'))
                        else:
                                # UDP
                                if 'connection' in uinfo:
                                        mysock = uinfo['connection'].request[1]
                                        mysock.sendto(message, uinfo['connection'].client_address)
                                else:
                                        log_debug(SYSLOG_WARNING,
                                                  'no connection field defined for user <%s> (UDP)' % uinfo.get('user'))
        except Exception, exc:
                log_debug(SYSLOG_ERR, '--- exception --- (send_msg_to_cti_client) send <%s ...> has failed for user <%s> : %s'
                          %(message[0:40], uinfo.get('user'), str(exc)))


def send_msg_to_cti_clients(strupdate):
        for astid in configs:
                if astid in userlist_lock:
                        userlist_lock[astid].acquire()
                        try:
                                for user,userinfo in userlist[astid].iteritems():
                                        send_msg_to_cti_client(userinfo, strupdate)
                        finally:
                                userlist_lock[astid].release()

"""
"""



## \brief Splits a channel name, allowing for instance local-extensions-3fb2,1 to be correctly split.
# \param channel the full channel name
# \return the phone id
def channel_splitter(channel):
        sp = channel.split("-")
        if len(sp) > 1:
                sp.pop()
        return "-".join(sp)


## \brief Extracts the phone number and the channel name from the asterisk/SIP/num-08abcf
# UI syntax for hangups or transfers
# \param fullname full string sent by the UI
# \return the phone number and the channel name, without the asterisk id
def split_from_ui(fullname):
        phone = ""
        channel = ""
        s1 = fullname.split("/")
        if len(s1) == 5:
                phone = s1[3] + "/" + channel_splitter(s1[4])
                channel = s1[3] + "/" + s1[4]
        return [phone, channel]


def originate_or_transfer(requester, l):
        src_split = l[1].split("/")
        dst_split = l[2].split("/")
        ret_message = 'originate_or_transfer KO from %s' % requester

        if len(src_split) == 5:
                [dummyp, astid_src, context_src, proto_src, userid_src] = src_split
        elif len(src_split) == 6:
                [dummyp, astid_src, context_src, proto_src, userid_src, dummy_exten_src] = src_split

        if len(dst_split) == 6:
                [dummyp, astid_dst, context_dst, proto_dst, userid_dst, exten_dst] = dst_split
        else:
                [dummyp, astid_dst, context_dst, proto_dst, userid_dst, exten_dst] = src_split
                exten_dst = l[2]
        if astid_src in configs and astid_src == astid_dst:
                if exten_dst == 'special:parkthecall':
                        exten_dst = configs[astid_dst].parkingnumber
                if astid_src in AMI_array_user_commands and AMI_array_user_commands[astid_src]:
                        if l[0] == 'originate':
                                log_debug(SYSLOG_INFO, "%s is attempting an ORIGINATE : %s" %(requester, str(l)))
                                if astid_dst != '':
                                        sipcid_src = "SIP/%s" % userid_src
                                        sipcid_dst = "SIP/%s" % userid_dst
                                        cidname_src = 'called by %s' % userid_src
                                        cidname_dst = 'calls %s' % userid_dst
                                        if sipcid_src in plist[astid_src].normal:
                                                cidname_src = '%s %s' %(plist[astid_src].normal[sipcid_src].calleridfirst,
                                                                        plist[astid_src].normal[sipcid_src].calleridlast)
                                        if sipcid_dst in plist[astid_dst].normal:
                                                cidname_dst = '%s %s' %(plist[astid_dst].normal[sipcid_dst].calleridfirst,
                                                                        plist[astid_dst].normal[sipcid_dst].calleridlast)
                                        ret = AMI_array_user_commands[astid_src].originate(proto_src,
                                                                                           userid_src,
                                                                                           cidname_src,
                                                                                           exten_dst,
                                                                                           cidname_dst,
                                                                                           context_dst)
                                else:
                                        ret = False
                                if ret:
                                        ret_message = 'originate OK (%s) %s %s' %(astid_src, l[1], l[2])
                                else:
                                        ret_message = 'originate KO (%s) %s %s' %(astid_src, l[1], l[2])
                        elif l[0] == 'transfer':
                                log_debug(SYSLOG_INFO, "%s is attempting a TRANSFER : %s" %(requester, str(l)))
                                phonesrc, phonesrcchan = split_from_ui(l[1])
                                if phonesrc == phonesrcchan:
                                        ret_message = 'transfer KO : %s not a channel' % phonesrcchan
                                else:
                                        if phonesrc in plist[astid_src].normal:
                                                channellist = plist[astid_src].normal[phonesrc].chann
                                                nopens = len(channellist)
                                                if nopens == 0:
                                                        ret_message = 'transfer KO : no channel opened on %s' % phonesrc
                                                else:
                                                        tchan = channellist[phonesrcchan].getChannelPeer()
                                                        ret = AMI_array_user_commands[astid_src].transfer(tchan,
                                                                                                          exten_dst,
                                                                                                          context_dst)
                                                        if ret:
                                                                ret_message = 'transfer OK (%s) %s %s' %(astid_src, l[1], l[2])
                                                        else:
                                                                ret_message = 'transfer KO (%s) %s %s' %(astid_src, l[1], l[2])
                        elif l[0] == 'atxfer':
                                log_debug(SYSLOG_INFO, "%s is attempting an ATXFER : %s" %(requester, str(l)))
                                phonesrc, phonesrcchan = split_from_ui(l[1])
                                if phonesrc == phonesrcchan:
                                        ret_message = 'atxfer KO : %s not a channel' % phonesrcchan
                                else:
                                        if phonesrc in plist[astid_src].normal:
                                                channellist = plist[astid_src].normal[phonesrc].chann
                                                nopens = len(channellist)
                                                if nopens == 0:
                                                        ret_message = 'atxfer KO : no channel opened on %s' % phonesrc
                                                else:
                                                        tchan = channellist[phonesrcchan].getChannelPeer()
                                                        ret = AMI_array_user_commands[astid_src].atxfer(tchan,
                                                                                                      exten_dst,
                                                                                                      context_dst)
                                                        if ret:
                                                                ret_message = 'atxfer OK (%s) %s %s' %(astid_src, l[1], l[2])
                                                        else:
                                                                ret_message = 'atxfer KO (%s) %s %s' %(astid_src, l[1], l[2])
        else:
                ret_message = 'originate or transfer KO : asterisk id mismatch (%s %s)' %(astid_src, astid_dst)
        return commandclass.dmessage_srv2clt(ret_message)


def hangup(requester, chan):
        astid_src = chan.split("/")[1]
        ret_message = 'hangup KO from %s' % requester
        if astid_src in configs:
                log_debug(SYSLOG_INFO, "%s is attempting a HANGUP : %s" %(requester, chan))
                phone, channel = split_from_ui(chan)
                if phone in plist[astid_src].normal:
                        if channel in plist[astid_src].normal[phone].chann:
                                channel_peer = plist[astid_src].normal[phone].chann[channel].getChannelPeer()
                                log_debug(SYSLOG_INFO, "UI action : %s : hanging up <%s> and <%s>"
                                          %(configs[astid_src].astid , channel, channel_peer))
                                if astid_src in AMI_array_user_commands and AMI_array_user_commands[astid_src]:
                                        ret = AMI_array_user_commands[astid_src].hangup(channel, channel_peer)
                                        if ret > 0:
                                                ret_message = 'hangup OK (%d) <%s>' %(ret, chan)
                                        else:
                                                ret_message = 'hangup KO : socket request failed'
                                else:
                                        ret_message = 'hangup KO : no socket available'
                        else:
                                ret_message = 'hangup KO : no such channel <%s>' % channel
                else:
                        ret_message = 'hangup KO : no such phone <%s>' % phone
        else:
                ret_message = 'hangup KO : no such asterisk id <%s>' % astid_src
        return commandclass.dmessage_srv2clt(ret_message)



def manage_login(cfg, requester_ip, requester_port, socket):
        global userinfo_by_requester
        for argum in commandclass.required_login_params():
                if argum not in cfg:
                        log_debug(SYSLOG_WARNING, 'missing argument when user attempts to log in : <%s>' % argum)
                        return commandclass.loginko_srv2clt('missing:%s' % argum)

        if cfg.get('astid') in configs:
                astid  = cfg.get('astid')
        else:
                log_debug(SYSLOG_INFO, "login command attempt from SB : asterisk name <%s> unknown" % cfg.get('astid'))
                return commandclass.loginko_srv2clt('asterisk_name')
        proto    = cfg.get('proto').lower()
        userid   = cfg.get('userid')
        state    = cfg.get('state')
        [whoami, whatsmyos] = cfg.get('ident').split("@")
        password = cfg.get('passwd')
        version  = cfg.get('version')
        if version == '':
                version = '0'

        if int(version) < REQUIRED_CLIENT_VERSION:
                return commandclass.loginko_srv2clt('version_client:%s;%d' % (version, REQUIRED_CLIENT_VERSION))

        capa_user = []
        userlist_lock[astid].acquire()
        try:
                userinfo = finduser(cfg.get('astid'), proto + userid)
                if userinfo == None:
                        repstr = commandclass.loginko_srv2clt('user_not_found')
                        log_debug(SYSLOG_INFO, "no user found %s" % str(cfg))
                elif password != userinfo['passwd']:
                        repstr = commandclass.loginko_srv2clt('login_passwd')
                else:
                        reterror = check_user_connection(userinfo, whoami)
                        if reterror is None:
                                for capa in capabilities_list:
                                        if capa in map_capas and (map_capas[capa] & userinfo.get('capas')):
                                                capa_user.append(capa)

                                sessionid = '%u' % random.randint(0,999999999)
                                connect_user(userinfo, sessionid,
                                             requester_ip, requester_port,
                                             whoami, whatsmyos, True, state,
                                             False, socket.makefile('w'))

                                repstr = "loginok=" \
                                         "context:%s;phonenum:%s;capas:%s;" \
                                         "xivoversion:%s;version:%s;state:%s" \
                                         %(userinfo.get('context'),
                                           userinfo.get('phonenum'),
                                           ",".join(capa_user),
                                           XIVOVERSION,
                                           __revision__,
                                           userinfo.get('state'))
                                if 'features' in capa_user:
                                        repstr += ';capas_features:%s' %(','.join(configs[astid].capafeatures))

                                userinfo['connection'] = socket
                                userinfo_by_requester[requester_ip + ":" + requester_port] = [cfg.get('astid'),
                                                                                              proto + userid,
                                                                                              userinfo.get('context'),
                                                                                              userinfo.get('capas')]
                                plist[astid].send_availstate_update(proto + userid, state)
                        else:
                                repstr = commandclass.loginko_srv2clt(reterror)
        finally:
                userlist_lock[astid].release()

        return repstr



## \brief Deals with requests from the UI clients.
# \param connid connection identifier
# \param allow_events tells if this connection belongs to events-allowed ones
# (for switchboard) or to events-disallowed ones (for WEBI CLI commands)
# \return none
def manage_tcp_connection(connid, allow_events):
        global AMI_array_user_commands, ins

        try:
                requester_ip   = connid[1]
                requester_port = str(connid[2])
                requester      = requester_ip + ":" + requester_port
        except Exception, exc:
                log_debug(SYSLOG_ERR, '--- exception --- UI connection : could not get IP details of connid = %s : %s'
                          %(str(connid),str(exc)))
                requester = str(connid)

        try:
                msg = connid[0].recv(BUFSIZE_LARGE)
        except Exception, exc:
                msg = ""
                log_debug(SYSLOG_ERR, '--- exception --- UI connection : a problem occured when recv from %s : %s'
                          %(requester, str(exc)))
        if len(msg) == 0:
                try:
                        connid[0].close()
                        ins.remove(connid[0])
                        if allow_events == True:
                                tcpopens_sb.remove(connid)
                                log_debug(SYSLOG_INFO, "TCP (SB)  socket closed from %s" % requester)
                                if requester in userinfo_by_requester:
                                        astid   = userinfo_by_requester[requester][0]
                                        username = userinfo_by_requester[requester][1]
                                        userlist_lock[astid].acquire()
                                        try:
                                                userinfo = finduser(astid, username)
                                                if userinfo == None:
                                                        log_debug(SYSLOG_INFO, "no user found for %s/%s" %(astid, username))
                                                else:
                                                        disconnect_user(userinfo)
                                                        plist[astid].send_availstate_update(username, "unknown")
                                        finally:
                                                userlist_lock[astid].release()
                                        del userinfo_by_requester[requester]
                        else:
                                tcpopens_webi.remove(connid)
                                log_debug(SYSLOG_INFO, "TCP (WEBI) socket closed from %s" % requester)
                except Exception, exc:
                        log_debug(SYSLOG_ERR, '--- exception --- UI connection [%s] : a problem occured when trying to close %s : %s'
                                  %(msg, str(connid[0]), str(exc)))
        else:
            for usefulmsgpart in msg.split("\n"):
                usefulmsg = usefulmsgpart.split("\r")[0]
                # debug/setup functions
                if usefulmsg == "show_infos":
                        try:
                                time_uptime = int(time.time() - time_start)
                                reply = 'infos=' \
                                        'xivo_version=%s;' \
                                        'server_version=%s;' \
                                        'clients_required_version=%d;' \
                                        'uptime=%d s;' \
                                        'logged_sb=%d/%d;' \
                                        'logged_xc=%d/%d' \
                                        %(XIVOVERSION,
                                          __revision__,
                                          REQUIRED_CLIENT_VERSION, time_uptime,
                                          conngui_sb, maxgui_sb, conngui_xc, maxgui_xc)
                                connid[0].send(reply + "\n")
                                connid[0].send("server capabilities = %s\n" %(",".join(capabilities_list)))
                                connid[0].send("%s:OK\n" %(XIVO_CLI_WEBI_HEADER))
                                if not allow_events:
                                        connid[0].close()
                        except Exception, exc:
                                log_debug(SYSLOG_ERR, '--- exception --- UI connection [%s] : KO when sending to %s : %s'
                                          %(usefulmsg, requester, str(exc)))
                elif usefulmsg == "show_phones":
                        try:
                                for astid, plast in plist.iteritems():
                                        k1 = plast.normal.keys()
                                        k1.sort()
                                        for kk in k1:
                                                canal = plast.normal[kk].chann
                                                connid[0].send('%10s %10s %6s [%s : %12s - %4d s] %4d %s\n'
                                                               %(plast.astid,
                                                                 kk,
                                                                 plast.normal[kk].towatch,
                                                                 plast.normal[kk].tech,
                                                                 plast.normal[kk].hintstatus,
                                                                 int(time.time() - plast.normal[kk].lasttime),
                                                                 len(canal),
                                                                 str(canal.keys())))
                                connid[0].send("%s:OK\n" %(XIVO_CLI_WEBI_HEADER))
                                if not allow_events:
                                        connid[0].close()
                        except Exception, exc:
                                log_debug(SYSLOG_ERR, '--- exception --- UI connection [%s] : KO when sending to %s : %s'
                                          %(usefulmsg, requester, str(exc)))
                elif usefulmsg == "show_busy":
                        try:
                                for astid, plast in plist.iteritems():
                                        connid[0].send('%s : normal=%d queues=%d oldqueues=%d\n'
                                                       %(astid, len(plast.normal), len(plast.queues), len(plast.oldqueues)))
                                        k1 = plast.oldqueues.keys()
                                        k1.sort()
                                        for kk in k1:
                                                connid[0].send('%s : %s %d\n' %(astid, kk, len(plast.oldqueues[kk])))
                                connid[0].send("%s:OK\n" %(XIVO_CLI_WEBI_HEADER))
                                if not allow_events:
                                        connid[0].close()
                        except Exception, exc:
                                log_debug(SYSLOG_ERR, '--- exception --- UI connection [%s] : KO when sending to %s : %s'
                                          %(usefulmsg, requester, str(exc)))
                elif usefulmsg == 'show_users' or usefulmsg == 'show_logged':
                        try:
                                for astid in userlist:
                                        userlist_lock[astid].acquire()
                                        try:
                                                connid[0].send("on <%s> :\n" % astid)
                                                for user,info in userlist[astid].iteritems():
                                                        if 'logintimestamp' in info or usefulmsg == 'show_users':
                                                                connid[0].send("%s %s\n" %(user, info))
                                        finally:
                                                userlist_lock[astid].release()
                                if requester in userinfo_by_requester:
                                        connid[0].send("%s\n" %str(userinfo_by_requester[requester]))
                                connid[0].send("%s:OK\n" %(XIVO_CLI_WEBI_HEADER))
                                if not allow_events:
                                        connid[0].close()
                        except Exception, exc:
                                log_debug(SYSLOG_ERR, '--- exception --- UI connection [%s] : KO when sending to %s : %s'
                                          %(usefulmsg, requester, str(exc)))
                elif usefulmsg == "show_ami":
                        try:
                                for amis in AMI_array_events_fd:
                                        connid[0].send("events   : %s : %s\n" %(amis, str(AMI_array_events_fd[amis])))
                                for amis in AMI_array_user_commands:
                                        connid[0].send("commands : %s : %s\n" %(amis, str(AMI_array_user_commands[amis])))
                                connid[0].send("%s:OK\n" %(XIVO_CLI_WEBI_HEADER))
                                if not allow_events:
                                        connid[0].close()
                        except Exception, exc:
                                log_debug(SYSLOG_ERR, '--- exception --- UI connection [%s] : KO when sending to %s : %s'
                                          %(usefulmsg, requester, str(exc)))
                elif usefulmsg != "":
                    if allow_events: # i.e. if SB-style connection
                        command = commandclass.parsecommand(usefulmsg)
                        if command.name in commandclass.get_list_commands_clt2srv():
                                if command.type == xivo_commandsets.CMD_LOGIN:
                                        try:
                                                cfg = commandclass.get_login_params(command)
                                                repstr = manage_login(cfg, requester_ip, requester_port, connid[0])
                                                connid[0].send(repstr + '\n')
                                        except Exception, exc:
                                                log_debug(SYSLOG_ERR, '--- exception --- UI connection [%s] : a problem occured when sending to %s : %s'
                                                          %(command.name, requester, str(exc)))
                                else:
                                        log_debug(SYSLOG_INFO, "%s is attempting a %s (TCP) : %s" %(requester, command.name, str(command.args)))
                                        r = commandclass.manage_srv2clt(connid[0], command)
                                        if r is not None:
                                                originate_or_transfer('clg/%s' % r,
                                                                      ['originate', 'p/clg/default/sip/%s/%s' %(r, r), 'p/clg/default///6%s' %(r)])
                                        try:
                                                if requester in userinfo_by_requester:
                                                        resp = parse_command_and_build_reply(userinfo_by_requester[requester],
                                                                                             ['tcp', connid[0], connid[1], connid[2]],
                                                                                             command)
                                                        try:
                                                                connid[0].send(resp + '\n')
                                                        except Exception, exc:
                                                                log_debug(SYSLOG_ERR, '--- exception --- (sending TCP) %s' % str(exc))
                                        except Exception, exc:
                                                log_debug(SYSLOG_ERR, '--- exception --- UI connection [%s] : a problem occured when sending to %s : %s'
                                                          %(command.name, requester, str(exc)))
                        else:
                                connid[0].send("Unknown Command\n")


                    else: # i.e. if WEBI-style connection
                                if requester_ip in ip_reverse_webi:
                                        try:
                                                astid = ip_reverse_webi[requester_ip]
                                                connid[0].send('%s:ID <%s>\n' %(XIVO_CLI_WEBI_HEADER, astid))
                                                if usefulmsg == 'xivo[userlist,update]':
                                                        update_userlist[astid] = True
                                                        connid[0].send('%s:OK\n' %(XIVO_CLI_WEBI_HEADER))
                                                        log_debug(SYSLOG_INFO, '%s : userlist update request received' % astid)
                                                elif astid in AMI_array_user_commands and AMI_array_user_commands[astid]:
                                                        try:
                                                                s = AMI_array_user_commands[astid].execclicommand(usefulmsg.strip())
                                                        except Exception, exc:
                                                                log_debug(SYSLOG_ERR, '--- exception --- (%s) WEBI command exec <%s> : (client %s) : %s'
                                                                          %(astid, str(usefulmsg.strip()), requester, str(exc)))
                                                        try:
                                                                for x in s: connid[0].send(x)
                                                                connid[0].send('%s:OK\n' %(XIVO_CLI_WEBI_HEADER))
                                                        except Exception, exc:
                                                                log_debug(SYSLOG_ERR, '--- exception --- (%s) WEBI command reply <%s> : (client %s) : %s'
                                                                          %(astid, str(usefulmsg.strip()), requester, str(exc)))
                                        except Exception, exc:
                                                log_debug(SYSLOG_ERR, '--- exception --- (%s) WEBI <%s> : (client %s) : %s'
                                                          %(astid, str(usefulmsg.strip()), requester, str(exc)))
                                                connid[0].send('%s:KO <Exception : %s>\n' %(XIVO_CLI_WEBI_HEADER, str(exc)))
                                else:
                                        connid[0].send('%s:KO <NOT ALLOWED>\n' %(XIVO_CLI_WEBI_HEADER))
                                try:
                                        ins.remove(connid[0])
                                        connid[0].close()
                                        log_debug(SYSLOG_INFO, 'TCP (WEBI) socket closed towards %s' % requester)
                                except Exception, exc:
                                        log_debug(SYSLOG_ERR, '--- exception --- (%s) WEBI could not close properly %s'
                                                  %(astid, requester))


## \brief Tells whether a channel is a "normal" one, i.e. SIP, IAX2, mISDN, Zap
# or not (like Local, Agent, ... anything else).
# \param chan the channel-like string (that should be like "proto/phone-id")
# \return True or False according to the above description
def is_normal_channel(chan):
        if chan.find("SIP/") == 0 or chan.find("IAX2/") == 0 or \
           chan.find("mISDN/") == 0 or chan.find("Zap/") == 0: return True
        else: return False


"""
Management of events that are spied on the AMI
"""


## \brief Handling of AMI events occuring in Events=on mode.
# \param astid the asterisk Id
# \param idata the data read from the AMI we want to parse
# \return none
# \sa handle_ami_event_dial, handle_ami_event_link, handle_ami_event_hangup
def handle_ami_event(astid, idata):
        global plist, save_for_next_packet_events
        if astid not in configs:
                log_debug(SYSLOG_INFO, "%s : no such asterisk Id" % astid)
                return

        full_idata = save_for_next_packet_events[astid] + idata
        evlist = full_idata.split("\r\n\r\n")
        save_for_next_packet_events[astid] = evlist.pop()
        plist_thisast = plist[astid]

        for evt in evlist:
                this_event = {}
                for myline in evt.split('\r\n'):
                        myfieldvalue = myline.split(': ', 1)
                        if len(myfieldvalue) == 2:
                                this_event[myfieldvalue[0]] = myfieldvalue[1]
                evfunction = this_event.get('Event')
                verboselog("/%s/ %s" %(astid, str(this_event)), True, False)
                if evfunction == 'Dial':
                        src     = this_event.get("Source")
                        dst     = this_event.get("Destination")
                        clid    = this_event.get("CallerID")
                        clidn   = this_event.get("CallerIDName")
                        context = this_event.get("Context")
                        try:
                                plist_thisast.handle_ami_event_dial(src, dst, clid, clidn)
                                #print "dial", context, x
                        except Exception, exc:
                                log_debug(SYSLOG_ERR, '--- exception --- handle_ami_event_dial : %s' % str(exc))
                elif evfunction == 'Link':
                        src     = this_event.get("Channel1")
                        dst     = this_event.get("Channel2")
                        clid1   = this_event.get("CallerID1")
                        clid2   = this_event.get("CallerID2")

                        #print src.split('-')[0], plist_thisast.normal[src.split('-')[0]].chann
                        #print dst.split('-')[0], plist_thisast.normal[dst.split('-')[0]].chann

                        #log_debug(SYSLOG_INFO, 'AMI:Link: %s : <%s> <%s> <%s> <%s> (%s)' %(astid, src, dst, clid1, clid2, this_event))
                        #for qname in plist_thisast.oldqueues:
                        #        print qname, plist_thisast.queues[qname]
                        # every time a link is established it goes there (even in regular no-agent calls)
                        if len(configs[astid].linkestablished) > 0:
                                try:
                                        user = '%s%s' % (dst.split('/')[0].lower(),
                                                         dst.split('/')[1].split('-')[0])
                                        userinfo = finduser(astid, user)
                                        ctxinfo  = contexts_cl.get(userinfo.get('context'))
        
                                        codetomatch = AMI_array_user_commands[astid].getvar(src, configs[astid].linkestablished)
                                        log_debug(SYSLOG_INFO, '%s : the variable %s has been set to <%s>'
                                                  % (astid, configs[astid].linkestablished, codetomatch))

        				if userinfo == None:
        					log_debug(SYSLOG_INFO, '%s : User <%s> not found (Link)' % (astid, user))
        				elif userinfo.has_key('ip') and userinfo.has_key('port') \
        					 and userinfo.has_key('state') and userinfo.has_key('sessionid') \
        					 and userinfo.has_key('sessiontimestamp'):
        					if time.time() - userinfo.get('sessiontimestamp') > xivoclient_session_timeout:
                                                        log_debug(SYSLOG_INFO, '%s : User <%s> session expired (Link)' % (astid, user))
                                                        userinfo = None
                                                else:
        						capalist = (userinfo.get('capas') & capalist_server)
                                                        if (capalist & CAPA_CUSTINFO):
                                                                state_userinfo = userinfo.get('state')
                                                        else:
                                                                userinfo = None
        				else:
        					log_debug(SYSLOG_WARNING, '%s : User <%s> session not defined (Link)' % (astid, user))
                                                userinfo = None
                                        
                                        uisend = sendfiche.senduiasync(userinfo,
                                                                       ctxinfo,
                                                                       codetomatch,
                                                                       xivoconf)
                                except Exception, exc:
                                        log_debug(SYSLOG_ERR, '--- exception --- handle_ami_event/Link : %s' % str(exc))

                        try:
                                plist_thisast.handle_ami_event_link(src, dst, clid1, clid2)
                        except Exception, exc:
                                log_debug(SYSLOG_ERR, '--- exception --- handle_ami_event_link : %s' % str(exc))
                elif evfunction == 'Unlink':
                        # there might be something to parse here
                        src   = this_event.get("Channel1")
                        dst   = this_event.get("Channel2")
                        clid1 = this_event.get("CallerID1")
                        clid2 = this_event.get("CallerID2")
                        try:
                                plist_thisast.handle_ami_event_unlink(src, dst, clid1, clid2)
                        except Exception, exc:
                                log_debug(SYSLOG_ERR, '--- exception --- handle_ami_event_unlink : %s' % str(exc))
                elif evfunction == 'Hangup':
                        chan  = this_event.get("Channel")
                        cause = this_event.get("Cause-txt")
                        try:
                                plist_thisast.handle_ami_event_hangup(chan, cause)
                        except Exception, exc:
                                log_debug(SYSLOG_ERR, '--- exception --- handle_ami_event_hangup : %s' % str(exc))
                elif evfunction == 'Reload':
                        message = this_event.get('Message')
                        if message == 'Reload Requested':
                                # warning : "reload" as well as "reload manager" can appear here
                                send_msg_to_cti_clients(commandclass.dmessage_srv2clt('Reload <%s>' % astid))
                        else:
                                log_debug(SYSLOG_INFO, "AMI:Reload: %s : %s" %(astid, str(this_event)))
                elif evfunction == 'Shutdown':
                        shutdown = this_event.get('Shutdown')
                        restart  = this_event.get('Restart')
                        log_debug(SYSLOG_INFO, "AMI:Shutdown: %s (how=%s restart=%s)" %(astid, shutdown, restart))
                        send_msg_to_cti_clients(commandclass.dmessage_srv2clt('Shutdown <%s>' % astid))
                elif evfunction == 'Join':
                        chan  = this_event.get('Channel')
                        clid  = this_event.get('CallerID')
                        qname = this_event.get('Queue')
                        count = int(this_event.get('Count'))
                        log_debug(SYSLOG_INFO, 'AMI:Join: %s queue=%s %s count=%s %s' % (astid, qname, chan, count, clid))
                        if len(clid) > 0:
                                if qname not in plist_thisast.queues:
                                        plist_thisast.queues[qname] = {}
                                        plist_thisast.oldqueues[qname] = []
                                plist_thisast.queues[qname][chan] = clid
                                if count != len(plist_thisast.queues[qname]):
                                        log_debug(SYSLOG_WARNING, "(AMI Join) %s : internal and asterisk count differ for queue <%s> : %d != %d"
                                                  %(astid, qname, len(plist_thisast.queues[qname]), count))
                                send_msg_to_cti_clients(commandclass.dmessage_srv2clt('<%s> <%s> is calling the queue <%s> (count = %d)'
                                                                                      %(chan, clid, qname, count)))
                elif evfunction == 'Leave':
                        chan  = this_event.get('Channel')
                        qname = this_event.get('Queue')
                        count = int(this_event.get('Count'))
                        if qname in plist_thisast.queues:
                                if chan in plist_thisast.queues[qname]:
                                        del plist_thisast.queues[qname][chan]
                                        plist_thisast.oldqueues[qname].append(chan)
                                        if count != len(plist_thisast.queues[qname]):
                                                log_debug(SYSLOG_WARNING, "(AMI Leave) %s : internal and asterisk count differ for queue <%s> : %d != %d"
                                                          %(astid, qname, len(plist_thisast.queues[qname]), count))
                                        log_debug(SYSLOG_INFO, 'AMI:Leave: %s queue=%s %s count=%s' % (astid, qname, chan, count))
                elif evfunction == 'PeerStatus':
                        # <-> register's ? notify's ?
                        pass
                elif evfunction == 'Agentlogin':
                        log_debug(SYSLOG_INFO, '//AMI:Agentlogin// %s : %s' %(astid, str(this_event)))
                elif evfunction == 'Agentlogoff':
                        log_debug(SYSLOG_INFO, '//AMI:Agentlogoff// %s : %s' %(astid, str(this_event)))
                elif evfunction == 'Agentcallbacklogin':
                        log_debug(SYSLOG_INFO, '//AMI:Agentcallbacklogin// %s : %s' %(astid, str(this_event)))
                elif evfunction == 'Agentcallbacklogoff':
                        log_debug(SYSLOG_INFO, '//AMI:Agentcallbacklogoff// %s : %s' %(astid, str(this_event)))
                elif evfunction == 'AgentCalled':
                        log_debug(SYSLOG_INFO, '//AMI:AgentCalled// %s : %s' %(astid, str(this_event)))
                        
                elif evfunction == 'ParkedCall':
                        # when the parking is requested
                        channel = this_event.get('Channel')
                        cfrom   = this_event.get('From')
                        exten   = this_event.get('Exten')
                        timeout = this_event.get('Timeout')
                        log_debug(SYSLOG_INFO, 'AMI:ParkedCall: %s : %s %s %s %s' %(astid, channel, cfrom, exten, timeout))
                        send_msg_to_cti_clients(commandclass.park_srv2clt('parked', [astid, channel, cfrom, exten, timeout]))
                elif evfunction == 'UnParkedCall':
                        # when somebody (From) took the call
                        channel = this_event.get('Channel')
                        cfrom   = this_event.get('From')
                        exten   = this_event.get('Exten')
                        log_debug(SYSLOG_INFO, 'AMI:UnParkedCall: %s : %s %s %s' %(astid, channel, cfrom, exten))
                        send_msg_to_cti_clients(commandclass.park_srv2clt('unparked', [astid, channel, cfrom, exten]))
                elif evfunction == 'ParkedCallTimeOut':
                        # when the timeout has occured
                        channel = this_event.get('Channel')
                        exten   = this_event.get('Exten')
                        log_debug(SYSLOG_INFO, 'AMI:ParkedCallTimeOut: %s : %s %s' %(astid, channel, exten))
                        send_msg_to_cti_clients(commandclass.park_srv2clt('timeout', [astid, channel, exten]))
                elif evfunction == 'ParkedCallGiveUp':
                        # when the peer is tired
                        channel = this_event.get('Channel')
                        exten   = this_event.get('Exten')
                        log_debug(SYSLOG_INFO, 'AMI:ParkedCallGiveUp: %s : %s %s' %(astid, channel, exten))
                        send_msg_to_cti_clients(commandclass.park_srv2clt('giveup', [astid, channel, exten]))
                elif evfunction == 'ParkedCallsComplete':
                        log_debug(SYSLOG_INFO, '//AMI:ParkedCallsComplete// %s : %s' %(astid, str(this_event)))
                        
                elif evfunction == 'Cdr':
                        log_debug(SYSLOG_INFO, '//AMI:Cdr// %s : %s' %(astid, str(this_event)))
                elif evfunction == 'Alarm':
                        log_debug(SYSLOG_INFO, '//AMI:Alarm// %s : %s' %(astid, str(this_event)))
                elif evfunction == 'AlarmClear':
                        log_debug(SYSLOG_INFO, '//AMI:AlarmClear// %s : %s' %(astid, str(this_event)))
                elif evfunction == 'FaxReceived':
                        log_debug(SYSLOG_INFO, '//AMI:FaxReceived// %s : %s' %(astid, str(this_event)))
                elif evfunction == 'Registry':
                        log_debug(SYSLOG_INFO, '//AMI:Registry// %s : %s' %(astid, str(this_event)))
                elif evfunction == 'MeetmeJoin':
                        channel = this_event.get('Channel')
                        meetme  = this_event.get('Meetme')
                        usernum = this_event.get('Usernum')
                        log_debug(SYSLOG_INFO, 'AMI:MeetmeJoin %s : %s %s %s'
                                  %(astid, channel, meetme, usernum))
                elif evfunction == 'MeetmeLeave':
                        channel = this_event.get('Channel')
                        meetme  = this_event.get('Meetme')
                        usernum = this_event.get('Usernum')
                        log_debug(SYSLOG_INFO, 'AMI:MeetmeLeave %s : %s %s %s'
                                  %(astid, channel, meetme, usernum))
                elif evfunction == 'ExtensionStatus':
                        exten   = this_event.get('Exten')
                        context = this_event.get('Context')
                        status  = this_event.get('Status')
                        log_debug(SYSLOG_INFO, 'AMI:ExtensionStatus: %s : %s %s %s' %(astid, exten, context, status))

                        sipphone = 'SIP/%s' % exten
                        if sipphone in plist_thisast.normal:
                                normv = plist_thisast.normal[sipphone]
                                normv.set_lasttime(time.time())
                                sippresence = 'Timeout'
                                if status == '-1':
                                        sippresence = 'Fail'
                                elif status == '0':
                                        sippresence = 'Ready'
                                elif status == '1':
                                        sippresence = 'On the phone'
                                elif status == '4':
                                        sippresence = 'Unavailable'
                                elif status == '8':
                                        sippresence = 'Ringing'
                                normv.set_hintstatus(sippresence)
                                plist_thisast.update_gui_clients(sipphone, "SIP-NTFY")
                        
                        # QueueMemberStatus ExtensionStatus
                        #                 0                  AST_DEVICE_UNKNOWN
                        #                 1               0  AST_DEVICE_NOT_INUSE  /  libre
                        #                 2               1  AST_DEVICE IN USE     / en ligne
                        #                 3                  AST_DEVICE_BUSY
                        #                                 4  AST_EXTENSION_UNAVAILABLE ?
                        #                 5                  AST_DEVICE_UNAVAILABLE
                        #                 6 AST_EXTENSION_RINGING = 8  appele
                elif evfunction == 'OriginateSuccess':
                        pass
                elif evfunction == 'OriginateFailure':
                        log_debug(SYSLOG_INFO, 'AMI:OriginateFailure: %s - reason = %s' % (astid, this_event.get('Reason')))
                        #define AST_CONTROL_HANGUP              1
                        #define AST_CONTROL_RING                2
                        #define AST_CONTROL_RINGING             3
                        #define AST_CONTROL_ANSWER              4
                        #define AST_CONTROL_BUSY                5
                        #define AST_CONTROL_TAKEOFFHOOK         6
                        #define AST_CONTROL_OFFHOOK             7
                        #define AST_CONTROL_CONGESTION          8
                        #define AST_CONTROL_FLASH               9
                        #define AST_CONTROL_WINK                10
                elif evfunction == 'Rename':
                        # appears when there is a transfer
                        channel_old = this_event.get('Oldname')
                        channel_new = this_event.get('Newname')
                        if channel_old.find('<MASQ>') < 0 and channel_new.find('<MASQ>') < 0 and \
                               is_normal_channel(channel_old) and is_normal_channel(channel_new):
                                log_debug(SYSLOG_INFO, 'AMI:Rename:N: %s : old=%s new=%s'
                                          %(astid, channel_old, channel_new))
                                phone_old = channel_splitter(channel_old)
                                phone_new = channel_splitter(channel_new)

                                channel_p1 = plist_thisast.normal[phone_old].chann[channel_old].getChannelPeer()
                                channel_p2 = plist_thisast.normal[phone_new].chann[channel_new].getChannelPeer()
                                phone_p1 = channel_splitter(channel_p1)

                                if channel_p2 == '':
                                        # occurs when 72 (interception) is called
                                        # A is calling B, intercepted by C
                                        # in this case old = B and new = C
                                        n1 = DUMMY_EXTEN
                                        n2 = DUMMY_EXTEN
                                else:
                                        phone_p2 = channel_splitter(channel_p2)
                                        n1 = plist_thisast.normal[phone_old].chann[channel_old].getChannelNum()
                                        n2 = plist_thisast.normal[phone_p2].chann[channel_p2].getChannelNum()

                                log_debug(SYSLOG_INFO, 'updating channels <%s> (%s) and <%s> (%s) and hanging up <%s>'
                                          %(channel_new, n1, channel_p1, n2, channel_old))

                                try:
                                        plist_thisast.normal_channel_fills(channel_new, DUMMY_CLID,
                                                                           DUMMY_STATE, 0, DUMMY_DIR,
                                                                           channel_p1, n1, 'ami-er1')
                                except Exception, exc:
                                        log_debug(SYSLOG_ERR, '--- exception --- %s : renaming (ami-er1) failed : %s' %(astid, str(exc)))

                                try:
                                        if channel_p1 != '':
                                                plist_thisast.normal_channel_fills(channel_p1, DUMMY_CLID,
                                                                                   DUMMY_STATE, 0, DUMMY_DIR,
                                                                                   channel_new, n2, 'ami-er2')
                                        else:
                                                log_debug(SYSLOG_INFO, 'channel_p1 is empty - was it a group call that has been intercepted ?')
                                except Exception, exc:
                                        log_debug(SYSLOG_ERR, '--- exception --- %s : renaming (ami-er2) failed : %s' %(astid, str(exc)))

                                try:
                                        plist_thisast.normal_channel_hangup(channel_old, 'ami-er3')
                                except Exception, exc:
                                        log_debug(SYSLOG_ERR, '--- exception --- %s : renaming (ami-er3 = hangup) failed : %s' %(astid, str(exc)))

                        else:
                                log_debug(SYSLOG_INFO, 'AMI:Rename:A: %s : old=%s new=%s'
                                          %(astid, channel_old, channel_new))
                elif evfunction == 'Newstate':
                        chan    = this_event.get('Channel')
                        clid    = this_event.get('CallerID')
                        clidn   = this_event.get('CallerIDName')
                        state   = this_event.get('State')
                        # state = Ringing, Up, Down
                        plist_thisast.normal_channel_fills(chan, clid,
                                                           state, 0, DUMMY_DIR,
                                                           DUMMY_RCHAN, DUMMY_EXTEN, 'ami-ns0')
                elif evfunction == 'Newcallerid':
                        # for tricky queues' management
                        chan    = this_event.get('Channel')
                        clid    = this_event.get('CallerID')
                        clidn   = this_event.get('CallerIDName')
                        log_debug(SYSLOG_INFO, 'AMI:Newcallerid: %s channel=%s callerid=%s calleridname=%s'
                                  %(astid, chan, clid, clidn))
                        # plist_thisast.normal_channel_fills(chan, clid,
                        # DUMMY_STATE, 0, DUMMY_DIR,
                        # DUMMY_RCHAN, DUMMY_EXTEN, 'ami-ni0')
                elif evfunction == 'Newchannel':
                        chan    = this_event.get('Channel')
                        clid    = this_event.get('CallerID')
                        state   = this_event.get('State')
                        # states = Ring, Down
                        if state == 'Ring':
                                plist_thisast.normal_channel_fills(chan, clid,
                                                                   'Calling', 0, DIR_TO_STRING,
                                                                   DUMMY_RCHAN, DUMMY_EXTEN, 'ami-nc0')
                        elif state == 'Down':
                                plist_thisast.normal_channel_fills(chan, clid,
                                                                   'Ringing', 0, DIR_FROM_STRING,
                                                                   DUMMY_RCHAN, DUMMY_EXTEN, 'ami-nc1')
                        # if not (clid == '' or (clid == '<unknown>' and is_normal_channel(chan))):
                        # for k in tcpopens_sb:
                        #       k[0].send('message=<' + clid + '> is entering the Asterisk <' + astid + '> through ' + chan + '\n')
                        # else:
                        # pass
                elif evfunction == 'UserEventFeature': # UserEvent(Feature,AppData: <context>|<num>|<unc>|<enable/disable>|<redir>)
                        try:
                                appdata = this_event.get('AppData').split('|')
                                log_debug(SYSLOG_INFO, 'AMI:UserEventFeature: %s : %s' % (astid, str(appdata)))
                                ctx = appdata[0]
                                userid = appdata[1]
                                feature = appdata[2]
                                enable = ''
                                value = ''
                                if len(appdata) >= 4:
                                        enable = appdata[3]
                                if len(appdata) >= 5:
                                        value = appdata[4]
                                strupdate = commandclass.features_srv2clt('update', ';'.join([astid, ctx, userid, feature, ':'.join([enable, value])]))
                                send_msg_to_cti_clients(strupdate)
                        except Exception, exc:
                                log_debug(SYSLOG_ERR, '--- exception --- (UserEventFeature) <%s> : %s' %(str(this_event), str(exc)))
                elif evfunction == 'Newexten': # in order to handle outgoing calls ?
                        chan    = this_event.get('Channel')
                        exten   = this_event.get('Extension')
                        context = this_event.get('Context')
                        if exten not in ['s', 'h', 't', 'enum']:
                                #print '--- exten :', chan, exten
                                plist_thisast.normal_channel_fills(chan, DUMMY_MYNUM,
                                                                   'Calling', 0, DIR_TO_STRING,
                                                                   DUMMY_RCHAN, exten, 'ami-ne0')
                        else:
                                pass
                        application = this_event.get('Application')
                        if application == 'Set':
                                #print application, this_event
                                pass
                        elif application == 'AGI':
                                #print application, this_event
                                pass
                        elif application == 'VoiceMailMain': # when s.o. checks one's own VM
                                #print application, this_event
                                pass
                        elif application == 'MeetMe':
                                #print application, this_event
                                pass
                        elif application == 'Park':
                                #print application, this_event
                                pass
                        elif application == 'Queue':
                                appdata = this_event.get('AppData')
                                exten   = this_event.get('Extension')
                                context = this_event.get('Context')
                                channel = this_event.get('Channel')
                                print application, appdata, exten, context, channel
                        elif application == 'VoiceMail': # when s.o. falls to s.o.(else)'s VM
                                #print application, this_event
                                pass
                        elif application not in ['Hangup', 'NoOp', 'Dial', 'Macro', 'MacroExit',
                                                 'Devstate', 'Playback',
                                                 'Answer', 'Background',
                                                 'AGI', 'Goto', 'GotoIf', 'SIPAddHeader', 'Wait']:
                                #print this_event
                                pass

                elif evfunction == 'MessageWaiting':
                        mwi_string = '%s waiting=%s; new=%s; old=%s' \
                                     % (this_event.get('Mailbox'), str(this_event.get('Waiting')), str(this_event.get('New')), str(this_event.get('Old')))
                        log_debug(SYSLOG_INFO, 'AMI:MessageWaiting: %s : %s' % (astid, mwi_string))
                elif evfunction == 'QueueParams':
                        log_debug(SYSLOG_INFO, '//AMI:QueueParams// %s : %s' %(astid, str(this_event)))
                elif evfunction == 'QueueMember':
                        log_debug(SYSLOG_INFO, '//AMI:QueueMember// %s : %s' %(astid, str(this_event)))
                elif evfunction == 'QueueMemberStatus':
                        qname    = this_event.get('Queue')
                        location = this_event.get('Location')
                        status   = int(this_event.get('Status'))

                        if qname in plist_thisast.queues and (status == 1 or status == 2 or status == 6):
                                est = ['?', 'Free', 'Busy', '?', '?', '?', 'Ringing', '?', '?']
                                if len(plist_thisast.queues[qname]) > 0:
                                        log_debug(SYSLOG_INFO,
                                                  'AMI:QueueMemberStatus: %s %s %s %s (%s)'
                                                  % (astid, qname, location, est[status], str(plist_thisast.queues[qname])))
                elif evfunction == 'Status':
                        state = this_event.get('State')
                        if state == 'Up':
                                chan    = this_event.get('Channel')
                                clid    = this_event.get('CallerID')
                                link    = this_event.get('Link')
                                exten   = this_event.get('Extension')
                                seconds = this_event.get('Seconds')
                                if link is not None:
                                        if seconds is None:
                                                # this is where the right callerid is set, esp in outgoing calls
                                                plist_thisast.normal_channel_fills(link, DUMMY_MYNUM,
                                                                                   'On the phone', 0, DIR_TO_STRING,
                                                                                   chan, clid,
                                                                                   'ami-st1')
                                                plist_thisast.normal_channel_fills(chan, DUMMY_MYNUM,
                                                                                   'On the phone', 0, DIR_FROM_STRING,
                                                                                   link, '',
                                                                                   'ami-st2')
                                        else:
                                                # this is where the right time of ongoing calls is set
                                                plist_thisast.normal_channel_fills(link, DUMMY_MYNUM,
                                                                                   'On the phone', int(seconds), DIR_FROM_STRING,
                                                                                   chan, clid,
                                                                                   'ami-st3')
                                                plist_thisast.normal_channel_fills(chan, DUMMY_MYNUM,
                                                                                   'On the phone', int(seconds), DIR_TO_STRING,
                                                                                   link, exten,
                                                                                   'ami-st4')
                                else:
                                        # we fall here when there is a MeetMe/Voicemail/Parked call ...
                                        log_debug(SYSLOG_INFO, 'AMI %s Status / linked with noone (Meetme conf, Voicemail, Parked call, ...) : chan=<%s>, clid=<%s>, exten=<%s>, seconds=<%s> : %s'
                                                  % (astid, chan, clid, exten, seconds, this_event))
                                        reply = AMI_array_user_commands[astid].execclicommand('show channel %s' % chan)
                                        res = {}
                                        for z in reply:
                                                if z.find('Application') >= 0 or z.find('Data') >= 0:
                                                        spl = z.split(':')
                                                        lhs = spl[0].strip()
                                                        rhs = spl[1].strip()
                                                        res[lhs] = rhs
                                        
                                        application = res['Application']
                                        if application == 'Parked Call':
                                                rep2 = AMI_array_user_commands[astid].execclicommand('show parkedcalls')
                                                #701          SIP/102-081cc888 (park-dial       SIP/101      1   )     40s
                                                for z2 in rep2[2:-1]: # 2 first lines are Ack Comm, Last one is Number of parked lines
                                                        #print '%s : %s ===> %s' % (application, chan, str(z2.strip().split()))
                                                        pass
                                        elif application == 'VoiceMailMain':
                                                print '<%s> <%s> <%s>' %(chan, application, res['Data'])
                                                pass
                                        elif application == 'MeetMe':
                                                #print '<%s> <%s> <%s>' %(chan, application, res['Data'])
                                                number = res['Data'].split('|')[0]
                                                rep2 = AMI_array_user_commands[astid].execclicommand('meetme list %s' % number)
                                                for z2 in rep2[1:-1]:
                                                        #print z2.strip()
                                                        pass
                                        elif application == 'VoiceMail':
                                                #print '<%s> <%s> <%s>' %(chan, application, res['Data'])
                                                pass

                                        if seconds is None:
                                                plist_thisast.normal_channel_fills(chan, DUMMY_MYNUM,
                                                                                   'On the phone', 0, DIR_TO_STRING,
                                                                                   DUMMY_RCHAN, DUMMY_EXTEN,
                                                                                   'ami-st5')
                                        else:
                                                plist_thisast.normal_channel_fills(chan, DUMMY_MYNUM,
                                                                                   'On the phone', int(seconds), DIR_TO_STRING,
                                                                                   DUMMY_RCHAN, exten,
                                                                                   'ami-st6')

                        elif state == 'Ring': # AST_STATE_RING
                                chan    = this_event.get('Channel')
                                seconds = this_event.get('Seconds')
                                exten   = this_event.get('Extension')
                                log_debug(SYSLOG_INFO, 'AMI %s Status / Ring (To): %s %s %s' % (astid, chan, exten, seconds))
                                plist_thisast.normal_channel_fills(chan, DUMMY_MYNUM,
                                                                   'Calling', int(seconds), DIR_TO_STRING,
                                                                   DUMMY_RCHAN, '<unknown>',
                                                                   'ami-st7')
                        elif state == 'Ringing': # AST_STATE_RINGING
                                chan    = this_event.get('Channel')
                                log_debug(SYSLOG_INFO, 'AMI %s Status / Ringing (From): %s' % (astid, chan))
                                plist_thisast.normal_channel_fills(chan, DUMMY_MYNUM,
                                                                   'Ringing', 0, DIR_FROM_STRING,
                                                                   DUMMY_RCHAN, '<unknown>',
                                                                   'ami-st8')
                        elif state == 'Rsrvd': # AST_STATE_RESERVED
                                # occurs in in meetme : AMI obelisk Status / Rsrvd: Zap/pseudo-1397436026
                                log_debug(SYSLOG_INFO, 'AMI %s Status / Rsrvd: %s'
                                          % (astid, this_event.get('Channel')))
                        else: # Down, OffHook, Dialing, Up, Busy
                                log_debug(SYSLOG_INFO, 'AMI %s Status / (other status event) : %s'
                                          % (astid, str(this_event)))
                elif evfunction == 'StatusComplete':
                        log_debug(SYSLOG_INFO, 'AMI %s StatusComplete' % astid)
                elif evfunction == 'UserEvent_txfax':
                        status = this_event.get('XIVO_FAXSTATUS')
                        log_debug(SYSLOG_INFO, 'AMI %s UserEvent_txfax (%s)' % (astid, status))

                        [faxid, faxstatus, remote] = status.split('|')
                        myconn = faxclients.pop(faxid)
                        faxpath = PATH_SPOOL_ASTERISK_FAX + '/' + faxid + ".tif"
                        os.unlink(faxpath)
                        log_debug(SYSLOG_INFO, "txfax event handler : removed %s" % faxpath)

                        if faxstatus == '0':
                                reply = 'ok;'
                        else:
                                reply = 'ko;%s' % faxstatus

                        # TODO: report remote station.
                        if myconn[0] == 'udp':
                                myconn[1].sendto('faxsent=%s\n' % reply, (myconn[2], myconn[3]))
                        else:
                                myconn[1].send('faxsent=%s\n' % reply)
                elif this_event.get('Response') == 'Follows' and this_event.get('Privilege') == 'Command':
                        log_debug(SYSLOG_INFO, 'AMI %s Response=Follows : %s' % (astid, str(this_event)))
                elif this_event.get('Response') == 'Success':
                        msg = this_event.get('Message')
                        if msg == 'Extension Status':
                                status  = this_event.get('Status')
                                hint    = this_event.get('Hint')
                                context = this_event.get('Context')
                                exten   = this_event.get('Exten')
                                # 90 seconds are needed to retrieve ~ 9000 phone statuses from an asterisk (on daemon startup)
                                if hint in plist_thisast.normal:
                                        normv = plist_thisast.normal[hint]
                                        normv.set_lasttime(time.time())
                                        sippresence = 'Timeout'
                                        if status == '-1':
                                                sippresence = 'Fail'
                                        elif status == '0':
                                                sippresence = 'Ready'
                                        elif status == '1':
                                                sippresence = 'On the phone'
                                        elif status == '4':
                                                sippresence = 'Unavailable'
                                        elif status == '8':
                                                sippresence = 'Ringing'
                                        normv.set_hintstatus(sippresence)
                                        plist_thisast.update_gui_clients(hint, "SIP-NTFY")
                                
                                # log_debug(SYSLOG_INFO, 'AMI %s Response=Success (Extension Status) %s %s %s %s' % (astid, status, hint, context, exten))
                        else:
                                log_debug(SYSLOG_INFO, 'AMI %s Response=Success : %s' % (astid, str(this_event)))
                elif len(this_event) > 0:
                        log_debug(SYSLOG_INFO, 'AMI:XXX: <%s> : %s' % (astid, str(this_event)))
                else:
                        log_debug(SYSLOG_INFO, 'AMI %s Other : %s' % (astid, str(this_event)))


## \brief Connects to the AMI if not yet.
# \param astid Asterisk id to (re)connect
# \return none
def update_amisocks(astid):
        try:
                if astid not in AMI_array_events_fd or AMI_array_events_fd[astid] is False:
                        log_debug(SYSLOG_INFO, '%s : AMI : attempting to connect' % astid)
                        als0 = connect_to_AMI((configs[astid].remoteaddr,
                                               configs[astid].ami_port),
                                              configs[astid].ami_login,
                                              configs[astid].ami_pass,
                                              True)
                        if als0:
                                AMI_array_events_fd[astid] = als0.fd
                                ins.append(als0.fd)
                                log_debug(SYSLOG_INFO, '%s : AMI : connected' % astid)
                                for x in plist[astid].normal.itervalues():
                                        x.clear_channels()
                                ret = als0.sendstatus()
                                if not ret:
                                        log_debug(SYSLOG_INFO, '%s : could not send status command' % astid)
                        else:
                                log_debug(SYSLOG_INFO, '%s : AMI : could NOT connect' % astid)
        except Exception, exc:
                log_debug(SYSLOG_ERR, '--- exception --- %s (update_amisocks) : %s' % (astid, str(exc)))

        try:
                if astid not in AMI_array_user_commands or AMI_array_user_commands[astid] is False:
                        log_debug(SYSLOG_INFO, '%s : AMI (commands)  : attempting to connect' % astid)
                        als1 = connect_to_AMI((configs[astid].remoteaddr,
                                               configs[astid].ami_port),
                                              configs[astid].ami_login,
                                              configs[astid].ami_pass,
                                              False)
                        if als1:
                                AMI_array_user_commands[astid] = als1
                                log_debug(SYSLOG_INFO, '%s : AMI (commands)  : connected' % astid)
                        else:
                                log_debug(SYSLOG_INFO, '%s : AMI (commands)  : could NOT connect' % astid)
        except Exception, exc:
                log_debug(SYSLOG_ERR, '--- exception --- %s (update_amisocks command) : %s' % (astid, str(exc)))


def update_services(astid):
        userlist_lock[astid].acquire()
        try:
                for user,userinfo in userlist[astid].iteritems():
                        if 'monit' in userinfo:
                                monit = userinfo['monit']
                                updatemessage = build_features_get([monit[0], monit[1], monit[2]])
                                send_msg_to_cti_client(userinfo, updatemessage)
        finally:
                userlist_lock[astid].release()


## \brief Updates the list of sip numbers according to the SSO then sends old and new peers to the UIs.
# The reconnection to the AMI is also done here when it has been broken.
# If the AMI sockets are dead, a reconnection is also attempted here.
# \param astid the asterisk Id
# \return none
# \sa get_phonelist_fromurl
def update_phonelist(astid):
        global plist, lstadd, lstdel

        try:
                dt1 = time.time()
                sipnuml = configs[astid].get_phonelist_fromurl()
                if sipnuml is None:
                        return
                dt2 = time.time()
                for x in configs[astid].extrachannels.split(','):
                        if x != '': sipnuml[x] = [x, '', '', x.split('/')[1], '', False]
                sipnumlistnew = dict.fromkeys(sipnuml.keys())
        except Exception, exc:
                log_debug(SYSLOG_ERR, '--- exception --- %s : get_phonelist_fromurl failed : %s' %(astid, str(exc)))
                sipnuml = {}

        sipnumlistold = dict.fromkeys(filter(lambda j: plist[astid].normal[j].towatch, plist[astid].normal))
        dt3 = time.time()
        lstadd[astid] = []
        lstdel[astid] = []
        for snl in sipnumlistold:
                pln = plist[astid].normal[snl]
                if snl not in sipnumlistnew:
                        lstdel[astid].append(":".join(["del",
                                                       astid,
                                                       pln.build_basestatus() + ';']))
                        deluser(astid, pln.tech.lower() + pln.phoneid)
                        del plist[astid].normal[snl] # or = "Absent"/0 ?
                else:
                        pln.updateIfNeeded(sipnuml[snl])
        dt4 = time.time()
        for snl in sipnumlistnew:
                if snl not in sipnumlistold:
                        if astid in AMI_array_events_fd:
                                AMI_array_events_fd[astid].write('Action: ExtensionState\r\n'
                                                                 'Exten: %s\r\n'
                                                                 'Context: %s\r\n'
                                                                 '\r\n'
                                                                 %(sipnuml[snl][3], sipnuml[snl][4]))
                        if snl.find("SIP") == 0:
                                plist[astid].normal[snl] = LineProp("SIP",
                                                                    snl.split("/")[1],
                                                                    sipnuml[snl][3],
                                                                    sipnuml[snl][4],
                                                                    "Timeout", True)
                                # replaced previous 'BefSubs' initial status here : avoids flooding of Timeout's
                                # when many phones are added at once
                        elif snl.find("IAX2") == 0:
                                plist[astid].normal[snl] = LineProp("IAX2",
                                                                    snl.split("/")[1],
                                                                    sipnuml[snl][3],
                                                                    sipnuml[snl][4],
                                                                    "Ready", True)
                        elif snl.find("mISDN") == 0:
                                plist[astid].normal[snl] = LineProp("mISDN",
                                                                    snl.split("/")[1],
                                                                    sipnuml[snl][3],
                                                                    sipnuml[snl][4],
                                                                    "Ready", True)
                        elif snl.find("Zap") == 0:
                                plist[astid].normal[snl] = LineProp("Zap",
                                                                    snl.split("/")[1],
                                                                    sipnuml[snl][3],
                                                                    sipnuml[snl][4],
                                                                    "Ready", True)
                        else:
                                log_debug(SYSLOG_WARNING, 'format <%s> not supported' % snl)
                                
                        if snl in plist[astid].normal:
                                plist[astid].normal[snl].set_callerid(sipnuml[snl])

                        lstadd[astid].append(":".join(["add",
                                                       astid,
                                                       plist[astid].normal[snl].build_basestatus(),
                                                       plist[astid].normal[snl].build_cidstatus(),
                                                       plist[astid].normal[snl].build_fullstatlist() + ';']))
        dt5 = time.time()
        log_debug(SYSLOG_INFO, '%s : sent ExtensionState request for new phones (%f seconds)' %(astid, (dt5-dt4)))
        if len(lstdel[astid]) > 0 or len(lstadd[astid]) > 0:
                strupdate = commandclass.phones_srv2clt('signal-deloradd',
                                                        [astid,
                                                         len(lstdel[astid]),
                                                         len(lstadd[astid]),
                                                         len(plist[astid].normal)])
                send_msg_to_cti_clients(strupdate)
                verboselog(strupdate, False, True)
        dt6 = time.time()
        #print 'update_phonelist', dt2-dt1, dt3-dt2, dt4-dt3, dt5-dt4, dt6-dt5


def database_update(me, myargs):
        try:
                lst = myargs[0].split(';')
                context = me[2]
                if context in contexts_cl:
                        csv = xivo_ldap.xivo_csv(contexts_cl[context].uri)
                        if csv.open():
                                vals = {}
                                for l in lst:
                                        [var, val] = l.split(':')
                                        vals[var.split('XIVOFORM-')[1]] = val
                                strs = []
                                for n in csv.keys:
                                        if n in vals:
                                                strs.append('"%s"' % vals[n])
                                        else:
                                                strs.append('""')
                                csv.add(strs)
        except Exception, exc:
                log_debug(SYSLOG_ERR, '--- exception --- database_update : %s' % str(exc))
        return ''



## \brief Connects to the AMI through AMIClass.
# \param address IP address
# \param loginname loginname
# \param password password
# \return the socket
def connect_to_AMI(address, loginname, password, events_on):
        lAMIsock = xivo_ami.AMIClass(address, loginname, password, events_on)
        try:
                lAMIsock.connect()
                lAMIsock.login()
        except socket.timeout: pass
        except socket:         pass
        except:
                del lAMIsock
                lAMIsock = False
        return lAMIsock


## \class LocalChannel
# \brief Properties of a temporary "Local" channel.
class LocalChannel:
        # \brief Class initialization.
        def __init__(self, istate, icallerid):
                self.state = istate
                self.callerid = icallerid
                self.peer = ""
        # \brief Sets the state and the peer channel name.
        def set_chan(self, istate, ipeer):
                self.state = istate
                if ipeer != "":
                        self.peer = ipeer
        def set_callerid(self, icallerid):
                self.callerid = icallerid


## \class PhoneList
# \brief Properties of the lines of a given Asterisk
class PhoneList:
        ## \var astid
        # \brief Asterisk id, the same as the one given in the configs

        ## \var normal
        # \brief "Normal" phone lines, like SIP, IAX, Zap, ...

        ## \var queues
        # \brief To store queues' statuses

        ## \var oldqueues
        # \brief To store closed queues channels

        ##  \brief Class initialization.
        def __init__(self, iastid):
                self.astid = iastid
                self.normal = {}
                self.queues = {}
                self.oldqueues = {}
                self.star10 = []


        def update_gui_clients(self, phonenum, fromwhom):
                phoneinfo = (fromwhom,
                             self.astid,
                             self.normal[phonenum].build_basestatus(),
                             self.normal[phonenum].build_cidstatus(),
                             self.normal[phonenum].build_fullstatlist())
                if self.normal[phonenum].towatch:
                        strupdate = commandclass.phones_srv2clt('update', phoneinfo)
                else:
                        strupdate = commandclass.phones_srv2clt('noupdate', phoneinfo)
                send_msg_to_cti_clients(strupdate)
                verboselog(strupdate, False, True)


        def send_availstate_update(self, username, state):
                try:
                        if username.find("sip") == 0:
                                phoneid = "SIP/" + username.split("sip")[1]
                        elif username.find("iax") == 0:
                                phoneid = "IAX/" + username.split("iax")[1]
                        else:
                                phoneid = ""

                        if phoneid in self.normal:
                                if state == "unknown" or self.normal[phoneid].imstat != state:
                                        self.normal[phoneid].set_imstat(state)
                                        self.normal[phoneid].update_time()
                                        self.update_gui_clients(phoneid, "kfc-sau")
                        else:
                                log_debug(SYSLOG_WARNING, "<%s> is not in my phone list" % phoneid)
                except Exception, exc:
                        log_debug(SYSLOG_ERR, '--- exception --- send_availstate_update : %s' % str(exc))


        def check_connected_accounts(self):
                userlist_lock[self.astid].acquire()
                try:
                        for user,userinfo in userlist[self.astid].iteritems():
                                if 'sessiontimestamp' in userinfo:
                                        if time.time() - userinfo.get('sessiontimestamp') > xivoclient_session_timeout:
                                                log_debug(SYSLOG_INFO, '%s : timeout reached for %s' %(self.astid, user))
                                                disconnect_user(userinfo)
                                                self.send_availstate_update(user, 'unknown')
                finally:
                        userlist_lock[self.astid].release()


        def normal_channel_fills(self, chan_src, num_src,
                                 action, timeup, direction,
                                 chan_dst, num_dst, comment):
                phoneid_src = channel_splitter(chan_src)
                phoneid_dst = channel_splitter(chan_dst)

                if phoneid_src not in self.normal:
                        self.normal[phoneid_src] = LineProp(phoneid_src.split("/")[0],
                                                            phoneid_src.split("/")[1],
                                                            phoneid_src.split("/")[1],
                                                            "which-context?", "hintstatus?", False)
                do_update = self.normal[phoneid_src].set_chan(chan_src, action, timeup, direction, chan_dst, num_dst, num_src)
                if do_update:
                        self.update_gui_clients(phoneid_src, comment + "F")


        def normal_channel_hangup(self, chan_src, comment):
                phoneid_src = channel_splitter(chan_src)
                if phoneid_src not in self.normal:
                        self.normal[phoneid_src] = LineProp(phoneid_src.split("/")[0],
                                                            phoneid_src.split("/")[1],
                                                            phoneid_src.split("/")[1],
                                                            "which-context?", "hintstatus?", False)
                self.normal[phoneid_src].set_chan_hangup(chan_src)
                self.update_gui_clients(phoneid_src, comment + "H")
                self.normal[phoneid_src].del_chan(chan_src)
                self.update_gui_clients(phoneid_src, comment + "D")
                if len(self.normal[phoneid_src].chann) == 0 and self.normal[phoneid_src].towatch == False:
                        del self.normal[phoneid_src]

        ## \brief Updates some channels according to the Dial events occuring in the AMI.
        # \param src the source channel
        # \param dst the dest channel
        # \param clid the callerid
        # \param clidn the calleridname
        # \return none
        def handle_ami_event_dial(self, src, dst, clid, clidn):
                self.normal_channel_fills(src, DUMMY_MYNUM,
                                          "Calling", 0, DIR_TO_STRING,
                                          dst, DUMMY_EXTEN,
                                          "ami-ed1")
                self.normal_channel_fills(dst, DUMMY_MYNUM,
                                          "Ringing", 0, DIR_FROM_STRING,
                                          src, clid,
                                          "ami-ed2")


        ## \brief Updates some channels according to the Link events occuring in the AMI.
        # \param src the source channel
        # \param dst the dest channel
        # \param clid1 the src callerid
        # \param clid2 the dest callerid
        # \return none
        def handle_ami_event_link(self, src, dst, clid1, clid2):
                if src not in self.star10:
                        self.normal_channel_fills(src, DUMMY_MYNUM,
                                                  "On the phone", 0, DIR_TO_STRING,
                                                  dst, clid2,
                                                  "ami-el1")
                if dst not in self.star10:
                        self.normal_channel_fills(dst, DUMMY_MYNUM,
                                                  "On the phone", 0, DIR_FROM_STRING,
                                                  src, clid1,
                                                  "ami-el2")


        # \brief Fills the star10 field on unlink events.
        # \param src the source channel
        # \param dst the dest channel
        # \param clid1 the src callerid
        # \param clid2 the dest callerid
        # \return none
        def handle_ami_event_unlink(self, src, dst, clid1, clid2):
                if src not in self.star10:
                        self.star10.append(src)
                if dst not in self.star10:
                        self.star10.append(dst)


        # \brief Updates some channels according to the Hangup events occuring in the AMI.
        # \param chan the channel
        # \param cause the reason why there has been a hangup (not used)
        # \return
        def handle_ami_event_hangup(self, chan, cause):
                if chan in self.star10:
                        self.star10.remove(chan)
                self.normal_channel_hangup(chan, "ami-eh0")



## \class ChannelStatus
# \brief Properties of a Channel, as given by the AMI.
class ChannelStatus:
        ## \var status
        # \brief Channel status

        ## \var deltatime
        # \brief Elapsed time spent by the channel with the current status

        ## \var time
        # \brief Absolute time

        ## \var direction
        # \brief "To" or "From"

        ## \var channel_peer
        # \brief Channel name of the peer with whom it is in relation

        ## \var channel_num
        # \brief Phone number of the peer with whom it is in relation

        ##  \brief Class initialization.
        def __init__(self, istatus, dtime, idir, ipeerch, ipeernum, itime, imynum):
                self.status = istatus
                self.special = "" # voicemail, meetme, ...
                self.deltatime = dtime
                self.time = itime
                self.direction = idir
                self.channel_peer = ipeerch
                self.channel_num = ipeernum
                self.channel_mynum = imynum
        def updateDeltaTime(self, dtime):
                self.deltatime = dtime
        def setChannelPeer(self, ipeerch):
                self.channel_peer = ipeerch
        def setChannelNum(self, ipeernum):
                self.channel_num = ipeernum

        def getChannelPeer(self):
                return self.channel_peer
        def getChannelNum(self):
                return self.channel_num
        def getChannelMyNum(self):
                return self.channel_mynum
        def getDirection(self):
                return self.direction
        def getTime(self):
                return self.time
        def getDeltaTime(self):
                return self.deltatime
        def getStatus(self):
                return self.status


## \class LineProp
# \brief Properties of a phone line. It might contain many channels.
class LineProp:
        ## \var tech
        # \brief Protocol of the phone (SIP, IAX2, ...)
        
        ## \var phoneid
        # \brief Phone identifier
        
        ## \var phonenum
        # \brief Phone number
        
        ## \var context
        # \brief Context
        
        ## \var lasttime
        # \brief Last time the phone has received a reply from a SUBSCRIBE
        
        ## \var chann
        # \brief List of Channels, with their properties as ChannelStatus
        
        ## \var hintstatus
        # \brief Status given through SIP presence detection
        
        ## \var imstat
        # \brief Instant Messaging status, as given by Xivo Clients
        
        ## \var voicemail
        # \brief Voicemail status
        
        ## \var queueavail
        # \brief Queue availability
        
        ## \var callerid
        # \brief Caller ID
        
        ## \var towatch
        # \brief Boolean value that tells whether this phone is watched by the switchboards
        
        ##  \brief Class initialization.
        def __init__(self, itech, iphoneid, iphonenum, icontext, ihintstatus, itowatch):
                self.tech = itech
                self.phoneid  = iphoneid
                self.phonenum = iphonenum
                self.context = icontext
                self.lasttime = 0
                self.chann = {}
                self.hintstatus = ihintstatus # Asterisk "hints" status
                self.imstat = "unknown"  # XMPP / Instant Messaging status
                self.voicemail = ""  # Voicemail status
                self.queueavail = "" # Availability as a queue member
                self.calleridfull = "nobody"
                self.calleridfirst = "nobody"
                self.calleridlast = "nobody"
                self.groups = ""
                self.towatch = itowatch
        def set_tech(self, itech):
                self.tech = itech
        def set_phoneid(self, iphoneid):
                self.phoneid = iphoneid
        def set_phonenum(self, iphonenum):
                self.phonenum = iphonenum
        def set_hintstatus(self, ihintstatus):
                self.hintstatus = ihintstatus
        def set_imstat(self, istatus):
                self.imstat = istatus
        def set_lasttime(self, ilasttime):
                self.lasttime = ilasttime

        def build_basestatus(self):
                basestatus = (self.tech.lower(),
                              self.phoneid,
                              self.phonenum,
                              self.context,
                              self.imstat,
                              self.hintstatus,
                              self.voicemail,
                              self.queueavail)
                return ":".join(basestatus)
        def build_cidstatus(self):
                cidstatus = (self.calleridfull,
                             self.calleridfirst,
                             self.calleridlast)
                return ":".join(cidstatus)
        ## \brief Builds the channel-by-channel part for the hints/update replies.
        # \param phoneid the "pointer" to the Asterisk phone statuses
        # \return the string containing the statuses for each channel of the given phone
        def build_fullstatlist(self):
                nchans = len(self.chann)
                fstat = [str(nchans)]
                for chan, phone_chan in self.chann.iteritems():
                        fstat.extend((":", chan, ":",
                                      phone_chan.getStatus(), ":",
                                      str(phone_chan.getDeltaTime()), ":",
                                      phone_chan.getDirection(), ":",
                                      phone_chan.getChannelPeer(), ":",
                                      phone_chan.getChannelNum()))
                return ''.join(fstat)

        def set_callerid(self, icallerid):
                self.calleridfull  = icallerid[0]
                self.calleridfirst = icallerid[1]
                self.calleridlast  = icallerid[2]
        def updateIfNeeded(self, icallerid):
                if icallerid[0:3] != (self.calleridfull, self.calleridfirst, self.calleridlast):
                        log_debug(SYSLOG_INFO, 'updated parameters for user <%s/%s> : %s => %s'
                                  % (self.tech, self.phoneid,
                                     (self.calleridfull, self.calleridfirst, self.calleridlast),
                                     icallerid[0:3]))
                        self.calleridfull  = icallerid[0]
                        self.calleridfirst = icallerid[1]
                        self.calleridlast  = icallerid[2]
        ##  \brief Updates the time elapsed on a channel according to current time.
        def update_time(self):
                nowtime = time.time()
                for ic in self.chann:
                        dtime = int(nowtime - self.chann[ic].getTime())
                        self.chann[ic].updateDeltaTime(dtime)
        ##  \brief Removes all channels.
        def clear_channels(self):
                self.chann = {}
        ##  \brief Adds a channel or changes its properties.
        # If the values of status, itime, peerch and/or peernum are empty,
        # they are not updated : the previous value is kept.
        # \param ichan the Channel to hangup.
        # \param status the status to set
        # \param itime the elapsed time to set
        def set_chan(self, ichan, status, itime, idir, peerch, peernum, mynum):
                #print "<%s> <%s> <%s> <%s> <%s> <%s> <%s>" %(ichan, status, itime, idir, peerch, peernum, mynum)
                do_update = True
                if mynum == "<unknown>" and is_normal_channel(ichan):
                        mynum = channel_splitter(ichan)
                        #               if peernum == "<unknown>" and is_normal_channel(peerch):
                        #                       peernum = channel_splitter(peerch)
                # does not update peerch and peernum if the new values are empty
                newstatus = status
                newdir = idir
                newpeerch = peerch
                newpeernum = peernum
                newmynum = mynum
                if ichan in self.chann:
                        thischannel = self.chann[ichan]
                        oldpeernum = thischannel.getChannelNum()

                        if status  == "": newstatus = thischannel.getStatus()
                        if idir    == "": newdir = thischannel.getDirection()
                        if peerch  == "": newpeerch = thischannel.getChannelPeer()
                        if oldpeernum != "": newpeernum = oldpeernum
                        if mynum   == "": newmynum = thischannel.getChannelMyNum()

                        # mynum != thischannel.getChannelMyNum()
                        # when dialing "*10", there are many successive newextens occuring, that reset
                        # the time counter to 0
                        if status == thischannel.getStatus() and \
                           idir == thischannel.getDirection() and \
                           peerch == thischannel.getChannelPeer() and \
                           peernum == thischannel.getChannelNum():
                                do_update = False

                if do_update:
                        firsttime = time.time()
                        self.chann[ichan] = ChannelStatus(newstatus, itime, newdir,
                                                          newpeerch, newpeernum, firsttime - itime,
                                                          newmynum)
                        for ic in self.chann:
                                self.chann[ic].updateDeltaTime(int(firsttime - self.chann[ic].getTime()))
                return do_update


        ##  \brief Hangs up a Channel.
        # \param ichan the Channel to hangup.
        def set_chan_hangup(self, ichan):
                nichan = ichan
                if ichan.find("<ZOMBIE>") >= 0:
                        log_debug(SYSLOG_INFO, "sch channel contains a <ZOMBIE> part (%s) : sending hup to %s anyway" %(ichan,nichan))
                        nichan = ichan.split("<ZOMBIE>")[0]
                firsttime = time.time()
                self.chann[nichan] = ChannelStatus("Hangup", 0, "", "", "", firsttime, "")
                for ic in self.chann:
                        self.chann[ic].updateDeltaTime(int(firsttime - self.chann[ic].getTime()))

        ##  \brief Removes a Channel.
        # \param ichan the Channel to remove.
        def del_chan(self, ichan):
                nichan = ichan
                if ichan.find("<ZOMBIE>") >= 0:
                        log_debug(SYSLOG_INFO, "dch channel contains a <ZOMBIE> part (%s) : deleting %s anyway" %(ichan,nichan))
                        nichan = ichan.split("<ZOMBIE>")[0]
                if nichan in self.chann: del self.chann[nichan]


class Context:
        def __init__(self):
                self.uri = ''
                self.sqltable = ''
                self.sheetui = ''
                self.search_titles = []
                self.search_valid_fields = []
                self.search_matching_fields = []
                self.sheet_valid_fields = []
                self.sheet_matching_fields = []
                self.sheet_callidmatch = []
        def setUri(self, uri):
                self.uri = uri
        def setSqlTable(self, sqltable):
                self.sqltable = sqltable
        def setSheetUi(self, sheetui):
                self.sheetui = sheetui

        def setSearchValidFields(self, vf):
                self.search_valid_fields = vf
                for x in vf:
                        self.search_titles.append(x[0])
        def setSearchMatchingFields(self, mf):
                self.search_matching_fields = mf

        def setSheetValidFields(self, vf):
                self.sheet_valid_fields = vf
        def setSheetMatchingFields(self, mf):
                self.sheet_matching_fields = mf
        def setSheetCallidMatch(self, cidm):
                self.sheet_callidmatch = cidm

        def result_by_valid_field(self, result):
                reply_by_field = []
                for [dummydispname, dbnames_list, keepspaces] in self.search_valid_fields:
                        field_value = ""
                        for dbname in dbnames_list:
                                if dbname in result and field_value is "":
                                        field_value = result[dbname]
                        if keepspaces:
                                reply_by_field.append(field_value)
                        else:
                                reply_by_field.append(field_value.replace(' ', ''))
                return reply_by_field


## \class AsteriskRemote
# \brief Properties of an Asterisk server
class AsteriskRemote:
        ## \var astid
        # \brief Asterisk String ID
        
        ## \var userlist_url
        # \brief Asterisk's URL
        
        ## \var extrachannels
        # \brief Comma-separated List of the Channels not present in the SSO

        ## \var localaddr
        # \brief Local IP address

        ## \var remoteaddr
        # \brief Address of the Asterisk server

        ## \var ipaddress_webi
        # \brief IP address allowed to send CLI commands

        ## \var ami_port
        # \brief AMI port of the monitored Asterisk

        ## \var ami_login
        # \brief AMI login of the monitored Asterisk

        ## \var ami_pass
        # \brief AMI password of the monitored Asterisk
        
        ##  \brief Class initialization.
        def __init__(self,
                     astid,
                     userlist_url,
                     extrachannels,
                     localaddr = '127.0.0.1',
                     remoteaddr = '127.0.0.1',
                     ipaddress_webi = '127.0.0.1',
                     ami_port = 5038,
                     ami_login = 'xivouser',
                     ami_pass = 'xivouser',
                     contexts = '',
                     userfeatures_db_uri = '',
                     capafeatures = [],
                     cdr_db_uri = '',
                     realm = 'asterisk',
                     parkingnumber = '700',
                     faxcallerid = 'faxcallerid',
                     linkestablished = ''):

                self.astid = astid
                self.userlist_url = userlist_url
                self.userlist_md5 = ""
                self.userlist_kind = userlist_url.split(':')[0]
                self.extrachannels = extrachannels
                self.localaddr = localaddr
                self.remoteaddr = remoteaddr
                self.ipaddress_webi = ipaddress_webi
                self.ami_port = ami_port
                self.ami_login = ami_login
                self.ami_pass = ami_pass
                self.userfeatures_db_uri  = userfeatures_db_uri
                self.userfeatures_db_conn = anysql.connect_by_uri(userfeatures_db_uri)
                self.capafeatures = capafeatures
                self.cdr_db_uri  = cdr_db_uri
                self.cdr_db_conn = anysql.connect_by_uri(cdr_db_uri)
                # charset = 'utf8' : add ?charset=utf8 to the URI

                self.realm = realm
                self.parkingnumber = parkingnumber
                self.faxcallerid = faxcallerid
                self.linkestablished = linkestablished
                self.contexts = {}
                if contexts != '':
                        for ctx in contexts.split(','):
                                if ctx in xivoconf.sections():
                                        self.contexts[ctx] = dict(xivoconf.items(ctx))

        ## \brief Function to load user file.
        # SIP, Zap, mISDN and IAX2 are taken into account there.
        # There would remain MGCP, CAPI, h323, ...
        # \param url the url where lies the sso, it can be file:/ as well as http://
        # \return the new phone numbers list
        # \sa update_phonelist
        def get_phonelist_fromurl(self):
                numlist = {}
                try:
                        if self.userlist_kind == 'file':
                                f = urllib.urlopen(self.userlist_url)
                        else:
                                f = urllib.urlopen(self.userlist_url + "?sum=%s" % self.userlist_md5)
                except Exception, exc:
                        log_debug(SYSLOG_ERR, "--- exception --- %s : unable to open URL %s : %s" %(self.astid, self.userlist_url, str(exc)))
                        return numlist

                t1 = time.time()
                try:
                        phone_list = []
                        mytab = []
                        for line in f:
                                mytab.append(line)
                        f.close()
                        fulltable = ''.join(mytab)
                        savemd5 = self.userlist_md5
                        self.userlist_md5 = md5.md5(fulltable).hexdigest()
                        csvreader = csv.reader(mytab, delimiter = '|')
                        # builds the phone_list
                        for line in csvreader:
                                if len(line) == USERLIST_LENGTH:
                                        if line[6] == "0":
                                                phone_list.append(line)
                                elif len(line) == USERLIST_LENGTH - 1:
                                        if line[6] == "0":
                                                line.append("0")
                                                phone_list.append(line)
                                elif len(line) == 1:
                                        if line[0] == 'XIVO-WEBI: no-data':
                                                log_debug(SYSLOG_INFO, "%s : received no-data from WEBI" % self.astid)
                                        elif line[0] == 'XIVO-WEBI: no-update':
                                                log_debug(SYSLOG_INFO, "%s : received no-update from WEBI" % self.astid)
                                                numlist = None
                                                self.userlist_md5 = savemd5
                                else:
                                        pass
                        t2 = time.time()
                        log_debug(SYSLOG_INFO, "%s : URL %s has read %d bytes in %f seconds" %(self.astid, self.userlist_url, len(fulltable), (t2-t1)))
                except Exception, exc:
                        log_debug(SYSLOG_ERR, "--- exception --- %s : a problem occured when building phone list : %s" %(self.astid, str(exc)))
                        return numlist
                
                try:
                        # updates other accounts
                        for l in phone_list:
                                try:
                                        # line is protocol | username | password | rightflag |
                                        #         phone number | initialized | disabled(=1) | callerid |
                                        #         firstname | lastname | context | enable_hint
                                        [sso_tech, sso_phoneid, sso_passwd, sso_cti_allowed,
                                         sso_phonenum, isinitialized, sso_l6,
                                         fullname, firstname, lastname, sso_context, enable_hint] = l

                                        if sso_phonenum != '':
                                                fullname = '%s %s <b>%s</b>' % (firstname, lastname, sso_phonenum)
                                                if sso_tech == 'sip':
                                                        argg = 'SIP/%s' % sso_phoneid
                                                elif sso_tech == 'iax':
                                                        argg = 'IAX2/%s' % sso_phoneid
                                                elif sso_tech == 'misdn':
                                                        argg = 'mISDN/%s' % sso_phoneid
                                                elif sso_tech == 'zap':
                                                        argg = 'Zap/%s' % sso_phoneid
                                                else:
                                                        argg = ''
                                                if argg != '':
                                                        # isinitialized = '1' # XXXXXXXXXX
                                                        adduser(self.astid, sso_tech + sso_phoneid, sso_passwd, sso_context, sso_phonenum,
                                                                bool(int(isinitialized)), sso_cti_allowed)
                                                        if bool(int(isinitialized)):
                                                                numlist[argg] = fullname, firstname, lastname, sso_phonenum, sso_context, bool(int(enable_hint))
                                except Exception, exc:
                                        log_debug(SYSLOG_ERR, '--- exception --- %s : a problem occured when building phone list : %s' %(self.astid, str(exc)))
                                        return numlist
                        if numlist is not None:
                                log_debug(SYSLOG_INFO, '%s : found %d ids in phone list, among which %d ids are registered as users'
                                          %(self.astid, len(phone_list), len(numlist)))
                finally:
                        f.close()
                return numlist


## \brief Adds (or updates) a user in the userlist.
# \param user the user to add
# \param passwd the user's passwd
# \return none
def adduser(astname, user, passwd, context, phonenum,
            isinitialized, cti_allowed):
        global userlist
        if userlist[astname].has_key(user):
                # updates
                userlist[astname][user]['passwd']   = passwd
                userlist[astname][user]['context']  = context
                userlist[astname][user]['phonenum'] = phonenum
                userlist[astname][user]['init']     = isinitialized
        else:
                userlist[astname][user] = {'user'     : user,
                                           'passwd'   : passwd,
                                           'context'  : context,
                                           'phonenum' : phonenum,
                                           'init'     : isinitialized,
                                           'capas'    : 0}
        if cti_allowed == '1':
                userlist[astname][user]['capas'] = CAPA_ALMOST_ALL
        else:
                userlist[astname][user]['capas'] = 0


## \brief Deletes a user from the userlist.
# \param user the user to delete
# \return none
def deluser(astname, user):
        global userlist
        if userlist[astname].has_key(user):
                userlist[astname].pop(user)


def check_user_connection(userinfo, whoami):
        if userinfo.has_key('init'):
                if not userinfo['init']:
                        return 'uninit_phone'
        if userinfo.has_key('sessiontimestamp'):
                if time.time() - userinfo.get('sessiontimestamp') < xivoclient_session_timeout:
                        if 'lastconnwins' in userinfo:
                                if userinfo['lastconnwins'] is True:
                                        # one should then disconnect the first peer
                                        pass
                                else:
                                        return 'already_connected'
                        else:
                                return 'already_connected'
        if whoami == 'XC':
                if conngui_xc >= maxgui_xc:
                        return 'xcusers:%d' % maxgui_xc
        else:
                if conngui_sb >= maxgui_sb:
                        return 'sbusers:%d' % maxgui_sb
        return None


def connect_user(userinfo, sessionid, iip, iport,
                 whoami, whatsmyos, tcpmode, state,
                 lastconnwins, socket):
        global conngui_xc, conngui_sb
        try:
                userinfo['sessionid'] = sessionid
                userinfo['sessiontimestamp'] = time.time()
                userinfo['logintimestamp'] = time.time()
                userinfo['ip'] = iip
                userinfo['port'] = iport
                userinfo['cticlienttype'] = whoami
                userinfo['cticlientos'] = whatsmyos
                userinfo['tcpmode'] = tcpmode
                userinfo['socket'] = socket
                # lastconnwins was introduced in the aim of forcing a new connection to take on for
                # a given user, however it might breed problems if the previously logged-in process
                # tries to reconnect ... unless we send something asking to Kill the process
                userinfo['lastconnwins'] = False # lastconnwins

                # we first check if 'state' has already been set for this customer, in which case
                # the CTI clients will be sent back this previous state
                if 'state' in userinfo:
                        futurestate = userinfo.get('state')
                        # only if it was a "defined" state anyway
                        if futurestate in allowed_states:
                                state = futurestate

                if state in allowed_states:
                        userinfo['state'] = state
                else:
                        log_debug(SYSLOG_WARNING, '(user %s) : state <%s> is not an allowed one => undefinedstate-connect'
                                  % (userinfo.get('user'), state))
                        userinfo['state'] = 'undefinedstate-connect'
                if whoami == 'XC':
                        conngui_xc = conngui_xc + 1
                else:
                        conngui_sb = conngui_sb + 1
        except Exception, exc:
                log_debug(SYSLOG_ERR, "--- exception --- connect_user %s : %s" %(str(userinfo), str(exc)))


def disconnect_user(userinfo):
        global conngui_xc, conngui_sb
        try:
                if 'sessionid' in userinfo:
                        if userinfo.get('cticlienttype') == 'XC':
                                conngui_xc = conngui_xc - 1
                        else:
                                conngui_sb = conngui_sb - 1
                        del userinfo['sessionid']
                        del userinfo['sessiontimestamp']
                        del userinfo['logintimestamp']
                        del userinfo['ip']
                        del userinfo['port']
                        del userinfo['cticlienttype']
                        del userinfo['cticlientos']
                        del userinfo['tcpmode']
                        del userinfo['socket']
                        if 'connection' in userinfo:
                                del userinfo['connection']
                        if 'monit' in userinfo:
                                del userinfo['monit']
        except Exception, exc:
                log_debug(SYSLOG_ERR, "--- exception --- disconnect_user %s : %s" %(str(userinfo), str(exc)))


## \brief Returns the user from the list.
# \param user searched for
# \return user found, otherwise None
def finduser(astname, user):
        if astname in userlist:
                u = userlist[astname].get(user)
        else:
                u = None
        return u

class FaxRequestHandler(SocketServer.StreamRequestHandler):
        def handle(self):
                threading.currentThread().setName('fax-%s:%d' %(self.client_address[0], self.client_address[1]))
                filename = 'astfaxsend-' + ''.join(random.sample(__alphanums__, 10)) + "-" + hex(int(time.time()))
                tmpfilepath = PATH_SPOOL_ASTERISK_TMP + '/' + filename
                faxfilepath = PATH_SPOOL_ASTERISK_FAX + '/' + filename + ".tif"
                tmpfiles = [tmpfilepath]

                try:
                        file_definition = self.rfile.readline().strip()
                        log_debug(SYSLOG_INFO, 'fax : received <%s>' % file_definition)
                        a = self.rfile.read()
                        z = open(tmpfilepath, 'w')
                        z.write(a)
                        z.close()
                        log_debug(SYSLOG_INFO, 'fax : received %d bytes stored into %s' % (len(a), tmpfilepath))
                        params = file_definition.split()
                        for p in params:
                                [var, val] = p.split('=')
                                if var == 'number':
                                        number = val
                                elif var == 'context':
                                        context = val
                                elif var == 'astid':
                                        astid = val
                                elif var == 'hide':
                                        hide = val

                        if astid in faxbuffer:
                                [dummyme, myconn] = faxbuffer[astid].pop()

                        if hide == "0":
                                callerid = configs[astid].faxcallerid
                        else:
                                callerid = 'anonymous'

                        reply = 'ko;unknown'
                        comm = commands.getoutput('file -b %s' % tmpfilepath)
                        brieffile = ' '.join(comm.split()[0:2])
                        if brieffile == 'PDF document,':
                                log_debug(SYSLOG_INFO, 'fax : the file received is a PDF one : converting to TIFF/F')
                                reply = 'ko;convert-pdftif'
                                ret = os.system("%s -o %s %s" % (PDF2FAX, faxfilepath, tmpfilepath))
                        else:
                                reply = 'ko;filetype'
                                log_debug(SYSLOG_WARNING, 'fax : the file received is a <%s> one : format not supported' % brieffile)
                                ret = -1

                        if ret == 0:
                                if os.path.exists(PATH_SPOOL_ASTERISK_FAX):
                                        try:
                                                reply = 'ko;AMI'
                                                ret = AMI_array_user_commands[astid].txfax(PATH_SPOOL_ASTERISK_FAX, filename, callerid, number, context)

                                                if ret:
                                                        reply = 'ok;'
                                        except Exception, exc:
                                                log_debug(SYSLOG_ERR, '--- exception --- (fax handler - AMI) : %s' %(str(exc)))
                                else:
                                        reply = 'ko;exists-pathspool'
                                        log_debug(SYSLOG_INFO, 'directory %s does not exist - could not send fax' %(PATH_SPOOL_ASTERISK_FAX))

                        if reply == 'ok;':
                                # filename is actually an identifier.
                                faxclients[filename] = myconn
                                reply = 'queued;'

                        if myconn[0] == 'udp':
                                myconn[1].sendto('faxsent=%s\n' % reply, (myconn[2], myconn[3]))
                        else:
                                myconn[1].send('faxsent=%s\n' % reply)
                except Exception, exc:
                        log_debug(SYSLOG_ERR, "--- exception --- (fax handler - global) : %s" %(str(exc)))

                for tmpfile in tmpfiles:
                        os.unlink(tmpfile)
                        log_debug(SYSLOG_INFO, "faxhandler : removed %s" % tmpfile)


## \class LoginHandler
# \brief The clients connect to this in order to obtain a valid session id.
# This could be enhanced to support a more complete protocol
# supporting commands coming from the client in order to pilot asterisk.
class LoginHandler(SocketServer.StreamRequestHandler):
        def logintalk(self):
                [user, port, state, astid] = ['', '', '', '']
                replystr = "ERROR"
                debugstr = "LoginRequestHandler (TCP) : client = %s:%d" %(self.client_address[0], self.client_address[1])
                loginargs = self.rfile.readline().strip().split(' ') # loginargs should be "[LOGIN <asteriskname>/sip<nnn> <XC@X11> <version>]"
                nloginargs = len(loginargs)
                if nloginargs != 4 or loginargs[0] != 'LOGIN':
                        replystr = "ERROR version_client:%d;%d" % (clientversion, REQUIRED_CLIENT_VERSION)
                        debugstr += " / Client version Error %d < %d" %(clientversion, REQUIRED_CLIENT_VERSION)
                        return [replystr, debugstr], [user, port, state, astid]
                clientversion = int(loginargs[3])
                if clientversion < REQUIRED_CLIENT_VERSION:
                        replystr = "ERROR version_client:%d;%d" % (clientversion, REQUIRED_CLIENT_VERSION)
                        debugstr += " / Client version Error %d < %d" %(clientversion, REQUIRED_CLIENT_VERSION)
                        return [replystr, debugstr], [user, port, state, astid]

                if loginargs[1].find("/") >= 0:
                        astname_xivoc = loginargs[1].split("/")[0]
                        user = loginargs[1].split("/")[1]
                else:
                        replystr = "ERROR id_format"
                        debugstr += " / LOGIN error ID"
                        return [replystr, debugstr], [user, port, state, astid]
                
                whoami = ""
                whatsmyos = ""
                nwhoami = loginargs[2].split("@")
                whoami  = nwhoami[0]
                if len(nwhoami) == 2:
                        whatsmyos = nwhoami[1]
                if whoami not in ["XC", "SB"]:
                        log_debug(SYSLOG_WARNING, "WARNING : %s/%s attempts to log in from %s:%d but has given no meaningful XC/SB hint (%s)"
                                  %(astname_xivoc, user, self.client_address[0], self.client_address[1], whoami))
                if whatsmyos not in ["X11", "WIN", "MAC"]:
                        log_debug(SYSLOG_WARNING, "WARNING : %s/%s attempts to log in from %s:%d but has given no meaningful OS hint (%s)"
                                  %(astname_xivoc, user, self.client_address[0], self.client_address[1], whatsmyos))


                # asks for PASS
                self.wfile.write('Send PASS for authentication\r\n')
                list1 = self.rfile.readline().strip().split(' ')
                if list1[0] == 'PASS':
                        passwd = ""
                        if len(list1) > 1: passwd = list1[1]
                else:
                        replystr = "ERROR pass_format"
                        debugstr += " / PASS error"
                        return [replystr, debugstr], [user, port, state, astid]

                if astname_xivoc in configs:
                        astid = astname_xivoc
                else:
                        replystr = "ERROR asterisk_name"
                        debugstr += " / asterisk name <%s> unknown" % astname_xivoc
                        return [replystr, debugstr], [user, port, state, astid]
                userlist_lock[astname_xivoc].acquire()
                try:
                        userinfo = finduser(astname_xivoc, user)
                        goodpass = (userinfo != None) and (userinfo.get('passwd') == passwd)
                finally:
                        userlist_lock[astname_xivoc].release()

                if userinfo is None:
                        replystr = "ERROR user_not_found"
                        debugstr += " / USER <%s> on asterisk <%s>" %(user, astname_xivoc)
                        return [replystr, debugstr], [user, port, state, astid]
                if not goodpass:
                        replystr = "ERROR login_passwd"
                        debugstr += " / PASS KO (%s given) for %s on asterisk <%s>" %(passwd, user, astname_xivoc)
                        return [replystr, debugstr], [user, port, state, astid]
                
                # asks for PORT
                self.wfile.write('Send PORT command\r\n')
                list1 = self.rfile.readline().strip().split(' ')
                if len(list1) != 2 or list1[0] != 'PORT':
                        replystr = "ERROR PORT"
                        debugstr += " / PORT KO"
                        return [replystr, debugstr], [user, port, state, astid]
                port = list1[1]
                
                # asks for STATE
                self.wfile.write('Send STATE command\r\n')
                list1 = self.rfile.readline().strip().split(' ')
                if len(list1) != 2 or list1[0] != 'STATE':
                        replystr = "ERROR STATE"
                        debugstr += " / STATE KO"
                        return [replystr, debugstr], [user, port, state, astid]
                state = list1[1]
                
                capa_user = []
                userlist_lock[astname_xivoc].acquire()
                try:
                        reterror = check_user_connection(userinfo, whoami)
                        if reterror is None:
                                for capa in capabilities_list:
                                        if capa in map_capas and (map_capas[capa] & userinfo.get('capas')):
                                                capa_user.append(capa)

                                # TODO : random pas au top, faire generation de session id plus luxe
                                sessionid = '%u' % random.randint(0,999999999)
                                connect_user(userinfo, sessionid,
                                             self.client_address[0], port,
                                             whoami, whatsmyos, False, state,
                                             False, self.request.makefile('w'))

                                replystr = "OK SESSIONID %s " \
                                           "context:%s;phonenum:%s;capas:%s;" \
                                           "xivoversion:%s;version:%s;state:%s" \
                                           %(sessionid,
                                             userinfo.get('context'),
                                             userinfo.get('phonenum'),
                                             ",".join(capa_user),
                                             XIVOVERSION,
                                             __revision__,
                                             userinfo.get('state'))
                                if 'features' in capa_user:
                                        replystr += ';capas_features:%s' %(','.join(configs[astid].capafeatures))
                        else:
                                replystr = "ERROR %s" % reterror
                                debugstr += " / USER %s (%s)" %(user, reterror)
                                return [replystr, debugstr], [user, port, state, astid]

                finally:
                        userlist_lock[astname_xivoc].release()

                debugstr += " / user %s, port %s, state %s, astid %s, cticlient %s/%s : connected : %s" %(user, port, state, astid,
                                                                                                           whoami, whatsmyos,
                                                                                                           replystr)
                return [replystr, debugstr], [user, port, state, astid]


        def handle(self):
                threading.currentThread().setName('login-%s:%d' %(self.client_address[0], self.client_address[1]))
                try:
                        [rstr, dstr], [user, port, state, astid] = self.logintalk()
                        self.wfile.write(rstr + "\r\n")
                        log_debug(SYSLOG_INFO, dstr)
                        if rstr.split()[0] == 'OK' and astid in configs:
                                plist[astid].send_availstate_update(user, state)
                except Exception, exc:
                        log_debug(SYSLOG_ERR, "--- exception --- (login handler) : %s" %(str(exc)))


## \class IdentRequestHandler
# \brief Gives client identification to the profile pusher.
# The connection is kept alive so several requests can be made on the same open TCP connection.
class IdentRequestHandler(SocketServer.StreamRequestHandler):
        def handle(self):
                threading.currentThread().setName('ident-%s:%d' %(self.client_address[0], self.client_address[1]))
                line = self.rfile.readline().strip()
                log_debug(SYSLOG_INFO, "IdentRequestHandler (TCP) : client = %s:%d / <%s>"
                          %(self.client_address[0],
                            self.client_address[1],
                            line))
                retline = 'ERROR'
                action = ''
                # PUSH user callerid msg
                m = re.match('PUSH (\S+) (\S+) <(\S*)> ?(.*)', line)
                if m != None:
                        called = m.group(1)
                        callerid = m.group(2)
                        callerctx = m.group(3)
                        msg = m.group(4)
                        action = 'PUSH'
                else:
                        log_debug(SYSLOG_ERR, 'PUSH command <%s> invalid' % line)
                        return

                if callerctx in contexts_cl:
                        ctxinfo = contexts_cl.get(callerctx)
                else:
                        log_debug(SYSLOG_WARNING, 'WARNING - no section has been defined for the context <%s>' % callerctx)
                        ctxinfo = contexts_cl.get('')

                astid = ip_reverse_sht[self.client_address[0]]
		userlist_lock[astid].acquire()
		try:
			try:
				userinfo = finduser(astid, called)
                                state_userinfo = 'unknown'
                                
				if userinfo == None:
					log_debug(SYSLOG_INFO, '%s : User <%s> not found (Call)' % (astid, called))
				elif userinfo.has_key('ip') and userinfo.has_key('port') \
					 and userinfo.has_key('state') and userinfo.has_key('sessionid') \
					 and userinfo.has_key('sessiontimestamp'):
					if time.time() - userinfo.get('sessiontimestamp') > xivoclient_session_timeout:
                                                log_debug(SYSLOG_INFO, '%s : User <%s> session expired (Call)' % (astid, called))
                                                userinfo = None
					else:
						capalist = (userinfo.get('capas') & capalist_server)
						if (capalist & CAPA_CUSTINFO):
                                                        state_userinfo = userinfo.get('state')
                                                else:
                                                        userinfo = None
				else:
					log_debug(SYSLOG_WARNING, '%s : User <%s> session not defined (Call)' % (astid, called))
                                        userinfo = None

                                sipcid = "SIP/%s" % callerid
                                localdirinfo = None
                                if sipcid in plist[astid].normal:
                                        localdirinfo = [plist[astid].normal[sipcid].calleridfull,
                                                        plist[astid].normal[sipcid].calleridfirst,
                                                        plist[astid].normal[sipcid].calleridlast]
                                calleridname = sendfiche.sendficheasync(userinfo,
                                                                        ctxinfo,
                                                                        callerid,
                                                                        msg,
                                                                        xivoconf,
                                                                        localdirinfo)
                                retline = 'USER %s STATE %s CIDNAME %s' %(called, state_userinfo, calleridname)
			except Exception, exc:
                                log_debug(SYSLOG_ERR, "--- exception --- error push : %s" %(str(exc)))
				retline = 'ERROR PUSH %s' %(str(exc))
		finally:
			userlist_lock[astid].release()

                try:
                        log_debug(SYSLOG_INFO, "PUSH : replying <%s>" % retline)
                        self.wfile.write(retline + '\r\n')
                except Exception, exc:
                        # something bad happened.
                        log_debug(SYSLOG_ERR, '--- exception --- IdentRequestHandler/Exception : %s'
                                  % str(exc))
                        return


def update_availstate(me, state):
        astid    = me[0]
        username = me[1]
        do_state_update = False
        userlist_lock[astid].acquire()
        try:
                userinfo = finduser(astid, username)
                if userinfo != None:
                        if 'sessiontimestamp' in userinfo:
                                userinfo['sessiontimestamp'] = time.time()
                        if state in allowed_states:
                                userinfo['state'] = state
                        else:
                                log_debug(SYSLOG_WARNING, '%s : (user %s) : state <%s> is not an allowed one => undefinedstate-updated'
                                          % (astid, username, state))
                                userinfo['state'] = 'undefinedstate-updated'
                        do_state_update = True
        finally:
                userlist_lock[astid].release()

        if do_state_update:
                plist[astid].send_availstate_update(username, state)
        return ""


def parse_command_and_build_reply(me, myconn, icommand):
        repstr = ""
        astid    = me[0]
        username = me[1]
        context  = me[2]
        ucapa    = me[3]

        try:
                capalist = (ucapa & capalist_server)
                if icommand.name == 'history':
                        if (capalist & CAPA_HISTORY):
                                repstr = build_history_string(icommand.args[0],
                                                              icommand.args[1],
                                                              icommand.args[2])
                elif icommand.name == 'directory-search':
                        if (capalist & CAPA_DIRECTORY):
                                repstr = build_customers(context, icommand.args)
                elif icommand.name == 'phones-list':
                        if (capalist & (CAPA_PEERS | CAPA_HISTORY)):
                                repstr = build_callerids_hints(icommand)
                elif icommand.name == 'phones-add':
                        if (capalist & (CAPA_PEERS | CAPA_HISTORY)):
                                repstr = build_callerids_hints(icommand)
                elif icommand.name == 'phones-del':
                        if (capalist & (CAPA_PEERS | CAPA_HISTORY)):
                                repstr = build_callerids_hints(icommand)
                elif icommand.name == 'availstate':
                        if (capalist & CAPA_PRESENCE):
                                repstr = update_availstate(me, icommand.args[0])
                elif icommand.name == 'database':
                        if (capalist & CAPA_DATABASE):
                                repstr = database_update(me, icommand.args)
                elif icommand.name == 'featuresget':
                        if (capalist & CAPA_FEATURES):
                                userlist_lock[astid].acquire()
                                try:
                                        if username in userlist[astid]:
                                                userlist[astid][username]['monit'] = icommand.args
                                finally:
                                        userlist_lock[astid].release()
                                repstr = build_features_get(icommand.args)
                elif icommand.name == 'featuresput':
                        if (capalist & CAPA_FEATURES):
                                repstr = build_features_put(icommand.args)
                elif icommand.name == 'faxsend':
                        if (capalist & CAPA_FAX):
                                if astid in faxbuffer:
                                        faxbuffer[astid].append([me, myconn])
                                repstr = "faxsend=%d" % port_fax
                elif icommand.name == 'message':
                        if (capalist & CAPA_MESSAGE):
                                send_msg_to_cti_clients(commandclass.message_srv2clt('%s/%s' %(astid, username),
                                                                                     '<%s>' % icommand.args[0]))
                elif icommand.name in ['originate', 'transfer', 'atxfer']:
                        if (capalist & CAPA_DIAL):
                                repstr = originate_or_transfer("%s/%s" %(astid, username),
                                                               [icommand.name, icommand.args[0], icommand.args[1]])
                elif icommand.name == 'hangup':
                        if (capalist & CAPA_DIAL):
                                repstr = hangup("%s/%s" %(astid, username),
                                                icommand.args[0])
        except Exception, exc:
                log_debug(SYSLOG_ERR, '--- exception --- (parse_command_and_build_reply) %s %s %s %s'
                          %(icommand.name, str(icommand.args), str(myconn), str(exc)))
        return repstr


def getboolean(fname, string):
        if string not in fname:
                return True
        else:
                value = fname.get(string)
                if value in ['false', '0', 'False']:
                        return False
                else:
                        return True


## \class KeepAliveHandler
# \brief It receives UDP datagrams and sends back a datagram containing whether
# "OK" or "ERROR <error-text>".
# It could be a good thing to give a numerical code to each error.
class KeepAliveHandler(SocketServer.DatagramRequestHandler):
        def handle(self):
                threading.currentThread().setName('keepalive-%s:%d' %(self.client_address[0], self.client_address[1]))
                requester = "%s:%d" %(self.client_address[0],self.client_address[1])
                log_debug(SYSLOG_INFO, "KeepAliveHandler    (UDP) : client = %s" % requester)
                astid = ''
                response = 'ERROR unknown'

                try:
                        ip = self.client_address[0]
                        list = self.request[0].strip().split(' ')
                        timestamp = time.time()
                        log_debug(SYSLOG_INFO, "received the message <%s> from %s" %(str(list), requester))

                        if len(list) < 4:
                                raise NameError, "not enough arguments (%d < 4)" %(len(list))
                        if list[0] != 'ALIVE' and list[0] != 'STOP' and list[0] != 'COMMAND':
                                raise NameError, "command %s not allowed" %(list[0])
                        if list[2] != 'SESSIONID':
                                raise NameError, "no SESSIONID defined"
                        [astname_xivoc, user] = list[1].split("/")
                        if astname_xivoc not in configs:
                                raise NameError, "unknown asterisk name <%s>" %astname_xivoc
                        
                        astid = astname_xivoc
                        sessionid = list[3]
                        capalist_user = 0

                        # first we check that the requester has the good sessionid and that its
                        # session has not expired
                        userlist_lock[astname_xivoc].acquire()
                        try:
                                userinfo = finduser(astname_xivoc, user)
                                if userinfo == None:
                                        raise NameError, "unknown user %s" %user
                                if userinfo.has_key('sessionid') and userinfo.has_key('ip') and userinfo.has_key('sessiontimestamp') \
                                       and sessionid == userinfo.get('sessionid') and ip == userinfo.get('ip') \
                                       and userinfo.get('sessiontimestamp') + xivoclient_session_timeout > timestamp:
                                        userinfo['sessiontimestamp'] = timestamp
                                        response = 'OK'
                                        capalist_user = userinfo.get('capas')
                                else:
                                        raise NameError, "session_expired"
                        finally:
                                userlist_lock[astname_xivoc].release()

                        if list[0] == 'ALIVE' and len(list) == 6 and list[4] == 'STATE':
                                # ALIVE user SESSIONID sessionid STATE state
                                state = list[5]
                                if state in allowed_states:
                                        userinfo['state'] = state
                                else:
                                        log_debug(SYSLOG_WARNING, '%s (user %s) : state <%s> is not an allowed one => undefinedstate-alive'
                                                  % (astid, user, state))
                                        userinfo['state'] = 'undefinedstate-alive'
                                plist[astname_xivoc].send_availstate_update(user, state)
                                response = 'OK'

                        elif list[0] == 'STOP' and len(list) == 4:
                                # STOP user SESSIONID sessionid
                                userlist_lock[astname_xivoc].acquire()
                                try:
                                        disconnect_user(userinfo)
                                        plist[astname_xivoc].send_availstate_update(user, "unknown")
                                finally:
                                        userlist_lock[astname_xivoc].release()
                                response = 'DISC'

                        elif list[0] == 'COMMAND':
                                try:
                                        userlist_lock[astname_xivoc].acquire()
                                        try:
                                                userinfo['connection'] = self
                                        finally:
                                                userlist_lock[astname_xivoc].release()

                                        command = commandclass.parsecommand(' '.join(list[4:]))
                                        if command.name in commandclass.get_list_commands_clt2srv():
                                                log_debug(SYSLOG_INFO, "%s is attempting a %s (UDP) : %s" %('requester', command.name, str(command.args)))
                                                response = parse_command_and_build_reply([astname_xivoc, user,
                                                                                          userinfo.get('context'), capalist_user],
                                                                                         ['udp', self.request[1], self.client_address[0], self.client_address[1]],
                                                                                         command)
                                except Exception, exc:
                                        log_debug(SYSLOG_ERR, "--- exception --- (command) %s" %str(exc))
                        else:
                                raise NameError, "unknown message <%s>" %str(list)
                except Exception, exc:
                        log_debug(SYSLOG_ERR, '--- exception --- KeepAliveHandler : %s' % str(exc))
                        response = 'ERROR %s' %(str(exc))

                # whatever has been received, we must reply something to the client who asked
                try:
                        log_debug(SYSLOG_INFO, "%s : replying <%s ...> (%d bytes) to %s" %(astname_xivoc, response[0:40], len(response), requester))
                        self.request[1].sendto(response + '\r\n', self.client_address)
                except socket:
                        log_debug(SYSLOG_ERR, "--- exception (socket) --- %s : sending UDP reply" %(astname_xivoc))
                except Exception, exc:
                        log_debug(SYSLOG_ERR, "--- exception --- %s : sending UDP reply : %s" %(astname_xivoc, str(exc)))


## \class MyTCPServer
# \brief TCPServer with the reuse address on.
class MyTCPServer(SocketServer.ThreadingTCPServer):
        allow_reuse_address = True


## \brief Handler for catching signals (in the main thread)
# \param signum signal number
# \param frame frame
# \return none
def sighandler(signum, frame):
        global askedtoquit
        print "--- signal", signum, "received : quits"
        for t in filter(lambda x: x.getName()<>"MainThread", threading.enumerate()):
                print "--- living thread <%s>" %(t.getName())
                t._Thread__stop()
        askedtoquit = True


## \brief Handler for catching signals (in the main thread)
# \param signum signal number
# \param frame frame
# \return none
def sighandler_reload(signum, frame):
        global askedtoquit
        print "--- signal", signum, "received : reloads"
        askedtoquit = False

# ==============================================================================
# ==============================================================================

def log_stderr_and_syslog(x):
        print >> sys.stderr, x
        syslogf(SYSLOG_ERR, x)

# ==============================================================================
# Main Code starts here
# ==============================================================================

# daemonize if not in debug mode
if not debug_mode:
        daemonize.daemonize(log_stderr_and_syslog, PIDFILE, True)
else:
        daemonize.create_pidfile_or_die(log_stderr_and_syslog, PIDFILE, True)

signal.signal(signal.SIGINT, sighandler)
signal.signal(signal.SIGTERM, sighandler)
signal.signal(signal.SIGHUP, sighandler_reload)

nreload = 0

while True: # loops over the reloads
        askedtoquit = False

        time_start = time.time()
        if nreload == 0:
                log_debug(SYSLOG_NOTICE, '# STARTING XIVO Daemon %s / svn %s # (0/3) Starting'
                          %(XIVOVERSION, __revision__))
        else:
                log_debug(SYSLOG_NOTICE, '# STARTING XIVO Daemon %s / svn %s # (0/3) Reloading (%d)'
                          %(XIVOVERSION, __revision__, nreload))
        nreload += 1
        
        # global default definitions
        commandset = 'xivosimple'
        port_login = 5000
        port_keepalive = 5001
        port_request = 5002
        port_ui_srv = 5003
        port_webi = 5004
        port_fax = 5020
        xivoclient_session_timeout = 60
        phonelist_update_period = 60
        capabilities_list = []
        capalist_server = 0
        asterisklist = []
        contextlist = []
        maxgui_sb = 3
        maxgui_xc = 10
        conngui_xc = 0
        conngui_sb = 0
        evt_filename = "/var/log/pf-xivo-cti-server/ami_events.log"
        gui_filename = "/var/log/pf-xivo-cti-server/gui.log"
        with_advert = False
        lstadd = {}
        lstdel = {}

        userinfo_by_requester = {}

        xivoconf = ConfigParser.ConfigParser()
        xivoconf.readfp(open(xivoconffile))
        xivoconf_general = dict(xivoconf.items("general"))

        # loads the general configuration
        if 'commandset' in xivoconf_general:
                commandset = xivoconf_general['commandset']
        if "port_fiche_login" in xivoconf_general:
                port_login = int(xivoconf_general["port_fiche_login"])
        if "port_fiche_keepalive" in xivoconf_general:
                port_keepalive = int(xivoconf_general["port_fiche_keepalive"])
        if "port_fiche_agi" in xivoconf_general:
                port_request = int(xivoconf_general["port_fiche_agi"])
        if "port_fax" in xivoconf_general:
                port_fax = int(xivoconf_general["port_fax"])
        if "port_switchboard" in xivoconf_general:
                port_ui_srv = int(xivoconf_general["port_switchboard"])
        if "port_webi" in xivoconf_general:
                port_webi = int(xivoconf_general["port_webi"])
        if "xivoclient_session_timeout" in xivoconf_general:
                xivoclient_session_timeout = int(xivoconf_general["xivoclient_session_timeout"])
        if "phonelist_update_period" in xivoconf_general:
                phonelist_update_period = int(xivoconf_general["phonelist_update_period"])
        if "capabilities" in xivoconf_general and xivoconf_general["capabilities"] != "":
                capabilities_list = xivoconf_general["capabilities"].split(",")
                for capa in capabilities_list:
                        if capa in map_capas: capalist_server |= map_capas[capa]
        if "asterisklist" in xivoconf_general:
                asterisklist = xivoconf_general["asterisklist"].split(",")
        if "maxgui_sb" in xivoconf_general:
                maxgui_sb = int(xivoconf_general["maxgui_sb"])
        if "maxgui_xc" in xivoconf_general:
                maxgui_xc = int(xivoconf_general["maxgui_xc"])
        if "evtfile" in xivoconf_general:
                evt_filename = xivoconf_general["evtfile"]
        if "guifile" in xivoconf_general:
                gui_filename = xivoconf_general["guifile"]

        if "advert" in xivoconf_general: with_advert = True

        cclass = xivo_commandsets.CommandClasses[commandset]
        commandclass = cclass()

        configs = {}
        save_for_next_packet_events = {}
        save_for_next_packet_status = {}
        faxbuffer = {}
        faxclients = {}
        ip_reverse_webi = {}
        ip_reverse_sht = {}

        # loads the configuration for each asterisk
        for i in xivoconf.sections():
                if i != 'general' and i in asterisklist:
                        xivoconf_local = dict(xivoconf.items(i))

                        localaddr = '127.0.0.1'
                        userlist_url = 'sso.php'
                        ipaddress = '127.0.0.1'
                        ipaddress_webi = '127.0.0.1'
                        extrachannels = ''
                        ami_port = 5038
                        ami_login = 'xivouser'
                        ami_pass = 'xivouser'
                        contexts = ''
                        userfeatures_db_uri = ''
                        cdr_db_uri = ''
                        realm = 'asterisk'
                        parkingnumber = '700'
                        faxcallerid = 'faxcallerid'
                        linkestablished = ''

                        if 'localaddr' in xivoconf_local:
                                localaddr = xivoconf_local['localaddr']
                        if 'userlisturl' in xivoconf_local:
                                userlist_url = xivoconf_local['userlisturl']
                        if 'ipaddress' in xivoconf_local:
                                ipaddress = xivoconf_local['ipaddress']
                        if 'ipaddress_webi' in xivoconf_local:
                                ipaddress_webi = xivoconf_local['ipaddress_webi']
                        if 'extrachannels' in xivoconf_local:
                                extrachannels = xivoconf_local['extrachannels']
                        if 'parkingnumber' in xivoconf_local:
                                parkingnumber = int(xivoconf_local['parkingnumber'])
                        if 'faxcallerid' in xivoconf_local:
                                faxcallerid = int(xivoconf_local['faxcallerid'])
                        if 'linkestablished' in xivoconf_local:
                                linkestablished = xivoconf_local['linkestablished']
                        if 'ami_port' in xivoconf_local:
                                ami_port = int(xivoconf_local['ami_port'])
                        if 'ami_login' in xivoconf_local:
                                ami_login = xivoconf_local['ami_login']
                        if 'ami_pass' in xivoconf_local:
                                ami_pass = xivoconf_local['ami_pass']
                        if 'contexts' in xivoconf_local:
                                contexts = xivoconf_local['contexts']
                                if contexts != '':
                                        for c in contexts.split(','):
                                                contextlist.append(c)
                        if 'userfeatures_db_uri' in xivoconf_local:
                                userfeatures_db_uri = xivoconf_local['userfeatures_db_uri']
                        if 'cdr_db_uri' in xivoconf_local:
                                cdr_db_uri = xivoconf_local['cdr_db_uri']
                        if 'realm' in xivoconf_local:
                                realm = xivoconf_local['realm']
                        for capauser, capadefs in xivoconf_local.iteritems():
                                if capauser.find('capas_') == 0:
                                        cuser = capauser[6:].split('/')
                                        cdefs = capadefs.split(',')

                        capafeatures = []
                        unallowed = []
                        if userfeatures_db_uri is not '':
                                conn = anysql.connect_by_uri(userfeatures_db_uri)
                                cursor = conn.cursor()
                                params = ['features']
                                columns = ('commented', 'context', 'name')
                                query = "SELECT ${columns} FROM extensions WHERE context = %s"
                                cursor.query(query,
                                             columns,
                                             params)
                                results = cursor.fetchall()
                                conn.close()
                                for res in results:
                                        if res[0] == 0:
                                                capafeatures.append(res[2])
                                        else:
                                                unallowed.append(res[2])
                        #print "%s : allowed     : %s" %(i, str(capafeatures))
                        #print "%s : not allowed : %s" %(i, str(unallowed))

                        astremote = AsteriskRemote(i,
                                                   userlist_url,
                                                   extrachannels,
                                                   localaddr,
                                                   ipaddress,
                                                   ipaddress_webi,
                                                   ami_port,
                                                   ami_login,
                                                   ami_pass,
                                                   contexts,
                                                   userfeatures_db_uri,
                                                   capafeatures,
                                                   cdr_db_uri,
                                                   realm,
                                                   parkingnumber,
                                                   faxcallerid,
                                                   linkestablished)
                        
                        configs[i] = astremote

                        if ipaddress not in ip_reverse_sht:
                                ip_reverse_sht[ipaddress] = i
                        else:
                                log_debug(SYSLOG_WARNING, 'WARNING - IP address already exists for asterisk <%s> - can not set it for <%s>'
                                          % (ip_reverse_sht[ipaddress], i))
                        if ipaddress_webi not in ip_reverse_webi:
                                ip_reverse_webi[ipaddress_webi] = i
                        else:
                                log_debug(SYSLOG_WARNING, 'WARNING - IP address (WEBI) already exists for asterisk <%s> - can not set it for <%s>'
                                          % (ip_reverse_webi[ipaddress_webi], i))
                        save_for_next_packet_events[i] = ''
                        save_for_next_packet_status[i] = ''
                        faxbuffer[i] = []

        contexts_cl = {}
        contexts_cl[''] = Context()
        # loads the configuration for each context
        for i in xivoconf.sections():
                if i != 'general' and i in contextlist:
                        xivoconf_local = dict(xivoconf.items(i))
                        dir_db_uri = ''
                        dir_db_sqltable = ''
                        dir_db_sheetui = ''

                        if 'dir_db_uri' in xivoconf_local:
                                dir_db_uri = xivoconf_local['dir_db_uri']
                        if 'dir_db_sqltable' in xivoconf_local:
                                dir_db_sqltable = xivoconf_local['dir_db_sqltable']
                        if 'dir_db_sheetui' in xivoconf_local:
                                dir_db_sheetui = xivoconf_local['dir_db_sheetui']

                        z = Context()
                        z.setUri(dir_db_uri)
                        z.setSqlTable(dir_db_sqltable)
                        z.setSheetUi(dir_db_sheetui)

                        fnames = {}
                        snames = {}
                        for field in xivoconf_local:
                                if field.find('dir_db_search') == 0:
                                        ffs = field.split('.')
                                        if len(ffs) == 3:
                                                if ffs[1] not in fnames:
                                                        fnames[ffs[1]] = {}
                                                fnames[ffs[1]][ffs[2]] = xivoconf_local[field]
                                elif field.find('dir_db_sheet') == 0:
                                        ffs = field.split('.')
                                        if len(ffs) == 3:
                                                if ffs[1] not in snames:
                                                        snames[ffs[1]] = {}
                                                snames[ffs[1]][ffs[2]] = xivoconf_local[field]
                                        elif len(ffs) == 2 and ffs[1] == 'callidmatch':
                                                z.setSheetCallidMatch(xivoconf_local[field].split(','))

                        search_vfields = []
                        search_mfields = []
                        for fname in fnames.itervalues():
                                if 'display' in fname and 'match' in fname:
                                        dbnames = fname['match']
                                        if dbnames != '':
                                                dbnames_list = dbnames.split(',')
                                                for dbn in dbnames_list:
                                                        if dbn not in search_mfields:
                                                                search_mfields.append(dbn)
                                                keepspaces = getboolean(fname, 'space')
                                                search_vfields.append([fname['display'], dbnames_list, keepspaces])
                        z.setSearchValidFields(search_vfields)
                        z.setSearchMatchingFields(search_mfields)
                        
                        sheet_vfields = []
                        sheet_mfields = []
                        for fname in snames.itervalues():
                                if 'field' in fname and 'match' in fname:
                                        dbnames = fname['match']
                                        if dbnames != '':
                                                dbnames_list = dbnames.split(',')
                                                for dbn in dbnames_list:
                                                        if dbn not in sheet_mfields:
                                                                sheet_mfields.append(dbn)
                                                sheet_vfields.append([fname['field'], dbnames_list, False])

                        z.setSheetValidFields(sheet_vfields)
                        z.setSheetMatchingFields(sheet_mfields)
                        
                        contexts_cl[i] = z

        # Instantiate the SocketServer Objects.
        loginserver = MyTCPServer(('', port_login), LoginHandler)
        # TODO: maybe we should listen on only one interface (localhost ?)
        requestserver = MyTCPServer(('', port_request), IdentRequestHandler)
        # Do we need a Threading server for the keep alive ? I dont think so,
        # packets processing is non blocking so thread creation/start/stop/delete
        # overhead is not worth it.
        # keepaliveserver = SocketServer.ThreadingUDPServer(('', port_keepalive), KeepAliveHandler)
        keepaliveserver = SocketServer.UDPServer(('', port_keepalive), KeepAliveHandler)
        faxserver = MyTCPServer(('', port_fax), FaxRequestHandler)

        # We have three sockets to listen to so we cannot use the
        # very easy to use SocketServer.serve_forever()
        # So select() is what we need. The SocketServer.handle_request() calls
        # won't block the execution. In case of the TCP servers, they will
        # spawn a new thread, in case of the UDP server, the request handling
        # process should be fast. If it isnt, use a threading UDP server ;)
        ins = [loginserver.socket, requestserver.socket, keepaliveserver.socket, faxserver.socket]

        if debug_mode:
                # opens the evtfile for output in append mode
                try:
                        evtfile = open(evt_filename, 'a')
                except Exception, exc:
                        print "Could not open %s in append mode : %s" %(evt_filename,exc)
                        evtfile = False
                # opens the guifile for output in append mode
                try:
                        guifile = open(gui_filename, 'a')
                except Exception, exc:
                        print "Could not open %s in append mode : %s" %(gui_filename,exc)
                        guifile = False

        # user list initialized empty
        userlist = {}
        userlist_lock = {}
        
        plist = {}
        AMI_array_events_fd = {}
        AMI_array_user_commands = {}
        update_userlist = {}
        lastrequest_time = {}

        log_debug(SYSLOG_INFO, "the monitored asterisk's is/are : %s" % str(asterisklist))
        log_debug(SYSLOG_INFO, "# STARTING XIVO Daemon # (1/2) AMI socket connections + fetch Web Services")

        tcpopens_sb = []
        tcpopens_webi = []

        for astid in configs:
                try:
                        plist[astid] = PhoneList(astid)
                        userlist[astid] = {}
                        userlist_lock[astid] = threading.Condition()

                        update_userlist[astid] = False

                        update_amisocks(astid)
                        plist[astid].check_connected_accounts()
                        update_phonelist(astid)
                        lastrequest_time[astid] = time.time()
                except Exception, exc:
                        log_debug(SYSLOG_ERR, '--- exception --- %s : failed while setting lists and sockets : %s'
                                  %(astid, str(exc)))

        xdal = None
        # xivo daemon advertising
        if with_advert:
                xda = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                xda.bind(("", 5010))
                xda.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                # xda.sendto('xivo_daemon:%d:%s' %(len(configs), configs.join(':')), ("255.255.255.255", 5011))

                xdal = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                xdal.bind(("", 5011))
                ins.append(xdal)

        log_debug(SYSLOG_INFO, "# STARTING XIVO Daemon # (2/2) listening UI sockets")
        # opens the listening socket for UI connections
        UIsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        UIsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        UIsock.bind(("", port_ui_srv))
        UIsock.listen(10)
        ins.append(UIsock)
        # opens the listening socket for WEBI/CLI connections
        WEBIsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        WEBIsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        WEBIsock.bind(("", port_webi))
        WEBIsock.listen(10)
        ins.append(WEBIsock)

        # Receive messages
        while not askedtoquit:
                try:
                        [i, o, e] = select.select(ins, [], [], phonelist_update_period)
                except Exception, exc:
                        if askedtoquit:
                                try:
                                        send_msg_to_cti_clients("ERROR server_stopped")
                                        os.unlink(PIDFILE)
                                except Exception, exc:
                                        print exc
                                if debug_mode:
                                        # Close files and sockets
                                        evtfile.close()
                                        guifile.close()
                                for t in filter(lambda x: x.getName()<>"MainThread", threading.enumerate()):
                                        print "--- (stop) killing thread <%s>" %(t.getName())
                                        t._Thread__stop()
                                sys.exit(5)
                        else:
                                send_msg_to_cti_clients("ERROR server_reloaded")
                                askedtoquit = True
                                for s in ins:
                                        s.close()
                                for t in filter(lambda x: x.getName()<>"MainThread", threading.enumerate()):
                                        print "--- (reload) the thread <%s> remains" %(t.getName())
                                        # t._Thread__stop() # does not work in reload case (vs. stop case)
                                continue
                if i:
                        if loginserver.socket in i:
                                loginserver.handle_request()
                        elif requestserver.socket in i:
                                requestserver.handle_request()
                        elif keepaliveserver.socket in i:
                                keepaliveserver.handle_request()
                        elif faxserver.socket in i:
                                faxserver.handle_request()
                        # these AMI connections are used in order to manage AMI commands with incoming events
                        elif filter(lambda j: j in AMI_array_events_fd.itervalues(), i):
                                res = filter(lambda j: j in AMI_array_events_fd.itervalues(), i)[0]
                                for astid, val in AMI_array_events_fd.iteritems():
                                        if val is res: break
                                try:
                                        a = AMI_array_events_fd[astid].readline() # (BUFSIZE_ANY)
                                        if len(a) == 0: # end of connection from server side : closing socket
                                                log_debug(SYSLOG_INFO, "%s : AMI : CLOSING" % astid)
                                                strmessage = commandclass.dmessage_srv2clt('AMI OFF for <%s>' % astid)
                                                send_msg_to_cti_clients(strmessage)
                                                AMI_array_events_fd[astid].close()
                                                ins.remove(AMI_array_events_fd[astid])
                                                del AMI_array_events_fd[astid]
                                        else:
                                                handle_ami_event(astid, a)
                                except Exception, exc:
                                        log_debug(SYSLOG_ERR, "--- exception --- AMI <%s> : %s" % (astid, str(exc)))
                        # the new UI (SB) connections are catched here
                        elif UIsock in i:
                                [conn, UIsockparams] = UIsock.accept()
                                log_debug(SYSLOG_INFO, "TCP (SB)  socket opened on   %s:%s" %(UIsockparams[0],str(UIsockparams[1])))
                                commandclass.connected_srv2clt(conn, 1)
                                # appending the opened socket to the ones watched
                                ins.append(conn)
                                conn.setblocking(0)
                                tcpopens_sb.append([conn, UIsockparams[0], UIsockparams[1]])
                        # the new UI (WEBI) connections are catched here
                        elif WEBIsock in i:
                                [conn, WEBIsockparams] = WEBIsock.accept()
                                log_debug(SYSLOG_INFO, "TCP (WEBI) socket opened on   %s:%s" %(WEBIsockparams[0],str(WEBIsockparams[1])))
                                # appending the opened socket to the ones watched
                                ins.append(conn)
                                conn.setblocking(0)
                                tcpopens_webi.append([conn, WEBIsockparams[0], WEBIsockparams[1]])
                        # open UI (SB) connections
                        elif filter(lambda j: j[0] in i, tcpopens_sb):
                                conn = filter(lambda j: j[0] in i, tcpopens_sb)[0]
                                try:
                                        manage_tcp_connection(conn, True)
                                except Exception, exc:
                                        log_debug(SYSLOG_ERR, '--- exception --- XC/SB tcp connection : %s' % str(exc))
                        # open UI (WEBI) connections
                        elif filter(lambda j: j[0] in i, tcpopens_webi):
                                conn = filter(lambda j: j[0] in i, tcpopens_webi)[0]
                                try:
                                        manage_tcp_connection(conn, False)
                                except Exception, exc:
                                        log_debug(SYSLOG_ERR, '--- exception --- WEBI tcp connection : %s' % str(exc))
                        # advertising from other xivo_daemon's around
                        elif xdal in i:
                                [data, addrsip] = xdal.recvfrom(BUFSIZE_UDP)
                                log_debug(SYSLOG_INFO, 'a xivo_daemon is around : <%s>' % str(addrsip))
                        else:
                                log_debug(SYSLOG_INFO, "unknown socket <%s>" % str(i))

                        for astid in configs:
                                if (time.time() - lastrequest_time[astid]) > phonelist_update_period or update_userlist[astid]:
                                        lastrequest_time[astid] = time.time()
                                        log_debug(SYSLOG_INFO, '%s : update_phonelist (computed timeout) %s'
                                                  % (astid, time.strftime("%H:%M:%S", time.localtime())))
                                        try:
                                                update_amisocks(astid)
                                                plist[astid].check_connected_accounts()
                                                update_phonelist(astid)
                                                update_services(astid)
                                                update_userlist[astid] = False
                                        except Exception, exc:
                                                log_debug(SYSLOG_ERR, '--- exception --- %s : failed while updating lists and sockets (computed timeout) : %s'
                                                          %(astid, str(exc)))
                                        
                else: # when nothing happens on the sockets, we fall here sooner or later
                        log_debug(SYSLOG_INFO, 'update_phonelist (select s timeout) %s'
                                  % time.strftime("%H:%M:%S", time.localtime()))
                        for astid in configs:
                                lastrequest_time[astid] = time.time()
                                try:
                                        update_amisocks(astid)
                                        plist[astid].check_connected_accounts()
                                        update_phonelist(astid)
                                except Exception, exc:
                                        log_debug(SYSLOG_ERR, '--- exception --- %s : failed while updating lists and sockets (select s timeout) : %s'
                                                  %(astid, str(exc)))

        log_debug(SYSLOG_NOTICE, 'after askedtoquit loop')
