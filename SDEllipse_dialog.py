# -*- coding: utf-8 -*-
"""
/***************************************************************************
 SDEllipseDialog
                                 A QGIS plugin
 Create standard deviational ellipse
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

# User interface input components:
#   selectedFeatures_cb: Checkbox to determine if selection is to be used
#   useWeights_cb: Checkbox to determine if weights are to be used
#   InputLayer: The input layer
#   inputField: The field for weights

import os
import csv

from math import pow, log, sin, cos, pi, sqrt
from PyQt4 import uic
from PyQt4.QtCore import SIGNAL, QObject, QThread, QCoreApplication
from PyQt4.QtCore import QPointF, QLineF, QRectF, QSettings
from PyQt4.QtCore import QPyNullVariant, Qt, QVariant
from PyQt4.QtGui import QDialog, QDialogButtonBox, QFileDialog
from PyQt4.QtGui import QGraphicsLineItem, QGraphicsRectItem
from PyQt4.QtGui import QGraphicsTextItem
from PyQt4.QtGui import QGraphicsScene, QBrush, QPen, QColor
from PyQt4.QtGui import QGraphicsView
from PyQt4.QtGui import QButtonGroup
from PyQt4.QtGui import QAbstractButton
from qgis.core import QgsMessageLog, QgsMapLayerRegistry, QgsMapLayer
from qgis.core import QGis, QgsPoint, QgsFeature, QgsGeometry, QgsVectorLayer
from qgis.core import *
from qgis.gui import QgsMessageBar

from SDEllipse_engine import Worker

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'SDEllipse.ui'))


class SDEllipseDialog(QDialog, FORM_CLASS):

    def __init__(self, iface, parent=None):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)

        # Some constants
        self.SDELLIPSE = self.tr('SD Ellipse')
        self.CANCEL = self.tr('Cancel')
        self.CLOSE = self.tr('Close')
        self.OK = self.tr('OK')

        """Constructor."""
        super(SDEllipseDialog, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        self.method_group = QButtonGroup()
        self.method_group.addButton(self.yuill_rb)
        self.method_group.addButton(self.crimestat_rb)
        self.method_group.buttonClicked[QAbstractButton].connect(self.methodChanged)
        okButton = self.button_box.button(QDialogButtonBox.Ok)
        okButton.setText(self.OK)
        cancelButton = self.button_box.button(QDialogButtonBox.Cancel)
        cancelButton.setText(self.CANCEL)
        cancelButton.setEnabled(False)
        closeButton = self.button_box.button(QDialogButtonBox.Close)
        closeButton.setText(self.CLOSE)

        # Connect signals
        okButton.clicked.connect(self.startWorker)
        cancelButton.clicked.connect(self.killWorker)
        closeButton.clicked.connect(self.reject)
        self.cumulative = False
        inpIndexCh = self.InputLayer.currentIndexChanged['QString']
        inpIndexCh.connect(self.layerchanged)
        fieldIndexCh = self.inputField.currentIndexChanged['QString']
        fieldIndexCh.connect(self.fieldchanged)

        QObject.disconnect(self.button_box, SIGNAL("rejected()"),
                           self.reject)

        # Set instance variables
        self.worker = None
        self.inputlayerid = None
        self.layerlistchanging = False
        self.selectedFeatures_cb.setChecked(True)
        self.useWeights_cb.setChecked(False)
        self.result = None

    def startWorker(self):
        #self.showInfo('Ready to start worker')
        self.degfreedCorr = self.degfreedcorr_cb.isChecked()
        self.crimestatCorr = self.crimestatcorr_cb.isChecked()
        # Get the input layer
        layerindex = self.InputLayer.currentIndex()
        layerId = self.InputLayer.itemData(layerindex)
        inputlayer = QgsMapLayerRegistry.instance().mapLayer(layerId)
        self.featureCount = inputlayer.featureCount()
        if inputlayer is None:
            self.showError(self.tr('No input layer defined'))
            return
        if self.featureCount == 0:
            self.showError(self.tr('No features in input layer'))
            #self.scene.clear()
            return
        if (self.useWeights_cb.isChecked() and
            self.inputField.count() == 0):
            self.showError(self.tr('Missing numerical field'))
            #self.scene.clear()
            return
        fieldindex = self.inputField.currentIndex()
        fieldname = self.inputField.itemData(fieldindex)
        if (not self.useWeights_cb.isChecked()):
            fieldname = None
        self.result = None
        self.SDLayer = inputlayer
        self.method = 1
        if self.yuill_rb.isChecked():
            self.method = 1
        elif self.crimestat_rb.isChecked():
            self.method = 2
        # create a new worker instance
        worker = Worker(inputlayer,
                        self.selectedFeatures_cb.isChecked(),
                        fieldname, self.method)
        # start the worker in a new thread
        thread = QThread(self)
        worker.moveToThread(thread)
        worker.finished.connect(self.workerFinished)
        worker.error.connect(self.workerError)
        worker.status.connect(self.workerInfo)
        worker.progress.connect(self.progressBar.setValue)
        #worker.progress.connect(self.aprogressBar.setValue)
        thread.started.connect(worker.run)
        thread.start()
        self.thread = thread
        self.worker = worker
        self.button_box.button(QDialogButtonBox.Ok).setEnabled(False)
        self.button_box.button(QDialogButtonBox.Close).setEnabled(False)
        self.button_box.button(QDialogButtonBox.Cancel).setEnabled(True)
        self.InputLayer.setEnabled(False)
        self.inputField.setEnabled(False)

    def workerFinished(self, ok, ret):
        """Handles the output from the worker and cleans up after the
           worker has finished."""
        # clean up the worker and thread
        self.worker.deleteLater()
        self.thread.quit()
        self.thread.wait()
        self.thread.deleteLater()
        # remove widget from the message bar (pop)
        #self.iface.messageBar().popWidget(self.messageBar)
        if ok and ret is not None:
            self.result = ret
            # Draw the ellipse
            self.drawEllipse()
        else:
            # notify the user that something went wrong
            if not ok:
                self.showError(self.tr('Aborted') + '!')
            else:
                self.showError(self.tr('Not able to create ellipse') + '!')
        # Update the user interface
        self.progressBar.setValue(0.0)
        self.button_box.button(QDialogButtonBox.Ok).setEnabled(True)
        self.button_box.button(QDialogButtonBox.Close).setEnabled(True)
        self.button_box.button(QDialogButtonBox.Cancel).setEnabled(False)
        self.InputLayer.setEnabled(True)
        self.inputField.setEnabled(True)
        # end of workerFinished(self, ok, ret)

    def workerError(self, exception_string):
        """Report an error from the worker."""
        self.showError(exception_string)

    def workerInfo(self, message_string):
        """Report an info message from the worker."""
        QgsMessageLog.logMessage(self.tr('Worker') + ': ' +
                                 message_string,
                                 self.SDELLIPSE,
                                 QgsMessageLog.INFO)

    def killWorker(self):
        """Kill the worker thread."""
        if self.worker is not None:
            QgsMessageLog.logMessage(self.tr('Killing worker'),
                                     self.SDELLIPSE,
                                     QgsMessageLog.INFO)
            self.worker.kill()

    # Implement the reject method to have the possibility to avoid
    # exiting the dialog when cancelling
    def reject(self):
        """Reject override."""
        # exit the dialog
        QDialog.reject(self)

    def drawEllipse(self):
        #self.showInfo('Result: ' + str(self.result))
        meanx = self.result[0]
        meany = self.result[1]
        angle1 = self.result[2]
        angle2 = self.result[3]
        SD1 = self.result[4]
        SD2 = self.result[5]
        if self.crimestatCorr and self.method != 2:
            SD1 = SD1 * sqrt(2)
            SD2 = SD2 * sqrt(2)
        if self.degfreedCorr and self.method != 2:
            SD1 = SD1 * self.featureCount / (self.featureCount - 2)
            SD2 = SD2 * self.featureCount / (self.featureCount - 2)
            #SD1 = SD1 * self.featureCount / (self.featureCount-1)
            #SD2 = SD2 * self.featureCount / (self.featureCount-1)
        # Find the major and minor axis
        majoraxisangle = angle1
        minoraxisangle = angle2
        majorSD = SD2
        minorSD = SD1
        if SD2 < SD1:
            majoraxisangle = angle2
            minoraxisangle = angle1
            majorSD = SD1
            minorSD = SD2
        #self.showInfo('Major axis angle: ' + str(majoraxisangle) +
        #              ' Major axis length: ' + str(majorSD) +
        #              ' Minor axis length: ' + str(minorSD))
        # Create the memory layer for the ellipse
        sdefields = []
        sdefields.append(QgsField("meanx", QVariant.Double))
        sdefields.append(QgsField("meany", QVariant.Double))
        sdefields.append(QgsField("majorangle", QVariant.Double))
        sdefields.append(QgsField("minorangle", QVariant.Double))
        sdefields.append(QgsField("majorsd", QVariant.Double))
        sdefields.append(QgsField("minorsd", QVariant.Double))
        layeruri = 'Polygon?'
        #layeruri = 'linestring?'
        layeruri = (layeruri + 'crs=' +
                    str(self.SDLayer.dataProvider().crs().authid()))
        memSDlayer = QgsVectorLayer(layeruri, self.OutputLayerName.text(),
                                    "memory")
#        memSDlayer = QgsVectorLayer(layeruri, self.SDLayer.name() +
#                                    "_SDE", "memory")
        memSDlayer.startEditing()  # ?
        for field in sdefields:
            memSDlayer.dataProvider().addAttributes([field])  # ?

        sdfeature = QgsFeature()
        theta1 = majoraxisangle
        points = []
        step = pi / 180
        t = 0.0
        while t < 2 * pi:
            p1 = QPointF(meanx + majorSD * cos(t) * cos(majoraxisangle) -
                         minorSD * sin(t) * sin(majoraxisangle),
                         meany + majorSD * cos(t) * sin(majoraxisangle) +
                         minorSD * sin(t) * cos(majoraxisangle))
            points.append(QgsPoint(p1))
            t = t + step
        sdfeature.setGeometry(QgsGeometry.fromPolygon([points]))
        #sdfeature.setGeometry(QgsGeometry.fromPolyline(points))
        attrs = [meanx, meany, majoraxisangle, minoraxisangle,
                 majorSD, minorSD]
        sdfeature.setAttributes(attrs)
        memSDlayer.dataProvider().addFeatures([sdfeature])
        memSDlayer.commitChanges()  # ?
        memSDlayer.updateExtents()
        QgsMapLayerRegistry.instance().addMapLayers([memSDlayer])
        return

    def layerchanged(self, number=0):
        """Do the necessary updates after a layer selection has
           been changed."""
        self.layerselectionactive = True
        layerindex = self.InputLayer.currentIndex()
        layerId = self.InputLayer.itemData(layerindex)
        self.inputlayerid = layerId
        inputlayer = QgsMapLayerRegistry.instance().mapLayer(layerId)
        while self.inputField.count() > 0:
            self.inputField.removeItem(0)
        self.layerselectionactive = False
        # Get the numerical fields
        if inputlayer is not None:
            provider = inputlayer.dataProvider()
            attribs = provider.fields()
            if str(type(attribs)) != "<type 'dict'>":
                atr = {}
                for i in range(attribs.count()):
                    atr[i] = attribs.at(i)
                attrdict = atr
            for id, attrib in attrdict.iteritems():
                # Check for numeric attribute
                if attrib.typeName().upper() in ('REAL', 'INTEGER', 'INT4',
                                                 'INT8', 'FLOAT4'):
                    self.inputField.addItem(attrib.name(), attrib.name())
            if (self.inputField.count() > 0):
                self.button_box.button(QDialogButtonBox.Ok).setEnabled(True)
            self.OutputLayerName.setText(
                "SDE_" +
                self.method_group.checkedButton().text() +
                "_" + self.InputLayer.currentText())
        #self.updateui()

    def fieldchanged(self, number=0):
        """Do the necessary updates after the field selection has
           been changed."""
        ## If the layer list is being updated, don't do anything
        #if self.layerlistchanging:
        #    return
        if self.layerselectionactive:
            return
        #self.button_box.button(QDialogButtonBox.Ok).setEnabled(False)
        inputlayer = QgsMapLayerRegistry.instance().mapLayer(self.inputlayerid)
        if inputlayer is not None:
            findx = self.inputField.itemData(self.inputField.currentIndex())
            inpfield = inputlayer.fieldNameIndex(findx)
            if (inpfield is not None):
                minval = inputlayer.minimumValue(inpfield)
                maxval = inputlayer.maximumValue(inpfield)
                if not isinstance(minval, QPyNullVariant):
                    self.button_box.button(QDialogButtonBox.Ok).setEnabled(True)

    def methodChanged(self, button):
        if self.InputLayer.currentText() is not None:
            self.OutputLayerName.setText("SDE_" + button.text() + "_" +
                                         self.InputLayer.currentText())
        if button.text() == "CrimeStat":
            self.crimestatcorr_cb.setEnabled(False)
            self.degfreedcorr_cb.setChecked(False)
            self.crimestatcorr_cb.setChecked(False)
            self.degfreedcorr_cb.setEnabled(False)
            self.useWeights_cb.setEnabled(False)
            self.useWeights_cb.setChecked(False)
        elif button.text() == "Yuill":
            self.crimestatcorr_cb.setEnabled(True)
            self.degfreedcorr_cb.setEnabled(True)
            self.useWeights_cb.setEnabled(True)
        else:
            self.useWeights_cb.setEnabled(True)

    def showError(self, text):
        """Show an error."""
        self.iface.messageBar().pushMessage(self.tr('Error'), text,
                                            level=QgsMessageBar.CRITICAL,
                                            duration=3)
        QgsMessageLog.logMessage('Error: ' + text,
                                 self.SDELLIPSE,
                                 QgsMessageLog.CRITICAL)

    def showWarning(self, text):
        """Show a warning."""
        self.iface.messageBar().pushMessage(self.tr('Warning'), text,
                                            level=QgsMessageBar.WARNING,
                                            duration=2)
        QgsMessageLog.logMessage('Warning: ' + text,
                                 self.SDELLIPSE,
                                 QgsMessageLog.WARNING)

    def showInfo(self, text):
        """Show info."""
        self.iface.messageBar().pushMessage(self.tr('Info'), text,
                                            level=QgsMessageBar.INFO,
                                            duration=2)
        QgsMessageLog.logMessage('Info: ' + text,
                                 self.SDELLIPSE,
                                 QgsMessageLog.INFO)

    # Implement the accept method to avoid exiting the dialog when
    # starting the work
    def accept(self):
        """Accept override."""
        pass

    # Implement the reject method to have the possibility to avoid
    # exiting the dialog when cancelling
    def reject(self):
        """Reject override."""
        # exit the dialog
        QDialog.reject(self)

    # Translation
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        return QCoreApplication.translate('Dialog', message)

    # Overriding
    def resizeEvent(self, event):
        return
        #self.showInfo("resizeEvent")

    # Overriding
    def showEvent(self, event):
        return
        #self.showInfo("showEvent")
