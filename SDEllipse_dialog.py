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
#   InputLayer: The input layer
#   inputField: The field for weights
#   OutputLayerName: text field for specifying the output layer name
#   selectedFeatures_cb: Checkbox to determine if selection is to be used
#   useWeights_cb: Checkbox to determine if weights are to be used
#   yuill_rb: Radiobutton to choose the Yuill method
#   crimestat_rb: Radiobutton to choose the Crimestat/aspace method
#   degfreedcorr_cb: Checkbox to enable degrees of freedom correction
#   crimestatcorr_cb: Checkbox to enable sqrt2 correction
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
        self.yuill_rb.setChecked(True)
        self.method = 1
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
        QObject.disconnect(self.button_box, SIGNAL("rejected()"),
                           self.reject)

        # Set instance variables
        self.worker = None
        self.inputlayerid = None
        self.layerlistchanging = False
        self.selectedFeatures_cb.setChecked(True)
        self.useWeights_cb.setChecked(False)
        self.result = None
    # end of __init__

    def startWorker(self):
        #self.showInfo('Ready to start worker')
        self.degfreedCorr = self.degfreedcorr_cb.isChecked()
        self.crimestatCorr = self.crimestatcorr_cb.isChecked()
        # Get the input layer
        layerindex = self.InputLayer.currentIndex()
        layerId = self.InputLayer.itemData(layerindex)
        inputlayer = QgsMapLayerRegistry.instance().mapLayer(layerId)
        self.featureCount = 0
        if self.selectedFeatures_cb.isChecked():
            self.featureCount = inputlayer.selectedFeatureCount()
        if self.featureCount == 0:
            self.featureCount = inputlayer.featureCount()
        if inputlayer is None:
            self.showError(self.tr('No input layer defined'))
            return
        if self.featureCount < 2:
            self.showError(self.tr('Not enough features'))
            #self.scene.clear()
            return
        if (self.useWeights_cb.isChecked() and
                 self.inputField.count() == 0):
            self.showError(self.tr('Missing numerical field'))
            return
        fieldindex = self.inputField.currentIndex()
        fieldname = self.inputField.itemData(fieldindex)
        #inpfield = inputlayer.fieldNameIndex(fieldindex)
        #minval = inputlayer.minimumValue(inpfield)

        if (not self.useWeights_cb.isChecked()):
            fieldname = None
        self.result = None
        self.SDLayer = inputlayer
        self.method = 1
        if self.yuill_rb.isChecked():
            self.method = 1
        elif self.crimestat_rb.isChecked():
            self.method = 2
        if self.featureCount < 3 and (self.method == 2 or
                                      self.degfreedCorr):
            self.showError(self.tr('Not enough features'))
            return
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
    # end of startWorker

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
            #self.showInfo("Result: " + str(ret))
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
        if self.method == 1 and self.inputField.count() > 0:
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
        if self.method == 2:  # CrimeStat
            SD1 = SD1 * (sqrt(2) *
                         sqrt(self.featureCount) /
                         sqrt(self.featureCount - 2))
            SD2 = SD2 * (sqrt(2) *
                         sqrt(self.featureCount) /
                         sqrt(self.featureCount - 2))
        if self.crimestatCorr and self.method != 2:
            SD1 = SD1 * sqrt(2)
            SD2 = SD2 * sqrt(2)
        if self.degfreedCorr and self.method != 2:
            SD1 = SD1 * sqrt(self.featureCount) / sqrt(self.featureCount - 2)
            SD2 = SD2 * sqrt(self.featureCount) / sqrt(self.featureCount - 2)
            #SD1 = SD1 * sqrt(self.featureCount) / sqrt(self.featureCount - 1)
            #SD2 = SD2 * sqrt(self.featureCount) / sqrt(self.featureCount - 1)
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
        # Calculate the "compass" direction angle (clockwise from north)
        direction = 90.0 - majoraxisangle * 180 / pi
        # Calculte the eccentricity
        eccentricity = sqrt(1 - pow(minorSD, 2) / pow(majorSD, 2))
        # Create the memory layer for the ellipse
        sdefields = []
        sdefields.append(QgsField("meanx", QVariant.Double))
        sdefields.append(QgsField("meany", QVariant.Double))
        sdefields.append(QgsField("majoranglerad", QVariant.Double))
        #sdefields.append(QgsField("minoranglerad", QVariant.Double))
        sdefields.append(QgsField("directiondeg", QVariant.Double))
        sdefields.append(QgsField("majorsd", QVariant.Double))
        sdefields.append(QgsField("minorsd", QVariant.Double))
        sdefields.append(QgsField("eccentricity", QVariant.Double))
        layeruri = 'Polygon?'
        layeruri = (layeruri + 'crs=' +
                    str(self.SDLayer.dataProvider().crs().authid()))
        memSDlayer = QgsVectorLayer(layeruri, self.OutputLayerName.text(),
                                    "memory")
        memSDlayer.startEditing()  # ?
        for field in sdefields:
            memSDlayer.dataProvider().addAttributes([field])
        sdfeature = QgsFeature()
        theta1 = majoraxisangle
        points = []
        step = pi / 180    # 360 points to draw the ellipse
        t = 0.0
        while t < 2 * pi:
            p1 = QPointF(meanx + majorSD * cos(t) * cos(majoraxisangle) -
                         minorSD * sin(t) * sin(majoraxisangle),
                         meany + majorSD * cos(t) * sin(majoraxisangle) +
                         minorSD * sin(t) * cos(majoraxisangle))
            points.append(QgsPoint(p1))
            t = t + step
        sdfeature.setGeometry(QgsGeometry.fromPolygon([points]))
        attrs = [meanx, meany, majoraxisangle, direction,
                 majorSD, minorSD, eccentricity]
        sdfeature.setAttributes(attrs)
        memSDlayer.dataProvider().addFeatures([sdfeature])
        memSDlayer.commitChanges()  # ?
        memSDlayer.updateExtents()
        QgsMapLayerRegistry.instance().addMapLayers([memSDlayer])
    # end of drawEllipse

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
        self.useWeights_cb.setEnabled(False)
        self.inputField.setEnabled(False)
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
                if self.method == 1:
                    self.useWeights_cb.setEnabled(True)
                    self.inputField.setEnabled(True)
            else:
                self.useWeights_cb.setChecked(False)
            self.OutputLayerName.setText(
                "SDE_" +
                self.method_group.checkedButton().text() +
                "_" + self.InputLayer.currentText())
    # end of layerchanged

    def methodChanged(self, button):
        if self.InputLayer.currentText() is not None:
            self.OutputLayerName.setText("SDE_" + button.text() + "_" +
                                         self.InputLayer.currentText())
        # Disable all options
        self.crimestatcorr_cb.setEnabled(False)
        self.crimestatcorr_cb.setChecked(False)
        self.degfreedcorr_cb.setEnabled(False)
        self.degfreedcorr_cb.setChecked(False)
        self.useWeights_cb.setEnabled(False)
        self.useWeights_cb.setChecked(False)
        self.inputField.setEnabled(False)
        if button.text() == '"CrimeStat"':
            self.method = 2
        elif button.text() == "Yuill":
            self.method = 1
            self.crimestatcorr_cb.setEnabled(True)
            self.degfreedcorr_cb.setEnabled(True)
            if self.inputField.count() > 0:
                self.useWeights_cb.setEnabled(True)
                self.inputField.setEnabled(True)
        else:  # Should not be reached yet
            if self.inputField.count() > 0:
                self.useWeights_cb.setEnabled(True)
                self.inputField.setEnabled(True)

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
