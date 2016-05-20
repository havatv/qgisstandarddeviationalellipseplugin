# -*- coding: utf-8 -*-
"""
/***************************************************************************
 standarddeviationalellipse
                                 A QGIS plugin
 Create a standard deviational histogram from a point layer.
                             -------------------
        begin                : 2016-05-20
        copyright            : (C) 2016 by Håvard Tveite
        email                : havard.tveite@nmbu.no
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load SDEllipse class from file SDEllipse.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """

    from .SDEllipse import SDEllipse
    return SDEllipse(iface)
