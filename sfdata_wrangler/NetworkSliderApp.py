__author__      = "Gregory D. Erhardt"
__copyright__   = "Copyright 2013 SFCTA"
__license__     = """
    This file is part of sfdata_wrangler.

    sfdata_wrangler is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    sfdata_wrangler is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with sfdata_wrangler.  If not, see <http://www.gnu.org/licenses/>.
"""

import numpy as np
import pandas as pd

from bokeh.plotting import figure
from bokeh.models import Plot, ColumnDataSource
from bokeh.properties import Instance
from bokeh.server.app import bokeh_app
from bokeh.server.utils.plugins import object_page
from bokeh.models.widgets import HBox, Slider, VBoxForm

import Visualizer
from HwyNetwork import HwyNetwork

INPUT_DYNAMEQ_NET_DIR    = "C:/CASA/Data/network/dynameq/validation2010.july19_Sig/Reports/Export"
INPUT_DYNAMEQ_NET_PREFIX = "pb_july19_830p"
TAXI_OUTFILE = "C:/CASA/DataExploration/taxi.h5"     
LOGGING_DIR = "C:/CASA/DataExploration"



def prepareLinkData(self, hwynet, date='2013-02-13'):
    """ 
    Returns a column data source with one record for each link, containing 
    the data necessary for plotting. 
    
    date - string for the date's data to display
    """
        
    # read the highway network
    hwynet = HwyNetwork()
    hwynet.readDTANetwork(INPUT_DYNAMEQ_NET_DIR, INPUT_DYNAMEQ_NET_PREFIX, logging_dir=LOGGING_DIR) 

    # start with the network links as a dataframe
    df = hwynet.getRoadLinkDataFrame()
        
    # now get the link speeds for the date, and for each hour
    store = pd.HDFStore(TAXI_OUTFILE)
    for hour in range(0,24):
        h = str(hour)
            
        # get the data
        query = "date==Timestamp('" + date + "') and hour==" + h
        obs_df = store.select('link_tt', where=query) 

        # append the hour to the end of each column name for this query
        obs_df.drop('date', axis=1, inplace=True)
        obs_df.rename(columns=lambda x: x+h, inplace=True)

        # merge, keeping all links
        df = pd.merge(df, obs_df, how='left', 
                      left_on=['ID'], right_on=['link_id'+h])
                        
        """ Calculations start here """
        # there are zero observations if its not in the righthand database
        df['observations'+h].replace(to_replace=np.nan, value=0, inplace=True)
            
        # calculate some extra fields
        length_tt_fftt = pd.Series(zip(df['LENGTH'], df['tt_mean'+h], df['FFTIME']))
        df['speed'+h] = length_tt_fftt.apply(Visualizer.calculateSpeed)
            
        tt_fftt = pd.Series(zip(df['tt_mean'+h], df['FFTIME']))
        df['tt_ratio'+h] = tt_fftt.apply(Visualizer.calculateTravelTimeRatio)
            
        # map the link colors based on the travel time ratio
        df['color'+h] = df['tt_ratio'+h].apply(Visualizer.getLinkTTRatioColor)
                
    store.close()

    df['color'] = df['color0']

    source = ColumnDataSource(df)
    return source
        

class NetworkSliderApp(HBox):
    """A browser-based, interactive plot with slider controls.
    For exploring network attributes. 
    """

    extra_generated_classes = [["NetworkSliderApp", "NetworkSliderApp", "HBox"]]

    inputs = Instance(VBoxForm)

    hour = Instance(Slider)
    plot = Instance(Plot)

    source = Instance(ColumnDataSource)

    @classmethod
    def create(cls, hwynet):
        """One-time creation of app's objects.

        This function is called once, and is responsible for
        creating all objects (plots, datasources, etc)
        """
        obj = cls()

        obj.source = obj.prepareLinkData(hwynet)
        
        obj.hour = Slider(
            title="Time of Day", name="hour",
            value=0, start=0, end=24, step=1
        )

        # Generate a figure container
        # TODO - add box_zoom tool back in when bokeh makes it work
        #        without distorting the proportions
        plot = figure(plot_width=900, # in units of px
                      plot_height=900,              
                      x_axis_type=None, 
                      y_axis_type=None,
                      tools="pan,wheel_zoom,reset,hover,save", 
                      title="SF Taxi Speeds") 
        
        # plot the links
        plot.multi_line(xs='X', 
                        ys='Y', 
                        line_width='LANES',  
                        line_color='color', 
                        source=obj.source)    

        obj.plot = plot
        obj.update_data()

        obj.inputs = VBoxForm(children=[obj.hour])

        obj.children.append(obj.inputs)
        obj.children.append(obj.plot)

        return obj


    def setup_events(self):
        """Attaches the on_change event to the value property of the widget.

        The callback is set to the input_change method of this app.
        """
        super(NetworkSliderApp, self).setup_events()
        if not self.hour:
            return

        # Slider event registration
        for w in ["hour"]:
            getattr(self, w).on_change('value', self, 'input_change')


    def input_change(self, obj, attrname, old, new):
        """Executes whenever the input form changes.

        It is responsible for updating the plot, or anything else you want.

        Args:
            obj : the object that changed
            attrname : the attr that changed
            old : old value of attr
            new : new value of attr
        """
        self.update_data()


    def update_data(self):
        """Called each time that any watched property changes.

        Update the data with the details columns specific to this
        hour. 
        """
        # Get the current slider values
        h = str(self.hour.value)

        self.source.data['color'] = self.source.data['color'+h]




"""
To view this applet directly from a bokeh server, you need to run a 
bokeh-server and point it at the script.  First navigate to a directory
where it is ok for bokeh to write temporary files, then call: 

    bokeh-server --script NetworkSlidersApp.py

Now navigate to the following URL in a browser:

    http://localhost:5006/bokeh/sf
"""

@bokeh_app.route("/bokeh/sf/")
@object_page("NetworkSlider")
def make_sliders():
    app = NetworkSliderApp.create(hwynet)
    return app