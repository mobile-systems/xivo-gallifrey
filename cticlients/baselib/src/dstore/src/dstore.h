#ifndef __DYN_TREE__
#define __DYN_TREE__
#include <QDebug>
#include <QVariant>
#include <QVariantMap>
#include <QVariantList>
#include <QStringList>
#include <QString>
#include <QList>
#include <QRegExp>
#include <QHash>
#include <stdio.h>

/*! Represent the kind of event that happened on a node monitored */
enum DStoreEvent { NODE_POPULATED, /*!< node or descendant has changed */
                   NODE_REMOVED /*!< a node got removed */ };

enum NodeType {INNER, LEAF};

class DStoreCallback;
class DStore;
class DStoreNode;
class VMapNode;
class VNode;

//! A DStoreNode this is the base type of every node
class DStoreNode
{
    public:
        /*! \return node unique identifier */
        qlonglong uid() const { return m_uid; };
        /*! \return parent node */
        VMapNode* parent() const { return m_parent; }
        /*! \return node type */
        NodeType type() const { return m_type; }
        /*! \return node name */
        QString name() const { return m_name; }
        /*! \return the fullpath of this node constructed */
        QString path() const;

        /*! make a pretty printed representation of a node and its 
           possible descendants
          \param  node  the node to represent
          \param  tc tab count, number of space to prepend at each level
          \param  showUid should we also display every unique node id ?
          \return QString, a string representation of the tree
         */
        static QString pp(const DStoreNode &node, int tc=4, int showUid=0);

    private:
        virtual DStoreNode* clone(DStore* tree, VMapNode *parent=NULL, int ripDad=0) = 0;
        virtual void destroy(DStore *tree, int recurseOverNodes);


        DStoreNode(const QString &name, NodeType type, VMapNode *parent);
        void construct(DStore *tree);
        void setParent(VMapNode *node) { m_parent = node; };
        VMapNode* muteToVMapNode(DStore *tree);

        QString m_name;
        qlonglong m_uid;
        VMapNode *m_parent;
        NodeType m_type;
        virtual ~DStoreNode() {};


    friend class VMapNode;
    friend class VNode;
    friend class DStore;
};

//! A VMapNode is a node, made to contain other node
class VMapNode : public DStoreNode
{
    public:
        /*!
          \return number of child node
         */
        int count();
        /*!
          \return child node names
         */
        QStringList nodeNames() const;
        /*! Does a child Node with name «x» exist ?
          \param nodeName x
          \return
                  - 0: no
                  - 1: yes
        */
        int nodeExist(const QString &nodeName);
        DStoreNode* node(const QString &) const;
        VNode* getVNode(const QString &path);
        //~VMapNode() { qDebug() << "~VMapNode" << this; }

    private:
        virtual DStoreNode* clone(DStore* tree, VMapNode *parent=NULL, int ripDad=0);
        virtual void destroy(DStore *, int destroyNode);
        VMapNode(const QString &name, VMapNode *parent, DStore *tree, const QVariantMap &node=QVariantMap());
        void destroyNodeList();
        int remove(const QString &);
        static VMapNode* getNode(const QString &, VMapNode *, DStore *);
        void populate(const QVariantMap &map, DStore *tree);
        void addNode(const QString &name, DStoreNode *node);
        void takeChild(VMapNode *node);

        QMap<QString, DStoreNode**> *m_nodeMap;

    friend class DStoreNode;
    friend class DStore;
};

//! A VNode is a leaf node, a node which isn't made to hold any other node
class VNode : public DStoreNode
{
    public:
        /*!
          \return QVariant, convert it using toString(), toInt(),.. as usual.
         */
        QVariant variant() const { return m_variant; };

    private:
        virtual DStoreNode* clone(DStore* tree, VMapNode *parent=NULL, int ripDad=0);
        virtual void destroy(DStore *, int);
        QVariant m_variant;
        VNode(const QString &name, VMapNode *parent, DStore *tree, const QVariant &);

    friend class DStoreNode;
    friend class VMapNode;
    friend class DStore;
};

//! A DStore, stand for Data Store help you to keep and manage you data in a tree
class DStore
{
    public:
        DStore();
        ~DStore();

        /*!
          \param  path  a request to extract a tree part
          \return DStore *, a tree part
         */
        DStore* extract(const QString &path);

        /*!
          This method is there to allow you to create some inner node
          A shell command equivalent, would be mkdir -p
          \param path   the path be created
          \param from   specify from where the path should be created
         */
        VMapNode* mkPath(const QString &path, VMapNode *from=NULL);
        /*!
          This method is there to allow you to remove a tree part
          \param path   the path to be removed
         */
        void rmPath(const QString &path);
        /*!
          This method is there to allow you to add/replace a bunch of data in your 
          DStore

          \param path   the base path where your tree fragment
                        should be put
          \param value  a tree fragment, you can of course insert multiple node at once
                        at different tree level by using QVariantMap properly nested.
                        
         */
        void populate(const QString &path, const QVariant &value);
        /*! 
          \return VMapNode * DStore root node
         */
        VMapNode* root() const { return m_root; };
        /*!
          When you are initially filling or destroying a DStore, you probably don't 
          want to call every QObject slots you might have binded to monitor change
          for a performance reason, isn't it?
          \param block  should signals be blocked ?
                             - 0: no 
                             - 1: yes (default when called without argument)
         */
        void blockSignal(int block=1) { m_blockSignal = block; };
        /*!
          This method is there to allow you to monitor tree changes
          ( a node was removed/added or changed ).\n
          A same path can be monitored by multiple QObject

          \param path     the base path from where you need to be informed 
                          if your node or a subnode was
                              - added / modified
                              - removed
          \param receiver a class which inherit QObject
          \param method   a Qt SLOT ( so use Qt SLOT() macro )\n
                          Your QObject slot protype should look as the following:
                          \code void treeChange(const QString &path, DStoreEvent event); \endcode
          \sa #DStoreEvent
         */
        void onChange(const QString &path, QObject *receiver, const char *method);
        


    private:
        void dynamicInvocation(const QString &path, DStoreEvent event);

        enum Op0p { IS_EQUAL };
        DStore* filter(Op0p op, const QString &path, const QVariant &value=QVariant());
        void registerNode(DStoreNode *);
        void unregisterNode(DStoreNode *);
        DStoreNode* getNode(qlonglong uid);
        DStoreNode* getNode(const QString &path);
        static QString sanitize(const QString &path);
        int getUid();
        qlonglong m_4genUid;
        QHash<QString, qlonglong> m_path2uid;
        QHash<qlonglong, DStoreNode*> m_uid2node;
        int m_blockSignal;
        VMapNode *m_root;
        QMultiHash<QString, DStoreCallback*> m_callbackList;

    friend class DStoreNode;
    friend class VMapNode;
    friend class VMap;
};

// INTERNAL & PRIVATE (structure to manage callback on QObject)
class DStoreCallback
{
    public:
        DStoreCallback(QObject *on, const char *slot);
        ~DStoreCallback();
        void call(const QString &path, DStoreEvent event);

    private:
        QObject *on;
        char *slot;
};

#endif
