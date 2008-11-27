/* XIVO CTI clients
 * Copyright (C) 2007, 2008  Proformatique
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License version 2 for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA.
 *
 * Linking the Licensed Program statically or dynamically with other
 * modules is making a combined work based on the Licensed Program. Thus,
 * the terms and conditions of the GNU General Public License version 2
 * cover the whole combination.
 *
 * In addition, as a special exception, the copyright holders of the
 * Licensed Program give you permission to combine the Licensed Program
 * with free software programs or libraries that are released under the
 * GNU Library General Public License version 2.0 or GNU Lesser General
 * Public License version 2.1 or any later version of the GNU Lesser
 * General Public License, and with code included in the standard release
 * of OpenSSL under a version of the OpenSSL license (with original SSLeay
 * license) which is identical to the one that was published in year 2003,
 * or modified versions of such code, with unchanged license. You may copy
 * and distribute such a system following the terms of the GNU GPL
 * version 2 for the Licensed Program and the licenses of the other code
 * concerned, provided that you include the source code of that other code
 * when and as the GNU GPL version 2 requires distribution of source code.
*/

/* $Revision: 4701 $
 * $Date: 2008-11-17 12:39:36 +0100 (lun, 17 nov 2008) $
 */

#include <QDebug>
#include <QFrame>
#include <QGridLayout>
#include <QLabel>
#include <QPushButton>
#include <QScrollArea>
#include <QVariant>

#include "agentspanel_next.h"
#include "userinfo.h"

/*! \brief Constructor
 */
AgentsPanelNext::AgentsPanelNext(const QVariant & optionmap,
                                 QWidget * parent)
        : QWidget(parent)
{
        m_gui_buttonsize = 10;
        
	m_gridlayout = new QGridLayout(this);
        m_title1 = new QLabel(tr("Agent"), this);
        m_title2 = new QLabel(tr("Record"), this);
        m_title3 = new QLabel(tr("Listen"), this);
        m_title4 = new QLabel(tr("On Line"), this);
        m_title5 = new QLabel(tr("Presence"), this);
        m_title6 = new QLabel(tr("Logged"), this);
        m_title7 = new QLabel(tr("Joined\nqueues"), this);
        m_title8 = new QLabel(tr("Paused\nqueues"), this);
        
        m_gridlayout->addWidget(m_title1, 0, 0, 1, 2, Qt::AlignLeft );
        m_gridlayout->addWidget(m_title2, 0, 2, 1, 1, Qt::AlignCenter );
        m_gridlayout->addWidget(m_title3, 0, 3, 1, 1, Qt::AlignCenter );
        m_gridlayout->addWidget(m_title4, 0, 4, 1, 1, Qt::AlignCenter );
        m_gridlayout->addWidget(m_title5, 0, 6, 1, 1, Qt::AlignCenter );
        m_gridlayout->addWidget(m_title6, 0, 8, 1, 2, Qt::AlignCenter );
        m_gridlayout->addWidget(m_title7, 0, 11, 1, 2, Qt::AlignCenter );
        m_gridlayout->addWidget(m_title8, 0, 14, 1, 2, Qt::AlignCenter );
        m_gridlayout->setColumnStretch( 16, 1 );
        m_gridlayout->setRowStretch( 100, 1 );
        m_gridlayout->setVerticalSpacing(0);
        
        setGuiOptions(optionmap);
}

AgentsPanelNext::~AgentsPanelNext()
{
        // qDebug() << "AgentsPanelNext::~AgentsPanelNext()";
}

void AgentsPanelNext::setGuiOptions(const QVariant & optionmap)
{
        if(optionmap.toMap().contains("fontname") && optionmap.toMap().contains("fontsize"))
                m_gui_font = QFont(optionmap.toMap()["fontname"].toString(),
                                   optionmap.toMap()["fontsize"].toInt());
        if(optionmap.toMap().contains("iconsize"))
                m_gui_buttonsize = optionmap.toMap()["iconsize"].toInt();
        
        // setFont(m_gui_font);
        m_title1->setFont(m_gui_font);
        m_title2->setFont(m_gui_font);
        m_title3->setFont(m_gui_font);
        m_title4->setFont(m_gui_font);
        m_title5->setFont(m_gui_font);
        m_title6->setFont(m_gui_font);
        m_title7->setFont(m_gui_font);
        m_title8->setFont(m_gui_font);
}

void AgentsPanelNext::setUserInfo(const UserInfo * ui)
{
        m_userinfo = ui;
}

void AgentsPanelNext::updateAgentPresence(const QString & agentname, const QVariant & presencestatus)
{
        // qDebug() << "AgentsPanelNext::updateAgentPresence" << agentname << presencestatus;
        if(agentname.size() > 0)
                if(m_agent_presence.contains(agentname)) {
                        QColor color = QColor(presencestatus.toMap()["color"].toString());
                        QPixmap * m_square = new QPixmap(m_gui_buttonsize, m_gui_buttonsize);
                        m_square->fill(color);
                        m_agent_presence[agentname]->setPixmap(QPixmap(* m_square));
                }
}

void AgentsPanelNext::updatePeerAgent(const QString &,
                                  const QString & what,
                                  const QStringList & params)
{
        if(what != "agentstatus")
                return;
        // qDebug() << "AgentsPanelNext::updatePeerAgent()" << what << params;
        QString command = params[0];
        if(command == "queuememberstatus") {
                QString agname = params[2];
                if(m_agent_labels.contains(agname)) {
                        QString qname = params[3];
                        QString status = params[4];
                        if(status == "1") {
                                QPixmap * m_square = new QPixmap(m_gui_buttonsize, m_gui_buttonsize);
                                m_square->fill(Qt::green);
                                m_agent_logged_status[agname]->setPixmap(QPixmap(* m_square));
                                m_agent_logged_status[agname]->setProperty("logged", true);
                                m_agent_logged_action[agname]->setIcon(QIcon(":/images/cancel.png"));
                        } else if(status == "5") {
                                QPixmap * m_square = new QPixmap(m_gui_buttonsize, m_gui_buttonsize);
                                m_square->fill(Qt::red);
                                m_agent_logged_status[agname]->setPixmap(QPixmap(* m_square));
                                m_agent_logged_status[agname]->setProperty("logged", false);
                                m_agent_logged_action[agname]->setIcon(QIcon(":/images/button_ok.png"));
                        } else if(status == "3") {
                                qDebug() << "AgentsPanelNext::updatePeerAgent()" << what << status;
                        } else {
                                qDebug() << "AgentsPanelNext::updatePeerAgent()" << what << status;
                        }
                }
        } else if(command == "joinqueue") {
                QString astid = params[1];
                QString agname = params[2];
                if((params.size() == 5) && m_agent_labels.contains(agname)) {
                        QString qname = params[3];
                        if(! m_agent_joined_list[agname].contains(qname)) {
                                QPixmap * m_square = new QPixmap(m_gui_buttonsize, m_gui_buttonsize);
                                m_square->fill(Qt::green);
                                m_agent_joined_list[agname].append(qname);
                                // m_agent_joined_status[agname]->setPixmap(QPixmap(* m_square));
                                
                                QString pstatus = params[4];
                                if(pstatus == "0") {
                                        if(! m_agent_paused_list[agname].contains(qname)) {
                                                QPixmap * m_square = new QPixmap(m_gui_buttonsize, m_gui_buttonsize);
                                                m_square->fill(Qt::green);
                                                m_agent_paused_list[agname].append(qname);
                                                // m_agent_paused_status[agname]->setPixmap(QPixmap(* m_square));
                                        }
                                } else {
                                        if(m_agent_paused_list[agname].contains(qname)) {
                                                m_agent_paused_list[agname].removeAll(qname);
                                        }
                                }
                        }
                        m_agent_joined_number[agname]->setText(QString::number(m_agent_joined_list[agname].size()));
                        m_agent_paused_number[agname]->setText(QString::number(m_agent_joined_list[agname].size()
                                                                               - m_agent_paused_list[agname].size()));
                }
        } else if(command == "leavequeue") {
                QString astid = params[1];
                QString agname = params[2];
                if(m_agent_labels.contains(agname)) {
                        QString qname = params[3];
                        if(m_agent_joined_list[agname].contains(qname)) {
                                m_agent_joined_list[agname].removeAll(qname);
                                m_agent_paused_list[agname].removeAll(qname);
                        }
                        m_agent_joined_number[agname]->setText(QString::number(m_agent_joined_list[agname].size()));
                        m_agent_paused_number[agname]->setText(QString::number(m_agent_joined_list[agname].size()
                                                                               - m_agent_paused_list[agname].size()));
                }
        } else if(command == "unpaused") {
                QString astid = params[1];
                QString agname = params[2];
                if(m_agent_labels.contains(agname)) {
                        QString qname = params[3];
                        if(! m_agent_paused_list[agname].contains(qname))
                                m_agent_paused_list[agname].append(qname);
                        m_agent_paused_number[agname]->setText(QString::number(m_agent_joined_list[agname].size()
                                                                               - m_agent_paused_list[agname].size()));
                }
        } else if(command == "paused") {
                QString astid = params[1];
                QString agname = params[2];
                if(m_agent_labels.contains(agname)) {
                        QString qname = params[3];
                        if(m_agent_paused_list[agname].contains(qname))
                                m_agent_paused_list[agname].removeAll(qname);
                        m_agent_paused_number[agname]->setText(QString::number(m_agent_joined_list[agname].size()
                                                                               - m_agent_paused_list[agname].size()));
                }
        } else if(command == "agentlogin") {
                QString astid = params[1];
                QString agname = params[2];
                if(m_agent_labels.contains(agname)) {
                        QPixmap * m_square = new QPixmap(m_gui_buttonsize, m_gui_buttonsize);
                        m_square->fill(Qt::green);
                        m_agent_logged_status[agname]->setPixmap(QPixmap(* m_square));
                        m_agent_logged_status[agname]->setProperty("logged", true);
                        m_agent_logged_action[agname]->setIcon(QIcon(":/images/cancel.png"));
                }
        } else if(command == "agentlogout") {
                QString astid = params[1];
                QString agname = params[2];
                if(m_agent_labels.contains(agname)) {
                        QPixmap * m_square = new QPixmap(m_gui_buttonsize, m_gui_buttonsize);
                        m_square->fill(Qt::red);
                        m_agent_logged_status[agname]->setPixmap(QPixmap(* m_square));
                        m_agent_logged_status[agname]->setProperty("logged", false);
                        m_agent_logged_action[agname]->setIcon(QIcon(":/images/button_ok.png"));
                }
        } else if((command == "agentlink") || (command == "phonelink")) {
                QString astid = params[1];
                QString agname = params[2];
                QPixmap * m_square = new QPixmap(m_gui_buttonsize, m_gui_buttonsize);
                m_square->fill(Qt::green);
                if(m_agent_busy.contains(agname))
                        if(astid == m_agent_busy[agname]->property("astid").toString())
                                m_agent_busy[agname]->setPixmap(QPixmap(* m_square));
        } else if((command == "agentunlink") || (command == "phoneunlink")) {
                QString astid = params[1];
                QString agname = params[2];
                QPixmap * m_square = new QPixmap(m_gui_buttonsize, m_gui_buttonsize);
                m_square->fill(Qt::gray);
                if(m_agent_busy.contains(agname))
                        if(astid == m_agent_busy[agname]->property("astid").toString())
                                m_agent_busy[agname]->setPixmap(QPixmap(* m_square));
        }
}

void AgentsPanelNext::setAgentList(const QVariant & alist)
{
        // qDebug() << "AgentsPanelNext::setAgentList()" << alist;
        QPixmap * m_square = new QPixmap(m_gui_buttonsize, m_gui_buttonsize);
        QVariantMap alistmap = alist.toMap();
        QString astid = alistmap["astid"].toString();
        QStringList agentids = alistmap["newlist"].toMap().keys();
        agentids.sort();
        foreach (QString agnum, agentids) {
                QVariant properties = alistmap["newlist"].toMap()[agnum].toMap()["properties"];
                QVariantList agqjoined = alistmap["newlist"].toMap()[agnum].toMap()["queues"].toList();
                QString agstatus = properties.toMap()["status"].toString();
                QString agfullname = properties.toMap()["name"].toString();
                QString phonenum = properties.toMap()["phonenum"].toString();
                bool link = properties.toMap()["link"].toBool();
                qDebug() << "AgentsPanelNext::setAgentList()" << agnum << agstatus << agfullname << phonenum << link;
                
                if(! m_agent_labels.contains(agnum)) {
                        QFrame * qvline1 = new QFrame(this);
                        qvline1->setFrameShape(QFrame::VLine);
                        qvline1->setLineWidth(1);
                        QFrame * qvline2 = new QFrame(this);
                        qvline2->setFrameShape(QFrame::VLine);
                        qvline2->setLineWidth(1);
                        QFrame * qvline3 = new QFrame(this);
                        qvline3->setFrameShape(QFrame::VLine);
                        qvline3->setLineWidth(1);
                        QFrame * qvline4 = new QFrame(this);
                        qvline4->setFrameShape(QFrame::VLine);
                        qvline4->setLineWidth(1);
                        
                        m_agent_labels[agnum] = new QLabel(agfullname + " (" + agnum + ")", this);
                        m_agent_more[agnum] = new QPushButton(this);
                        m_agent_more[agnum]->setProperty("astid", astid);
                        m_agent_more[agnum]->setProperty("agentid", agnum);
                        m_agent_more[agnum]->setProperty("action", "changeagent");
                        connect( m_agent_more[agnum], SIGNAL(clicked()),
                                 this, SLOT(agentClicked()));
                        
                        m_agent_record[agnum] = new QPushButton(this);
                        m_agent_record[agnum]->setProperty("astid", astid);
                        m_agent_record[agnum]->setProperty("agentid", agnum);
                        m_agent_record[agnum]->setProperty("action", "record");
                        connect( m_agent_record[agnum], SIGNAL(clicked()),
                                 this, SLOT(agentClicked()));
                        
                        m_agent_listen[agnum] = new QPushButton(this);
                        m_agent_listen[agnum]->setProperty("astid", astid);
                        m_agent_listen[agnum]->setProperty("agentid", agnum);
                        m_agent_listen[agnum]->setProperty("action", "listen");
                        connect( m_agent_listen[agnum], SIGNAL(clicked()),
                                 this, SLOT(agentClicked()));
                        
                        m_agent_busy[agnum] = new QLabel(this);
                        m_agent_busy[agnum]->setProperty("astid", astid);
                        m_agent_presence[agnum] = new QLabel(this);
                        m_agent_logged_status[agnum] = new QLabel(this);
                        m_agent_logged_action[agnum] = new QPushButton(this);
                        m_agent_logged_action[agnum]->setProperty("astid", astid);
                        m_agent_logged_action[agnum]->setProperty("agentid", agnum);
                        m_agent_logged_action[agnum]->setProperty("action", "loginoff");
                        connect( m_agent_logged_action[agnum], SIGNAL(clicked()),
                                 this, SLOT(agentClicked()));
                        
                        m_agent_joined_number[agnum] = new QLabel(this);
                        // m_agent_joined_status[agnum] = new QLabel(this);
                        m_agent_paused_number[agnum] = new QLabel(this);
                        // m_agent_paused_status[agnum] = new QLabel(this);
                        
                        m_agent_more[agnum]->setIconSize(QSize(m_gui_buttonsize, m_gui_buttonsize));
                        m_agent_more[agnum]->setIcon(QIcon(":/images/add.png"));
                        m_agent_record[agnum]->setIconSize(QSize(m_gui_buttonsize, m_gui_buttonsize));
                        m_agent_record[agnum]->setIcon(QIcon(":/images/player_stop.png"));
                        m_agent_listen[agnum]->setIconSize(QSize(m_gui_buttonsize, m_gui_buttonsize));
                        m_agent_listen[agnum]->setIcon(QIcon(":/images/player_play.png"));
                        m_agent_logged_action[agnum]->setIconSize(QSize(m_gui_buttonsize, m_gui_buttonsize));
                        
                        if(link)
                                m_square->fill(Qt::green);
                        else
                                m_square->fill(Qt::gray);
                        m_agent_busy[agnum]->setPixmap(QPixmap(* m_square));
                        m_square->fill(Qt::gray);
                        m_agent_presence[agnum]->setPixmap(QPixmap(* m_square));
                        
                        if(agstatus == "AGENT_IDLE") {
                                m_square->fill(Qt::green);
                                m_agent_logged_action[agnum]->setIcon(QIcon(":/images/cancel.png"));
                                m_agent_logged_status[agnum]->setProperty("logged", true);
                        } else if(agstatus == "AGENT_LOGGEDOFF") {
                                m_square->fill(Qt::red);
                                m_agent_logged_action[agnum]->setIcon(QIcon(":/images/button_ok.png"));
                                m_agent_logged_status[agnum]->setProperty("logged", false);
                        } else {
                                qDebug() << "AgentsPanelNext::setAgentList() unknown status" << agstatus;
                        }
                        m_agent_logged_status[agnum]->setPixmap(QPixmap(* m_square));
                        
                        foreach (QVariant qv, agqjoined) {
                                QStringList agqprops = qv.toStringList();
                                if(agqprops.size() > 2) {
                                        QString qname = agqprops[0];
                                        QString pstatus = agqprops[1];
                                        QString xstatus = agqprops[2];
                                        m_agent_joined_list[agnum] << qname;
                                        if(pstatus == "0")
                                                m_agent_paused_list[agnum] << qname;
                                        // } else if(agqprops.size() == 1) {
                                }
                        }
                        int njoined = m_agent_joined_list[agnum].size();
                        m_agent_joined_number[agnum]->setText(QString::number(njoined));

                        int nunpaused = m_agent_paused_list[agnum].size();
                        m_agent_paused_number[agnum]->setText(QString::number(njoined - nunpaused));

                        int colnum = 0;
                        int linenum = m_agent_labels.size();
                        m_gridlayout->addWidget( m_agent_labels[agnum], linenum, colnum++, Qt::AlignLeft );
                        m_gridlayout->addWidget( m_agent_more[agnum], linenum, colnum++, Qt::AlignCenter );
                        m_gridlayout->addWidget( m_agent_record[agnum], linenum, colnum++, Qt::AlignCenter );
                        m_gridlayout->addWidget( m_agent_listen[agnum], linenum, colnum++, Qt::AlignCenter );
                        m_gridlayout->addWidget( m_agent_busy[agnum], linenum, colnum++, Qt::AlignCenter );
                        m_gridlayout->addWidget( qvline1, linenum, colnum++, Qt::AlignHCenter );
                        m_gridlayout->addWidget( m_agent_presence[agnum], linenum, colnum++, Qt::AlignCenter );
                        m_gridlayout->addWidget( qvline2, linenum, colnum++, Qt::AlignHCenter );
                        m_gridlayout->addWidget( m_agent_logged_status[agnum], linenum, colnum++, Qt::AlignCenter );
                        m_gridlayout->addWidget( m_agent_logged_action[agnum], linenum, colnum++, Qt::AlignLeft );
                        m_gridlayout->addWidget( qvline3, linenum, colnum++, Qt::AlignHCenter );
                        m_gridlayout->addWidget( m_agent_joined_number[agnum], linenum, colnum++, Qt::AlignRight );
                        // m_gridlayout->addWidget( m_agent_joined_status[agnum], linenum, colnum++, Qt::AlignCenter );
                        colnum++;
                        m_gridlayout->addWidget( qvline4, linenum, colnum++, Qt::AlignHCenter );
                        m_gridlayout->addWidget( m_agent_paused_number[agnum], linenum, colnum++, Qt::AlignRight );
                        // m_gridlayout->addWidget( m_agent_paused_status[agnum], linenum, colnum++, Qt::AlignCenter );
                        colnum++;
                }
        }
}


void AgentsPanelNext::agentClicked()
{
        // qDebug() << "AgentsPanelNext::agentClicked()" << sender()->property("agentid");
        QString astid   = sender()->property("astid").toString();
        QString agentid = sender()->property("agentid").toString();
        QString action  = sender()->property("action").toString();
        if(action == "changeagent")
                changeWatchedAgent(astid + " " + agentid, true);
        else if(action == "loginoff") {
                if(m_agent_logged_status[agentid]->property("logged").toBool())
                        agentAction("logout " + astid + " " + agentid);
                else
                        agentAction("login " + astid + " " + agentid);
        } else if(action == "listen") {
                agentAction("listen " + astid + " " + agentid);
                m_agent_listen[agentid]->setStyleSheet("QPushButton {background: #fbb638}");
        } else if(action == "record") {
                agentAction("record " + astid + " " + agentid);
                m_agent_record[agentid]->setProperty("action", "stoprecord");
                m_agent_record[agentid]->setStyleSheet("QPushButton {background: #fbb638}");
        } else if(action == "stoprecord") {
                agentAction("stoprecord " + astid + " " + agentid);
                m_agent_record[agentid]->setProperty("action", "record");
                m_agent_record[agentid]->setStyleSheet("");
        }
}


void AgentsPanelNext::setAgentStatus(const QString & status)
{
        QStringList newstatuses = status.split("/");
        // qDebug() << "AgentsPanelNext::setAgentstatus()" << newstatuses;
        if (newstatuses.size() == 4) {
                QString command = newstatuses[0];
                if (command == "queuechannels") {
                        QString astid = newstatuses[1];
                        QString queuename = newstatuses[2];
                        QString busyness = newstatuses[3];
                }
        }
}