# -*- coding: utf-8 -*-
#
#
# TheVirtualBrain-Framework Package. This package holds all Data Management, and 
# Web-UI helpful to run brain-simulations. To use it, you also need do download
# TheVirtualBrain-Scientific Package (for simulators). See content of the
# documentation-folder for more details. See also http://www.thevirtualbrain.org
#
# (c) 2012-2013, Baycrest Centre for Geriatric Care ("Baycrest")
#
# This program is free software; you can redistribute it and/or modify it under 
# the terms of the GNU General Public License version 2 as published by the Free
# Software Foundation. This program is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of 
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public
# License for more details. You should have received a copy of the GNU General 
# Public License along with this program; if not, you can download it here
# http://www.gnu.org/licenses/old-licenses/gpl-2.0
#
#
#   CITATION:
# When using The Virtual Brain for scientific publications, please cite it as follows:
#
#   Paula Sanz Leon, Stuart A. Knock, M. Marmaduke Woodman, Lia Domide,
#   Jochen Mersmann, Anthony R. McIntosh, Viktor Jirsa (2013)
#       The Virtual Brain: a simulator of primate brain network dynamics.
#   Frontiers in Neuroinformatics (7:10. doi: 10.3389/fninf.2013.00010)
#
#

"""
.. moduleauthor:: Bogdan Neacsa <bogdan.neacsa@codemart.ro>
"""

import sys
import numpy
import json
from scipy import interpolate
from tvb.core.entities import model
from tvb.core.entities.storage import dao
from tvb.core.adapters.abcdisplayer import ABCMPLH5Displayer
from tvb.core.adapters.exceptions import LaunchException
from tvb.datatypes.mapped_values import DatatypeMeasure
from tvb.basic.config.settings import TVBSettings as config
from tvb.basic.filters.chain import FilterChain


# The resolution for computing dots inside the displayed isocline.
# This is not the sae as display size.
RESOLUTION = (600, 600)



class IsoclinePSEAdapter(ABCMPLH5Displayer):
    """
    Visualization adapter for Parameter Space Exploration.
    Will be used as a generic visualizer, accessible when input entity is DataTypeGroup.
    Will also be used in Burst as a supplementary navigation layer.
    """

    _ui_name = "Isocline Parameter Space Exploration"
    _ui_subsection = "pse_iso"


    def __init__(self):
        ABCMPLH5Displayer.__init__(self)
        self.figures = {}
        self.interp_models = {}
        self.nan_indices = {}


    def get_input_tree(self):
        """
        Take as Input a Connectivity Object.
        """
        return [{'name': 'datatype_group',
                 'label': 'Datatype Group',
                 'type': model.DataTypeGroup,
                 'required': True,
                 'conditions': FilterChain(fields=[FilterChain.datatype + ".no_of_ranges",
                                                   FilterChain.datatype + ".only_numeric_ranges"],
                                           operations=["==", "=="], values=[2, True])}]


    def get_required_memory_size(self, **kwargs):
        """
        Return the required memory to run this algorithm.
        """
        # Don't know how much memory is needed.
        return -1


    def burst_preview(self, datatype_group_gid, width, height):
        """
        Generate the preview for the burst page.
        """
        if not width:
            width = height
        figure_size = (700, 700)
        if width and height:
            figure_size = (width, height)
        datatype_group = dao.get_datatype_group_by_gid(datatype_group_gid)
        result_dict = self.launch(datatype_group=datatype_group, figure_size=figure_size)
        return result_dict


    def launch(self, datatype_group, **kwargs):
        """
        Also overwrite launch from ABCDisplayer, since we want to handle a list of figures,
        instead of only one Matplotlib figure.

        :raises LaunchException: when called before all operations in the group are finished
        """
        if self.PARAM_FIGURE_SIZE in kwargs:
            figsize = kwargs[self.PARAM_FIGURE_SIZE]
            figsize = ((figsize[0]) / 80, (figsize[1]) / 80)
            del kwargs[self.PARAM_FIGURE_SIZE]
        else:
            figsize = (15, 7)

        operation_group = dao.get_operationgroup_by_id(datatype_group.fk_operation_group)
        _, range1_name, self.range1 = operation_group.load_range_numbers(operation_group.range1)
        _, range2_name, self.range2 = operation_group.load_range_numbers(operation_group.range2)

        for operation in dao.get_operations_in_group(operation_group.id):
            if operation.status == model.STATUS_STARTED:
                raise LaunchException("Can not display until all operations from this range are finished!")

            op_results = dao.get_results_for_operation(operation.id)
            if len(op_results):
                datatype = op_results[0]
                if datatype.type == "DatatypeMeasure":
                    ## Load proper entity class from DB.
                    dt_measure = dao.get_generic_entity(DatatypeMeasure, datatype.id)[0]
                else:
                    dt_measure = dao.get_generic_entity(DatatypeMeasure, datatype.gid, '_analyzed_datatype')
                    if dt_measure:
                        dt_measure = dt_measure[0]
                break
            else:
                dt_measure = None

        figure_nrs = {}
        metrics = dt_measure.metrics if dt_measure else {}
        if metrics:
            for metric in metrics:
                # Separate plot for each metric.
                self._create_plot(metric, figsize, operation_group, range1_name, range2_name, figure_nrs)
        else:
            raise LaunchException("No datatypes were generated due to simulation errors. Nothing to display.")

        parameters = dict(title=self._ui_name, showFullToolbar=True,
                          serverIp=config.SERVER_IP, serverPort=config.MPLH5_SERVER_PORT,
                          figureNumbers=figure_nrs, metrics=metrics, figuresJSON=json.dumps(figure_nrs))

        return self.build_display_result("pse_isocline/view", parameters)


    def plot(self, figure, operation_group, metric, range1_name, range2_name):
        """
        Do the plot for the given figure. Also need operation group, metric and ranges
        in order to compute the data to be plotted.
        """
        operations = dao.get_operations_in_group(operation_group.id)
        # Data from which to interpolate larger 2-D space
        apriori_x = numpy.array(self.range1)
        apriori_y = numpy.array(self.range2)
        apriori_data = numpy.zeros((apriori_x.size, apriori_y.size))

        # An 2D array of GIDs which is used later to launch overlay for a DataType
        datatypes_gids = [[None for _ in self.range2] for _ in self.range1]
        for operation_ in operations:
            range_values = eval(operation_.range_values)
            key_1 = range_values[range1_name]
            index_x = self.range1.index(key_1)
            key_2 = range_values[range2_name]
            index_y = self.range2.index(key_2)
            if operation_.status == model.STATUS_STARTED:
                raise LaunchException("Not all operations from this range are complete. Cannot view until then.")

            operation_results = dao.get_results_for_operation(operation_.id)
            if operation_results:
                datatype = operation_results[0]
                datatypes_gids[index_x][index_y] = datatype.gid
    
                if datatype.type == "DatatypeMeasure":
                    measures = dao.get_generic_entity(DatatypeMeasure, datatype.id)
                else:
                    measures = dao.get_generic_entity(DatatypeMeasure, datatype.gid, '_analyzed_datatype')
            else:
                datatypes_gids[index_x][index_y] = None
                measures = None

            if measures:
                apriori_data[index_x][index_y] = measures[0].metrics[metric]
            else:
                apriori_data[index_x][index_y] = numpy.NaN
            
        # Convert array to 0 but keep track of nan values so we can replace after interpolation
        # since interpolating with nan values will just break the whole process
        nan_indices = numpy.isnan(apriori_data)
        self.nan_indices[figure.number] = nan_indices
        apriori_data = numpy.nan_to_num(apriori_data)
        # Attempt order-3 interpolation.
        kx = ky = 3
        if len(self.range1) <= 3 or len(self.range2) <= 3:
            # Number of points is too small, just do linear interpolation
            kx = ky = 1
        s = interpolate.RectBivariateSpline(apriori_x, apriori_y, apriori_data, kx=kx, ky=ky)
        # Get data of higher resolution that we'll plot later on
        posteriori_x = numpy.arange(self.range1[0], self.range1[-1],
                                    (self.range1[-1] - self.range1[0]) / RESOLUTION[0])
        posteriori_y = numpy.arange(self.range2[0], self.range2[-1],
                                    (self.range2[-1] - self.range2[0]) / RESOLUTION[1])
        posteriori_data = s(posteriori_x, posteriori_y)
        x_granularity = RESOLUTION[0] / len(self.range1)
        y_granularity = RESOLUTION[1] / len(self.range2)
        for idx, row in enumerate(nan_indices):
            for idy, was_nan in enumerate(row):
                if was_nan:
                    # Now we want to set back all the values that were NaN before interpolation
                    # and keep track of the change in granularity. For this reason for each nan
                    # value we had before, we will now have a matrix of the shape [x_granularity x y_granularity]
                    # full of NaN values
                    start_x = idx * x_granularity
                    end_x = (idx + 1) * x_granularity
                    start_y = idy * y_granularity
                    end_y = (idy + 1) * y_granularity
                    for x_scaled in xrange(start_x, end_x, 1):
                        for y_scaled in xrange(start_y, end_y, 1):
                            posteriori_data[x_scaled, y_scaled] = numpy.NaN
        # Rotate to get good plot
        posteriori_data = numpy.rot90(posteriori_data)
        
        self.interp_models[figure.number] = s
        # Do actual plot.        
        axes = figure.gca()
        img = axes.imshow(posteriori_data, extent=(min(self.range1), max(self.range1),
                                                   min(self.range2), max(self.range2)),
                          aspect='auto', interpolation='nearest')
        axes.set_title("Interpolated values for metric %s" % (metric,))
        figure.colorbar(img)
        axes.set_xlabel(range1_name)
        axes.set_ylabel(range2_name)


        def format_coord(x, y):
            return 'x=%1.4f, y=%1.4f' % (x, y)


        axes.format_coord = format_coord
        return datatypes_gids


    def _create_plot(self, metric, figsize, operation_group, range1_name, range2_name, figure_nrs):
        """
        Create a plot for each metric, with a given figsize:. We need also operation group,
        ranges for data computations. figure_nrs iw a mapping between metric : figure_number
        """
        figure = self._create_new_figure(figsize)
        
        def _get_x_index(x):
            x_idx = -1
            x_dist = sys.maxint
            for idx, val in enumerate(self.range1):
                if x_dist > abs(val - x):
                    x_dist = abs(val - x)
                    x_idx = idx
            return x_idx
        
        def _get_y_index(y):
            y_idx = -1
            y_dist = sys.maxint
            for idx, val in enumerate(self.range2):
                if y_dist > abs(val - y):
                    y_dist = abs(val - y)
                    y_idx = idx
            return y_idx

        # Create events for each figure.
        def _click_event(event, figure=figure):
            if event.inaxes is figure.gca():
                x, y = event.xdata, event.ydata
                x_idx = _get_x_index(x)
                y_idx = _get_y_index(y)
                if self.datatype_gids[x_idx][y_idx]:
                    figure.command = "clickedDatatype('%s')" % (self.datatype_gids[x_idx][y_idx])


        def _hover_event(event, figure=figure):
            if event.inaxes is figure.gca():
                x, y = event.xdata, event.ydata
                x_idx = _get_x_index(x)
                y_idx = _get_y_index(y)
                if self.nan_indices[figure.number][x_idx][y_idx]:
                    hover_value = 'NaN'
                else:
                    hover_value = self.interp_models[figure.number]([x], [y])
                figure.command = "hoverPlot(%s, %s, %s, %s)" % (figure.number, x, y, hover_value)


        dt_gids = self.plot(figure, operation_group, metric, range1_name, range2_name)
        # Save the array of GIDs so we can later look op for the on_click events
        self.datatype_gids = dt_gids
        self.figures[figure.number] = figure
        figure_nrs[metric] = figure.number
        figure.canvas.mpl_connect('button_press_event', _click_event)
        figure.canvas.mpl_connect('motion_notify_event', _hover_event)
        figure.canvas.draw()


