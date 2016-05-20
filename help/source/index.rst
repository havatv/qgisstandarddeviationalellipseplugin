.. linedirectionhistogram documentation master file, created by
   sphinx-quickstart on Sun Feb 12 17:11:03 2015.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

********************************************
The QGIS Standard Deviational Ellipse Plugin
********************************************

.. toctree::
   :maxdepth: 2


The QGIS Standard Deviational Ellipse plugin implements the
algorithms presented in "The Standard Deviational Ellipse;
An Updated Tool for Spatial Description".  Robert S. Yuill.
Geografiska Annaler. Series B, Human Geography.
Vol. 53, No. 1 (1971), pp. 28-39.
URL: https://www.jstor.org/stable/490885

   
Functionality
=================

- The QGIS Standard Deviational Ellipse plugin can be used to
  investigate point patterns, showing a summary of the
  distribution as an ellipse.
  

Options
=============

- The user can specify if only selected features are to be used
  (but if no features are selected, all features will be used)

- The user can select an attribute for weighting.


Implementation
================

The calculations of the standard deviational ellipse is performed
in a separate thread.


Versions
===============
The current version is 1.0.

- 1.0: First official version.


Links
=======

`Standard Deviational Ellipse Plugin`_

`Standard Deviational Ellipse code repository`_

`Standard Deviational Ellipse issues`_


.. _Standard Deviational Ellipse code repository: https://github.com/havatv/qgisstandarddeviationalellipseplugin.git
.. _Standard Deviational Ellipse Plugin: http://arken.umb.no/~havatv/gis/qgisplugins/SDEllipse
.. _Standard Deviational Ellipse issues: https://github.com/havatv/qgisstandarddeviationalellipseplugin/issues
.. |N2| replace:: N\ :sup:`2`
