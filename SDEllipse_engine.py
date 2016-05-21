# -*- coding: utf-8 -*-
from math import sqrt, pow, sin, cos, atan
from PyQt4 import QtCore
from PyQt4.QtCore import QCoreApplication, QPyNullVariant
from qgis.core import QGis
from qgis.core import QgsVectorLayer


class Worker(QtCore.QObject):
    '''The worker that does the heavy lifting.
    The error ellipse is returned as a list of numbers
    (centrex, centrey, angle in radians, length of longest axis,
     length of shortest axis).
    '''
    # Define the signals used to communicate
    progress = QtCore.pyqtSignal(float)  # For reporting progress
    status = QtCore.pyqtSignal(str)
    error = QtCore.pyqtSignal(str)
    # Signal for sending over the result:
    finished = QtCore.pyqtSignal(bool, object)

    def __init__(self, inputvectorlayer, selectedfeaturesonly,
                                  numericalattribute):
        """Initialise.

        Arguments:
        inputvectorlayer --     (QgsVectorLayer) The base vector
                                 layer for the join
        bins --                 (int) bins for end point matching
        minvalue --             (float) lower limit for range
        maxvalue --             (float) upper limit for range
        selectedfeaturesonly -- (boolean) should only selected
                                 features be considered
        numericalattribute --   (string) attribute name for the
                                 numerical attribute
        """

        QtCore.QObject.__init__(self)  # Essential!
        # Creating instance variables from parameters
        self.inputvectorlayer = inputvectorlayer
        self.selectedfeaturesonly = selectedfeaturesonly
        self.numericalattribute = numericalattribute
        self.useWeight = True
        if self.numericalattribute is None:
            self.useWeight = False
        # Creating instance variables for the progress bar ++
        # Number of elements that have been processed - updated by
        # calculate_progress
        self.processed = 0
        # Current percentage of progress - updated by
        # calculate_progress
        self.percentage = 0
        # Flag set by kill(), checked in the loop
        self.abort = False
        # Number of features in the input layer - used by
        # calculate_progress
        self.feature_count = self.inputvectorlayer.featureCount()
        # The number of elements that is needed to increment the
        # progressbar - set early in run()
        self.increment = self.feature_count // 1000

    def run(self):
        #self.status.emit('Started! Min: ' + str(self.minvalue) +
        #                 ' Max: ' + str(self.maxvalue))
        try:
            # Make sure the input layer is OK
            inputlayer = self.inputvectorlayer
            if inputlayer is None:
                self.error.emit(self.tr('No input layer defined'))
                self.finished.emit(False, None)
                return
            # Prepare for the progress bar
            self.processed = 0
            self.percentage = 0
            self.feature_count = inputlayer.featureCount()
            # Check if the layer has features
            if self.feature_count == 0:
                self.error.emit("No features in layer")
                self.finished.emit(False, None)
                return
            self.increment = self.feature_count // 1000
            # Get the features (iterator)
            if (inputlayer.selectedFeatureCount() > 0 and
                                          self.selectedfeaturesonly):
                features = inputlayer.selectedFeaturesIterator()
            else:
                features = inputlayer.getFeatures()
            weight = 1.0
            sumweight = 0.0
            sumx = 0.0
            sumy = 0.0
            # Find the (weighted) centre
            for feat in features:
                # Allow user abort
                if self.abort is True:
                    break
                # Work on the attribute
                if self.useWeight:
                    weight = feat[self.numericalattribute]
                # Check if the value is meaningful
                if weight is None:
                    continue
                if isinstance(weight, QPyNullVariant):
                    continue
                theweight = float(weight)
                geom = feat.geometry().asPoint()
                sumx = sumx + geom.x()
                sumy = sumy + geom.y()
                sumweight = sumweight + theweight
                self.calculate_progress()
            self.meanx = sumx / sumweight
            self.meany = sumy / sumweight
            self.status.emit('Meanx: ' + str(self.meanx) + ' Meany: ' + str(self.meany))
            self.processed = 0
            self.percentage = 0
            # Get the features (iterator)
            if (inputlayer.selectedFeatureCount() > 0 and
                                          self.selectedfeaturesonly):
                features = inputlayer.selectedFeaturesIterator()
            else:
                features = inputlayer.getFeatures()
            # Find the ellipse angles
            weight = 1.0
            xyw = 0.0
            x2w = 0.0
            y2w = 0.0
            #sumweight = 0.0
            for feat in features:
                # Allow user abort
                if self.abort is True:
                    break
                # Work on the attribute
                if self.useWeight:
                    weight = feat[self.numericalattribute]
                # Check if the value is meaningful
                if weight is None:
                    continue
                if isinstance(weight, QPyNullVariant):
                    continue
                theweight = float(weight)
                geom = feat.geometry().asPoint()
                xyw = xyw + (geom.x()-self.meanx) * (geom.y()-self.meany) * theweight
                x2w = x2w + (geom.x()-self.meanx) * (geom.x()-self.meanx) * theweight
                y2w = y2w + (geom.y()-self.meany) * (geom.y()-self.meany) * theweight
                #sumweight = sumweight + theweight
                self.calculate_progress()
            self.status.emit('xyw: ' + str(xyw) + ' x2w: ' + str(x2w))
            tantheta1 = - (x2w - y2w) / (2 * xyw) + sqrt(pow(x2w-y2w, 2) + 4 * pow(xyw, 2)) / (2 * xyw)
            tantheta2 = - (x2w - y2w) / (2 * xyw) - sqrt(pow(x2w-y2w, 2) + 4 * pow(xyw, 2)) / (2 * xyw)
            self.theta1 = atan(tantheta1)
            self.theta2 = atan(tantheta2)
            self.status.emit('theta1: ' + str(self.theta1) + ' theta2: ' + str(self.theta2))
            self.processed = 0
            self.percentage = 0
            # Get the features (iterator)
            if (inputlayer.selectedFeatureCount() > 0 and
                                          self.selectedfeaturesonly):
                features = inputlayer.selectedFeaturesIterator()
            else:
                features = inputlayer.getFeatures()
            # Find the SD
            angleterm1 = 0.0
            angleterm2 = 0.0
            sumweight = 0.0
            for feat in features:
                # Allow user abort
                if self.abort is True:
                    break
                # Work on the attribute
                if self.useWeight:
                    weight = feat[self.numericalattribute]
                # Check if the value is meaningful
                if weight is None:
                    continue
                if isinstance(weight, QPyNullVariant):
                    continue
                theweight = float(weight)
                geom = feat.geometry().asPoint()
                angleterm1 = angleterm1 + pow(
                                 (geom.y()-self.meany) * cos(self.theta1) +
                                 (geom.x()-self.meanx) * sin(self.theta1), 2) * theweight
                angleterm2 = angleterm2 + pow(
                                 (geom.y()-self.meany) * cos(self.theta2) +
                                 (geom.x()-self.meanx) * sin(self.theta2), 2) * theweight
                sumweight = sumweight + theweight
                self.calculate_progress()
            self.SD1 = sqrt(angleterm1 / sumweight)
            self.SD2 = sqrt(angleterm2 / sumweight)
            self.status.emit('SD1: ' + str(self.SD1) + ' SD2: ' + str(self.SD2))
        except:
            import traceback
            self.error.emit(traceback.format_exc())
            self.finished.emit(False, None)
        else:
            if self.abort:
                self.finished.emit(False, None)
            else:
                self.finished.emit(True, [self.meanx,self.meany,self.theta1,self.theta2,self.SD1,self.SD2])

    def calculate_progress(self):
        '''Update progress and emit a signal with the percentage'''
        self.processed = self.processed + 1
        # update the progress bar at certain increments
        if self.increment == 0 or self.processed % self.increment == 0:
            percentage_new = (self.processed * 100) / self.feature_count
            if percentage_new > self.percentage:
                self.percentage = percentage_new
                self.progress.emit(self.percentage)

    def kill(self):
        '''Kill the thread by setting the abort flag'''
        self.abort = True

    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('Engine', message)
