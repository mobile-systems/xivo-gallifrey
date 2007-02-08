#ifndef __CONFWIDGET_H__
#define __CONFWIDGET_H__

#include <QWidget>
#include <QDialog>
#include <QLineEdit>
#include "engine.h"

/*! \brief Configuration Window
 *
 * This Widget enables the user to edit the connection
 * parameters to the identification server */
/* could be a QDialog instead of QWidget */
//class ConfWidget: public QWidget
class ConfWidget: public QDialog
{
	Q_OBJECT
public:
	//! Constructor
	/*!
	 * Construct the widget and its layout.
	 * Fill widgets with values got from the Engine object.
	 * Once constructed, the Widget is ready to be shown.
	 * \param engine	related Engine object where parameters will be modified
	 * \param parent	parent QWidget
	 */
	ConfWidget(Engine *engine, QWidget *parent = 0);
private slots:
	//! Save the configuration to the Engine object and close
	void saveAndClose();
private:
	QLineEdit *m_lineip;		//!< IP/hostname of the server
	QLineEdit *m_lineport;		//!< port of the server
	QLineEdit *m_linelogin;		//!< user login
	QLineEdit *m_linepasswd;	//!< user password
	Engine *m_engine;			//!< Engine object parameters are commited to
};

#endif

