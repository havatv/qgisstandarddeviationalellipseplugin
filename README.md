# qgisstandarddeviationalellipseplugin
A QGIS plugin to create a standard deviational ellipse, according to
the method presented by Robert Yuill (1971).
This method does not give a radius equal to the standard distance
deviation for a random point distribution.  To achieve this, the
SDs should be multiplied by sqrt(2), as explained in the CrimeStat
documentation (Chapter 4, endnote ii).
The method does not correct for degrees of freedom (it assumes
that the dataset contains the complete population).

The plugin works on point vector layers.
The user can choose to use only selected features, and then has to
choose an attribute for weighting.

A polygon vector layer with the standard deviational ellipse is
produced, containing the attributes: meanx, meany, majorangle,
minorangle, majorsd and minorsd.
Angles are counter-clockwise relative to the first axis.


References:

Robert S. Yuill (1971).  The Standard Deviational Ellipse; An Updated Tool for Spatial Description.
Geografiska Annaler. Series B, Human Geography. Vol. 53, No. 1 (1971), pp. 28-39.
<URL: https://www.jstor.org/stable/490885>

Ned Levine (2015). CrimeStat: A Spatial Statistics Program for the Analysis of Crime Incident Locations (v 4.02).  Chapter 4.  Ned Levine & Associates, Houston, Texas, and the National Institute of Justice, Washington, D.C. August 2015
<URUL: http://nij.gov/topics/technology/maps/documents/crimestat-files/CrimeStat IV Chapter 4.pdf>


