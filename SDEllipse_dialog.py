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
#   histogramGraphicsView: The GraphicsView that contains the histogram
#   frequencyRangeSpinBox: Spinbox to set the frequency cutoff value
#   selectedFeaturesCheckBox: Checkbox to determine if selection is to be used
#   useWeightsCheckBox: Checkbox to determine if weights are to be used
#   InputLayer: The input layer
#   inputField: The field for which the histogram is to be computed

import os
import csv

from math import pow, log, sin, cos, pi
from PyQt4 import uic
from PyQt4.QtCore import SIGNAL, QObject, QThread, QCoreApplication
from PyQt4.QtCore import QPointF, QLineF, QRectF, QSettings
from PyQt4.QtCore import QPyNullVariant, Qt
from PyQt4.QtGui import QDialog, QDialogButtonBox, QFileDialog
from PyQt4.QtGui import QGraphicsLineItem, QGraphicsRectItem
from PyQt4.QtGui import QGraphicsTextItem
from PyQt4.QtGui import QGraphicsScene, QBrush, QPen, QColor
from PyQt4.QtGui import QGraphicsView
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
        self.HISTOGRAM = self.tr('Histogram')
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

        okButton = self.button_box.button(QDialogButtonBox.Ok)
        okButton.setText(self.OK)
        cancelButton = self.button_box.button(QDialogButtonBox.Cancel)
        cancelButton.setText(self.CANCEL)
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
        self.selectedFeaturesCheckBox.setChecked(True)
        self.useWeightsCheckBox.setChecked(False)
        #self.scene = QGraphicsScene(self)
        #self.histogramGraphicsView.setScene(self.scene)
        self.result = None

    def startWorker(self):
        #self.showInfo('Ready to start worker')
        # Get the input layer
        layerindex = self.InputLayer.currentIndex()
        layerId = self.InputLayer.itemData(layerindex)
        inputlayer = QgsMapLayerRegistry.instance().mapLayer(layerId)
        if inputlayer is None:
            self.showError(self.tr('No input layer defined'))
            return
        if inputlayer.featureCount() == 0:
            self.showError(self.tr('No features in input layer'))
            #self.scene.clear()
            return
        if (self.useWeightsCheckBox.isChecked() and self.inputField.count() == 0):
            self.showError(self.tr('Missing numerical field'))
            #self.scene.clear()
            return
        fieldindex = self.inputField.currentIndex()
        fieldname = self.inputField.itemData(fieldindex)
        if (not self.useWeightsCheckBox.isChecked()):
            fieldname = None
        self.result = None
        self.SDLayer = inputlayer
        # create a new worker instance
        worker = Worker(inputlayer,
                        self.selectedFeaturesCheckBox.isChecked(),
                        fieldname)
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
            #self.showInfo("Histogram: " + str(ret))
            self.result = ret
            # Draw the ellipse
            self.drawHistogram()
        else:
            # notify the user that something went wrong
            if not ok:
                self.showError(self.tr('Aborted') + '!')
            else:
                self.showError(self.tr('No histogram created') + '!')
        # Update the user interface
        self.progressBar.setValue(0.0)
        self.button_box.button(QDialogButtonBox.Ok).setEnabled(True)
        self.button_box.button(QDialogButtonBox.Close).setEnabled(True)
        self.InputLayer.setEnabled(True)
        self.inputField.setEnabled(True)
        # end of workerFinished(self, ok, ret)

    def workerError(self, exception_string):
        """Report an error from the worker."""
        #QgsMessageLog.logMessage(self.tr('Worker failed - exception') +
        #                         ': ' + str(exception_string),
        #                         self.HISTOGRAM,
        #                         QgsMessageLog.CRITICAL)
        self.showError(exception_string)

    def workerInfo(self, message_string):
        """Report an info message from the worker."""
        QgsMessageLog.logMessage(self.tr('Worker') + ': ' +
                                 message_string,
                                 self.HISTOGRAM,
                                 QgsMessageLog.INFO)

    def killWorker(self):
        """Kill the worker thread."""
        if self.worker is not None:
            QgsMessageLog.logMessage(self.tr('Killing worker'),
                                     self.HISTOGRAM,
                                     QgsMessageLog.INFO)
            self.worker.kill()

    # Implement the reject method to have the possibility to avoid
    # exiting the dialog when cancelling
    def reject(self):
        """Reject override."""
        # exit the dialog
        QDialog.reject(self)

    def drawHistogram(self):
        #self.showInfo('Result: ' + str(self.result))
        meanx = self.result[0] # OK
        meany = self.result[1] # OK
        angle1 = self.result[2]
        angle2 = self.result[3]
        SD1 = self.result[4]
        SD2 = self.result[5]
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
        self.showInfo('Major axis angle: ' + str(majoraxisangle) + ' Major axis length: ' + str(majorSD) + ' Minor axis length: ' + str(minorSD))
        # Create the memory layer for the ellipse
        layeruri = 'Polygon?'
        #layeruri = 'linestring?'
        layeruri = (layeruri + 'crs=' +
                    str(self.SDLayer.dataProvider().crs().authid()))
        memSDlayer = QgsVectorLayer(layeruri, self.SDLayer.name() + "_SDE", "memory")
        sdfeature = QgsFeature()
        theta1 = majoraxisangle
        points = []
        step = 2 * pi / 100
        t = 0.0
        while t < 2 * pi:
            p1 = QPointF(meanx + majorSD*cos(t)*cos(majoraxisangle) -
                         minorSD*sin(t)*sin(majoraxisangle),
                         meany + majorSD*cos(t)*sin(majoraxisangle) +
                         minorSD*sin(t)*cos(majoraxisangle))
            points.append(QgsPoint(p1))
            t = t + step
        sdfeature.setGeometry(QgsGeometry.fromPolygon([points]))
        #sdfeature.setGeometry(QgsGeometry.fromPolyline(points))
        memSDlayer.dataProvider().addFeatures([sdfeature])
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

    def showError(self, text):
        """Show an error."""
        self.iface.messageBar().pushMessage(self.tr('Error'), text,
                                            level=QgsMessageBar.CRITICAL,
                                            duration=3)
        QgsMessageLog.logMessage('Error: ' + text,
                                 self.HISTOGRAM,
                                 QgsMessageLog.CRITICAL)

    def showWarning(self, text):
        """Show a warning."""
        self.iface.messageBar().pushMessage(self.tr('Warning'), text,
                                            level=QgsMessageBar.WARNING,
                                            duration=2)
        QgsMessageLog.logMessage('Warning: ' + text,
                                 self.HISTOGRAM,
                                 QgsMessageLog.WARNING)

    def showInfo(self, text):
        """Show info."""
        self.iface.messageBar().pushMessage(self.tr('Info'), text,
                                            level=QgsMessageBar.INFO,
                                            duration=2)
        QgsMessageLog.logMessage('Info: ' + text,
                                 self.HISTOGRAM,
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
        #self.showInfo("resizeEvent")
        if (self.result is not None):
            self.drawHistogram()

    # Overriding
    def showEvent(self, event):
        return
        #self.showInfo("showEvent")

