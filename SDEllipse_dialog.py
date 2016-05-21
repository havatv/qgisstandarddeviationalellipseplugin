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
#   binsSpinBox: Spinbox to set the number of bins
#   minValueSpinBox: Spinbox to set the minimum value
#   maxValueSpinBox: Spinbox to set the maximum value
#   frequencyRangeSpinBox: Spinbox to set the frequency cutoff value
#   selectedFeaturesCheckBox: Checkbox to determine if selection is to be used
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
        #self.iface.legendInterface().itemAdded.connect(
        #    self.layerlistchanged)
        #self.iface.legendInterface().itemRemoved.connect(
        #    self.layerlistchanged)
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
        #self.bins = 8
        #self.binsSpinBox.setValue(self.bins)
        self.selectedFeaturesCheckBox.setChecked(True)
        self.useWeightsCheckBox.setChecked(False)
        self.scene = QGraphicsScene(self)
        self.histogramGraphicsView.setScene(self.scene)
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
            self.scene.clear()
            return
        #self.binSize = self.binSizeSpinBox.value()
        #self.bins = self.binsSpinBox.value()
        #self.outputfilename = self.outputFile.text()
        #self.minValue = self.minValueSpinBox.value()
        #self.maxValue = self.maxValueSpinBox.value()
        #self.maxValue = self.minValue + self.bins * self.binSize
        #if (self.maxValue - self.minValue < 0):
        #    self.showError(self.tr('Max value less than min value'))
        #    return
        if (self.useWeightsCheckBox.isChecked() and self.inputField.count() == 0):
            self.showError(self.tr('Missing numerical field'))
            self.scene.clear()
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
        ## configure the QgsMessageBar
        #msgBar = self.iface.messageBar().createMessage(self.tr('Joining'), '')
        #self.aprogressBar = QProgressBar()
        #self.aprogressBar.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        #acancelButton = QPushButton()
        #acancelButton.setText(self.CANCEL)
        #acancelButton.clicked.connect(self.killWorker)
        #msgBar.layout().addWidget(self.aprogressBar)
        #msgBar.layout().addWidget(acancelButton)
        ## Has to be popped after the thread has finished (in
        ## workerFinished).
        #self.iface.messageBar().pushWidget(msgBar,
        #                                   self.iface.messageBar().INFO)
        #self.messageBar = msgBar
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
            # report the result
            # As a CSV file:
            # Draw the histogram
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
        self.showInfo('Result: ' + str(self.result))
        self.scene.clear()
        viewprect = QRectF(self.histogramGraphicsView.viewport().rect())
        self.histogramGraphicsView.setSceneRect(viewprect)
        bottom = self.histogramGraphicsView.sceneRect().bottom()
        top = self.histogramGraphicsView.sceneRect().top()
        left = self.histogramGraphicsView.sceneRect().left()
        right = self.histogramGraphicsView.sceneRect().right()
        height = bottom - top - 1
        width = right - left - 1
        padding = 3
        toppadding = 3
        maxsd = max(self.result[4],self.result[5])
        hline1 = QGraphicsLineItem(QLineF(width/2, height/2,
                                          width/2 + self.result[4] / maxsd * width / 2.0 * cos(self.result[2]),
                                          height/2 + self.result[4] / maxsd * width / 2.0 * sin(self.result[2])))
        hlinepen = QPen(QColor(255, 0, 0))
        #hlinepen.setStyle(Qt.DotLine)
        #setDashPattern([5,5,5,5])
        hline1.setPen(hlinepen)
        self.scene.addItem(hline1)
        hline2 = QGraphicsLineItem(QLineF(width/2, height/2,
                                          width/2 + self.result[5] / maxsd * width / 2.0 * cos(self.result[3]),
                                          height/2 + self.result[5] / maxsd * width / 2.0 * sin(self.result[3])))
        hlinepen = QPen(QColor(0, 255, 0))
        #hlinepen = QPen(QColor(153, 153, 153), 1, Qt.DashLine)
        hlinepen.setStyle(Qt.DashLine)
        #setDashPattern([5,5,5,5])
        hline2.setPen(hlinepen)
        self.scene.addItem(hline2)

        a = self.result[4] / maxsd * width/2
        b = self.result[5] / maxsd * width/2
        theta1 = self.result[2]
        theta2 = self.result[3]
        step = pi / 100
        t = 0.0
        p1 = QPointF(width/2 + a*cos(0)*cos(theta1) -
                         b*sin(0)*sin(theta1),
                     height/2 + a*cos(0)*sin(theta1) +
                         b*sin(0)*cos(theta1))
        while t < 2 * pi:
            t = t + step
            p2 = QPointF(width/2 + a*cos(t)*cos(theta1) -
                         b*sin(t)*sin(theta1),
                         height/2 + a*cos(t)*sin(theta1) +
                         b*sin(t)*cos(theta1))
            segment = QGraphicsLineItem(QLineF(p1,p2))
            linepen = QPen(QColor(0, 255, 0))
            hlinepen.setStyle(Qt.DashLine)
            segment.setPen(linepen)
            self.scene.addItem(segment)
            #self.showInfo('t: ' + str(t) + " Point: " + str(p1))
            p1 = p2


        # Create the memory layer for the ellipse
        layeruri = 'Polygon?'
        #layeruri = 'linestring?'
        layeruri = (layeruri + 'crs=' +
                    str(self.SDLayer.dataProvider().crs().authid()))
        memSDlayer = QgsVectorLayer(layeruri, self.SDLayer.name() + "_SDE", "memory")
        sdfeature = QgsFeature()
        meanx = self.result[0] # OK
        meany = self.result[1] # OK
        theta1 = self.result[2] 
        b = self.result[4]
        a = self.result[5]
        points = []
        #t = pi / 4.0
        t = 0.0
        while t < 2 * pi:
        #while t < 2 * pi + pi / 4.0:
            p1 = QPointF(meanx + a*cos(t)*cos(theta1) -
                         b*sin(t)*sin(theta1),
                         meany + a*cos(t)*sin(theta1) +
                         b*sin(t)*cos(theta1))
            points.append(QgsPoint(p1))
            t = t + step
        sdfeature.setGeometry(QgsGeometry.fromPolygon([points]))
        #sdfeature.setGeometry(QgsGeometry.fromPolyline(points))
        memSDlayer.dataProvider().addFeatures([sdfeature])
        memSDlayer.updateExtents()
        QgsMapLayerRegistry.instance().addMapLayers([memSDlayer])

        return

        if self.result is None:
            return
        # Label the histogram
        minvaltext = QGraphicsTextItem(str(self.minValue))
        minvaltextheight = minvaltext.boundingRect().height()
        maxvaltext = QGraphicsTextItem(str(self.maxValue))
        maxvaltextwidth = maxvaltext.boundingRect().width()

        #self.showInfo(str(self.result))
        # Which element should be used for the histogram
        element = 1
        # Find the maximum value for scaling
        maxvalue = 0
        for i in range(len(self.result)):
            if self.cumulative:
                maxvalue = maxvalue + self.result[i][element]
            else:
                if self.result[i][element] > maxvalue:
                    maxvalue = self.result[i][element]
        cutoffvalue = maxvalue
        self.scene.clear()
        if maxvalue == 0:
            return
        viewprect = QRectF(self.histogramGraphicsView.viewport().rect())
        self.histogramGraphicsView.setSceneRect(viewprect)
        bottom = self.histogramGraphicsView.sceneRect().bottom()
        top = self.histogramGraphicsView.sceneRect().top()
        left = self.histogramGraphicsView.sceneRect().left()
        right = self.histogramGraphicsView.sceneRect().right()
        height = bottom - top - 1
        width = right - left - 1
        padding = 3
        toppadding = 3
        bottompadding = minvaltextheight
        # Determine the width of the left margin (depends on the y range)
        clog = log(cutoffvalue, 10)
        clogint = int(clog)
        yincr = pow(10, clogint)
        dummytext = QGraphicsTextItem(str(yincr))
        # The left padding must accomodate the y labels
        leftpadding = dummytext.boundingRect().width()
        # Find the width of the maximium frequency label
        maxfreqtext = QGraphicsTextItem(str(cutoffvalue))
        maxfreqtextwidth = maxvaltext.boundingRect().width()
        rightpadding = maxfreqtextwidth
        width = width - (leftpadding + rightpadding)
        height = height - (toppadding + bottompadding)
        barwidth = width / self.bins
        binsize = 0
        # Create the histogram
        for i in range(self.bins):
            if self.cumulative:
                binsize = binsize + self.result[i][element]
            else:
                binsize = self.result[i][element]
            #barheight = height * self.result[i][element] / maxvalue
            barheight = height * binsize / cutoffvalue
            barrect = QGraphicsRectItem(QRectF(leftpadding + barwidth * i,
                        height - barheight + toppadding, barwidth, barheight))
            barbrush = QBrush(QColor(255, 153, 102))
            barrect.setBrush(barbrush)
            self.scene.addItem(barrect)
        # Determine the increments for the horizontal lines
        if (cutoffvalue // yincr <= 5 and yincr > 1):
            yincr = yincr / 2
            if (cutoffvalue // yincr < 5 and yincr > 10):
                yincr = yincr / 2
        # Draw horizontal lines with labels
        yval = 0
        while (yval <= cutoffvalue):
            scval = height + toppadding - yval * height / cutoffvalue
            hline = QGraphicsLineItem(QLineF(leftpadding - 3, scval,
                                             width + (leftpadding), scval))
            #hlinepen = QPen(QColor(153, 153, 153), 1, Qt.DashLine)
            hlinepen = QPen(QColor(153, 153, 153))
            hlinepen.setStyle(Qt.DotLine)
            #setDashPattern([5,5,5,5])
            hline.setPen(hlinepen)
            self.scene.addItem(hline)
            ylabtext = QGraphicsTextItem(str(int(yval)))
            ylabtextheight = ylabtext.boundingRect().height()
            ylabtextwidth = ylabtext.boundingRect().width()
            ylabtext.setPos(leftpadding - ylabtextwidth,
                            scval - ylabtextheight / 2)
            if (scval - ylabtextheight / 2 > 0):
                self.scene.addItem(ylabtext)
            yval = yval + yincr
        # Draw frame
        vline1 = QGraphicsLineItem(QLineF(leftpadding - 1, toppadding,
                                 leftpadding - 1, toppadding + height))
        vlinepen = QPen(QColor(153, 153, 153))
        vline1.setPen(vlinepen)
        self.scene.addItem(vline1)
        vline2 = QGraphicsLineItem(QLineF(leftpadding + width + 1, toppadding,
                               leftpadding + width + 1, toppadding + height))
        vline2.setPen(vlinepen)
        self.scene.addItem(vline2)

        minvaltextwidth = minvaltext.boundingRect().width()
        minvaltext.setPos(leftpadding - minvaltextwidth / 2,
                          height + toppadding + bottompadding
                          - minvaltextheight)
        self.scene.addItem(minvaltext)
        maxvaltext.setPos(leftpadding + width - maxvaltextwidth / 2,
                          height + toppadding + bottompadding
                          - minvaltextheight)
        self.scene.addItem(maxvaltext)
        maxfreqtext.setPos(leftpadding + width, 0)
        self.scene.addItem(maxfreqtext)

    #def layerlistchanged(self):
    #    self.layerlistchanging = True
    #    # Repopulate the input and join layer combo boxes
    #    # Save the currently selected input layer
    #    inputlayerid = self.inputlayerid
    #    self.InputLayer.clear()
    #    # We are only interested in line and polygon layers
    #    for alayer in self.iface.legendInterface().layers():
    #        if alayer.type() == QgsMapLayer.VectorLayer:
    #            if (alayer.geometryType() == QGis.Line or
    #                alayer.geometryType() == QGis.Polygon):
    #                self.InputLayer.addItem(alayer.name(), alayer.id())
    #    # Set the previous selection
    #    for i in range(self.InputLayer.count()):
    #        if self.InputLayer.itemData(i) == inputlayerid:
    #            self.InputLayer.setCurrentIndex(i)
    #    self.layerlistchanging = False

    def layerchanged(self, number=0):
        """Do the necessary updates after a layer selection has
           been changed."""
        ## If the layer list is being updated, don't do anything
        #if self.layerlistchanging:
        #    return
        #self.button_box.button(QDialogButtonBox.Ok).setEnabled(False)
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


def saveDialog(parent):
        """Shows a file dialog and return the selected file path."""
        settings = QSettings()
        key = '/UI/lastShapefileDir'
        outDir = settings.value(key)
        filter = 'Comma Separated Value (*.csv)'
        outFilePath = QFileDialog.getSaveFileName(parent,
                       parent.tr('Output CSV file'), outDir, filter)
        outFilePath = unicode(outFilePath)
        if outFilePath:
            root, ext = os.path.splitext(outFilePath)
            if ext.upper() != '.CSV':
                outFilePath = '%s.csv' % outFilePath
            outDir = os.path.dirname(outFilePath)
            settings.setValue(key, outDir)
        return outFilePath
