# -*- coding: utf-8 -*-
"""
/***************************************************************************
 SDEllipse
                                 A QGIS plugin
 Create a standard deviational ellipse for a point layer
                              -------------------
        begin                : 2016-05-20
        git sha              : $Format:%H$
        copyright            : (C) 2016 by Håvard Tveite, NMBU
        email                : havard.tveite@nmbu.no
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from PyQt4.QtCore import QSettings, QTranslator, qVersion
from PyQt4.QtCore import QCoreApplication, QFileInfo
from PyQt4.QtGui import QAction, QIcon
from qgis.core import QGis, QgsMapLayer
# Initialize Qt resources from file resources.py
import resources_rc
# Import the code for the dialog
from SDEllipse_dialog import SDEllipseDialog
import os.path


# The following user interface components are referenced (in run()):
# "InputLayer", "progressBar"
class SDEllipse:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        pluginPath = QFileInfo(os.path.realpath(__file__)).path()
        # initialize locale using the QGIS locale
        locale = QSettings().value('locale/userLocale')[0:2]
        if QFileInfo(pluginPath).exists():
            locale_path = os.path.join(
                pluginPath,
                'i18n',
                '{}.qm'.format(locale))
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Create the dialog (after translation) and keep reference
        self.dlg = SDEllipseDialog(self.iface)

        # Declare instance attributes
        self.menu = self.tr(u'&Standard deviational ellipse')

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('Histogram', message)

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        icon_path = ':/plugins/SDEllipse/icon.png'
        # Create action that will start plugin configuration
        self.action = QAction(
            QIcon(icon_path),
            self.menu, self.iface.mainWindow())
        # connect the action to the run method
        self.action.triggered.connect(self.run)
        # Add toolbar icon
        if hasattr(self.iface, 'addVectorToolBarIcon'):
            self.iface.addVectorToolBarIcon(self.action)
        else:
            self.iface.addToolBarIcon(self.action)
        # Add menu item
        if hasattr(self.iface, 'addPluginToVectorMenu'):
            self.iface.addPluginToVectorMenu(self.menu, self.action)
        else:
            self.iface.addPluginToMenu(self.menu, self.action)

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        # Remove the plugin menu item
        if hasattr(self.iface, 'removePluginVectorMenu'):
            self.iface.removePluginVectorMenu(self.menu, self.action)
        else:
            self.iface.removePluginMenu(self.menu, self.action)
        # Remove the plugin toolbar icon
        if hasattr(self.iface, 'removeVectorToolBarIcon'):
            self.iface.removeVectorToolBarIcon(self.action)
        else:
            self.iface.removeToolBarIcon(self.action)

    def run(self):
        # Do some initialisations
        # The progressbar
        self.dlg.progressBar.setValue(0.0)
        # The input layer
        self.dlg.InputLayer.clear()
        for alayer in self.iface.legendInterface().layers():
            # Look for vector point layers
            if (alayer.type() == QgsMapLayer.VectorLayer and
                      (alayer.wkbType() == QGis.WKBPoint
                       or alayer.wkbType() == QGis.WKBPoint25D
                       #or alayer.wkbType() == QGis.WKBMultiPoint
               )):
                self.dlg.InputLayer.addItem(alayer.name(), alayer.id())
        """Run method that performs all the real work"""
        # show the dialog
        self.dlg.show()
