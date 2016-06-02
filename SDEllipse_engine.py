# -*- coding: utf-8 -*-
from math import sqrt, pow, sin, cos, atan, pi
from PyQt4 import QtCore
from PyQt4.QtCore import QCoreApplication, QPyNullVariant
from qgis.core import QGis
from qgis.core import QgsVectorLayer


class Worker(QtCore.QObject):
    '''The worker that does the heavy lifting.
    The error ellipse is returned as a list of numbers
    (centrex, centrey, angle in radians (counter-clockwise
     relative to the x axis), length of major axis,
     length of minor axis).

    The original formulaes for the CrimeStat / R aspace
    method are based on clockwise angles relative to north.
    These have been adapted to counter-clockwise angles
    relative to x / east.
    '''
    # Define the signals used to communicate
    progress = QtCore.pyqtSignal(float)  # For reporting progress
    status = QtCore.pyqtSignal(str)
    error = QtCore.pyqtSignal(str)
    # Signal for sending over the result:
    finished = QtCore.pyqtSignal(bool, object)

    def __init__(self, inputvectorlayer, selectedfeaturesonly,
                                  numericalattribute, method):
        """Initialise.

        Arguments:
        inputvectorlayer --     (QgsVectorLayer) The base vector
                                 layer for the join
        selectedfeaturesonly -- (boolean) should only selected
                                 features be considered
        numericalattribute --   (string) attribute name for the
                                 numerical attribute (weight)
        method --               (integer) The method to be appied
                                 1: Yuill, 2: CrimeStat
        """

        QtCore.QObject.__init__(self)  # Essential!
        # Creating instance variables from parameters
        self.method = method
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
        try:
            # Make sure the input layer is OK
            inputlayer = self.inputvectorlayer
            if inputlayer is None:
                self.error.emit(self.tr('No input layer defined'))
                self.finished.emit(False, None)
                return
            self.feature_count = inputlayer.featureCount()
            # Check if the layer has features
            if self.feature_count < 2:
                self.error.emit("Not enough features in layer")
                self.finished.emit(False, None)
                return
            # Prepare for the progress bar
            self.processed = 0
            self.percentage = 0
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
            # Find the (weighted) centre (OK)
            for feat in features:
                # Allow user abort
                if self.abort is True:
                    break
                # Weighting?
                if self.useWeight:
                    weight = feat[self.numericalattribute]
                # Check if the value is meaningful - skip if not
                if weight is None:
                    continue
                if isinstance(weight, QPyNullVariant):
                    continue
                theweight = float(weight)
                geom = feat.geometry().asPoint()
                sumx = sumx + geom.x() * theweight
                sumy = sumy + geom.y() * theweight
                sumweight = sumweight + theweight
                self.calculate_progress()
            if sumweight == 0.0:
                self.error.emit(self.tr('Weights add to zero'))
                self.finished.emit(False, None)
                return
            # Calculate the (weighted) mean
            self.meanx = sumx / sumweight
            self.meany = sumy / sumweight

            # Reset the progress bar
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
            for feat in features:
                # Allow user abort
                if self.abort is True:
                    break
                # Weighting?
                if self.useWeight:
                    weight = feat[self.numericalattribute]
                # Check if the value is meaningful - skip if not
                if weight is None:
                    continue
                if isinstance(weight, QPyNullVariant):
                    continue
                theweight = float(weight)
                geom = feat.geometry().asPoint()
                xm = geom.x() - self.meanx
                ym = geom.y() - self.meany
                xyw = xyw + xm * ym * theweight
                x2w = x2w + pow(xm, 2) * theweight
                y2w = y2w + pow(ym, 2) * theweight
                self.calculate_progress()
            if xyw == 0.0:
                self.error.emit(
                  self.tr('Weights add to zero or all points are identical'))
                self.finished.emit(False, None)
                return
            top1 = x2w - y2w
            top2 = sqrt(pow(x2w - y2w, 2) + 4 * pow(xyw, 2))
            bottom = 2 * xyw
            # Compute the angles (Yuill - counter-clockwise from
            # the x-axis / east)
            # (In the CrimeStat / aspace method the angles are clockwise
            # relative to north, so there was no leading minus)
            tantheta1 = - top1 / bottom + top2 / bottom
            tantheta2 = - top1 / bottom - top2 / bottom
            self.theta1 = atan(tantheta1)
            self.theta2 = atan(tantheta2)
            # Find sigma1 and sigma2 according to Wang et.al.
            # "Spectral decomposition"
            #self.sigma1 = sqrt(((x2w + y2w) + top2) / (2 * sumweight))
            #self.sigma2 = sqrt(((x2w + y2w) - top2) / (2 * sumweight))
            # CrimeStat / aspace uses clockwise angles from north:
            #if self.method == 2:
            #    self.theta1 = atan(-tantheta1)
            #    self.theta2 = atan(-tantheta2)

            # Could this be skipped if we use the Wang calculations?
            # How to find the angle of the major axis?
            # Reset the progress bar
            self.processed = 0
            self.percentage = 0
            # Get the features (iterator)
            if (inputlayer.selectedFeatureCount() > 0 and
                                          self.selectedfeaturesonly):
                features = inputlayer.selectedFeaturesIterator()
            else:
                features = inputlayer.getFeatures()
            # Find the SD - trouble!
            angleterm1 = 0.0
            angleterm2 = 0.0
            sxterm = 0.0
            syterm = 0.0
            sumweight = 0.0
            for feat in features:
                # Allow user abort
                if self.abort is True:
                    break
                # Work on the attribute
                if self.useWeight:
                    weight = feat[self.numericalattribute]
                # Check if the value is meaningful - skip if not
                if weight is None:
                    continue
                if isinstance(weight, QPyNullVariant):
                    continue
                theweight = float(weight)
                geom = feat.geometry().asPoint()
                xm = geom.x() - self.meanx
                ym = geom.y() - self.meany
                if self.method == 1 or self.method == 2:  # Yuill/CrimeStat OK
                #if self.method == 1: # Yuill - OK
                    # Angles counter-clockwise relative to the x axis
                    angleterm1 = (angleterm1 +
                                  pow(ym * cos(self.theta1) -
                                      xm * sin(self.theta1), 2) *
                                  theweight)
                    angleterm2 = (angleterm2 +
                                  pow(ym * cos(self.theta2) -
                                      xm * sin(self.theta2), 2) *
                                  theweight)
                #if self.method == 2:
                #    # Crimestat / aspace - OK (angles clockwise relative
                #    # to north):
                #    sxterm = (sxterm +
                #          pow(xm * cos(self.theta1) -
                #              ym * sin(self.theta1), 2) *
                #          theweight)
                #    syterm = (syterm +
                #          pow(xm * sin(self.theta1) +
                #              ym * cos(self.theta1), 2) *
                #           theweight)
                sumweight = sumweight + theweight
                self.calculate_progress()
            if self.method == 1 or self.method == 2:  # Yuill/CrimeStat
            #if self.method == 1:  # Yuill - OK
                self.SD1 = sqrt(angleterm1 / sumweight)
                self.SD2 = sqrt(angleterm2 / sumweight)
            #elif self.method == 2:  # crimestat
            #    self.SD1 = sqrt(2 * syterm / (sumweight - 2))
            #    self.SD2 = sqrt(2 * sxterm / (sumweight - 2))
            #    # Fix angles to be relative to the first axis
            #    self.theta1 = atan(tantheta1)
            #    self.theta2 = atan(tantheta2)
            #self.status.emit('SD1: ' + str(self.SD1) + ' SD2: '
            #                 + str(self.SD2))
        except:
            import traceback
            self.error.emit(traceback.format_exc())
            self.finished.emit(False, None)
        else:
            if self.abort:
                self.finished.emit(False, None)
            else:
                self.finished.emit(True, [self.meanx, self.meany,
                                          self.theta1, self.theta2,
                                          self.SD1, self.SD2])

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
