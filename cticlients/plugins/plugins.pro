# build projects contained in subdirectories
TEMPLATE = subdirs
SUBDIRS  = xletweb \
           videoxlet \
           xletnull \
           conference \
           history \
           switchboard \
           identity
win32:SUBDIRS += outlook
