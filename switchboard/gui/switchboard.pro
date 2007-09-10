######################################################################
# Automatically generated by qmake (2.01a) ven. f�vr. 23 12:17:56 2007
######################################################################
#
# $Revision$
# $Date$
#

VERSION = $$system(svn info -r HEAD | tail -3 | head -1 | sed "s/.*:.//")
VERSTR = '\\"$${VERSION}\\"'  # place quotes around the version string
DEFINES += SVNVER=\"$${VERSTR}\" # create a VER macro containing the version string

XCDIR = ../../xivoclient/gui
TEMPLATE = app
TARGET = 
DEPENDPATH += .
INCLUDEPATH += . $${XCDIR}
CONFIG -= debug
CONFIG += static

# Input
HEADERS += mainwidget.h switchboardwindow.h
HEADERS += baseengine.h
HEADERS += callwidget.h callstackwidget.h peerwidget.h
HEADERS += astchannel.h peerslayout.h searchpanel.h
HEADERS += peeritem.h logeltwidget.h logwidget.h dialpanel.h
HEADERS += directorypanel.h displaymessages.h
HEADERS += peerchannel.h extendedtablewidget.h
HEADERS += xivoconsts.h
HEADERS += $${XCDIR}/servicepanel.h $${XCDIR}/popup.h $${XCDIR}/urllabel.h $${XCDIR}/xmlhandler.h
HEADERS += $${XCDIR}/remotepicwidget.h $${XCDIR}/confwidget.h $${XCDIR}/identitydisplay.h

SOURCES += main.cpp mainwidget.cpp switchboardwindow.cpp
SOURCES += baseengine.cpp
SOURCES += callwidget.cpp callstackwidget.cpp peerwidget.cpp
SOURCES += astchannel.cpp peerslayout.cpp searchpanel.cpp
SOURCES += peeritem.cpp logeltwidget.cpp logwidget.cpp dialpanel.cpp
SOURCES += directorypanel.cpp displaymessages.cpp
SOURCES += peerchannel.cpp extendedtablewidget.cpp
SOURCES += $${XCDIR}/servicepanel.cpp $${XCDIR}/popup.cpp $${XCDIR}/urllabel.cpp $${XCDIR}/xmlhandler.cpp
SOURCES += $${XCDIR}/remotepicwidget.cpp $${XCDIR}/confwidget.cpp $${XCDIR}/identitydisplay.cpp

QT += network
QT += xml
RESOURCES += appli.qrc
TRANSLATIONS = switchboard_fr.ts
RC_FILE = appli.rc
