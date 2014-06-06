# -*- coding: utf-8 -*-
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

import pandas as pd
import datetime

import transitfeed
            
            

def determineMinDepTime(df):
    """
    Sets the DEPTIME field to the min value across the group.
    """
    minTime = df['DEPTIME'].min()
    df['MINDEPTIME'] = minTime        
    return df

def determineMaxArrTime(df):
    """
    Sets the ARRTIME field to the min value across the group.
    """
    maxTime = df['ARRTIME'].max()
    df['MAXARRTIME'] = maxTime        
    return df
    

def getWrapAroundTime(dateString, timeString):
    """
    Converts a string in the format '%H:%M:%S' to a datetime object.
    Accounts for the convention where service after midnight is counted
    with the previous day, so input times can be >24 hours. 
    """        
    nextDay = False
    hr, min, sec = timeString.split(':')
    if int(hr)>= 24:
        hr = str(int(hr) - 24)
        timeString = hr + ':' + min + ':' + sec
        nextDay = True
        
    datetimeString = dateString + ' ' + timeString    
    time = pd.to_datetime(datetimeString, format='%Y%m%d %H:%M:%S')
        
    if nextDay: 
       time = time + pd.DateOffset(days=1)
    
    return time
        
                                                
            
class GTFSHelper():
    """ 
    Methods used for loading and converting General Transit Feed Specification
    (GTFS) files, and relating them to AVL/APC data. 
    
    """

    # specifies how to read in each column from raw input files
    #  columnName,       stringLength, index(0/1)
    COLUMNS = [
        ['START_DATE',        0, 1], 
        ['END_DATE',          0, 1], 
        ['DOW',               0, 1], 
        ['TOD',               0, 0], 
        ['ROUTE_ID',          0, 1], 
        ['DIRECTION_ID',      0, 1], 
        ['TRIP_ID',           0, 1], 
        ['STOP_SEQUENCE',     0, 1], 
        ['STOP_ID',           0, 0], 
        #['ROUTE',             0, 0], 
        #['PATTCODE',          0, 0], 
        #['DIR',               0, 0], 
        ['TRIP',              0, 0], 
        #['SEQ',               0, 0], 
        #['QSTOP',             0, 0], 
        ['AGENCY_ID',        10, 0], 
        ['BLOCK_ID',          0, 0], 
        ['SHAPE_ID',          0, 0], 
        ['ROUTE_SHORT_NAME', 32, 0], 
        ['ROUTE_LONG_NAME',  32, 0], 
        ['ROUTE_TYPE',        0, 0], 
        ['TRIP_HEADSIGN',    32, 0], 
        ['FARE',              0, 0], 
        ['STOP_NAME',        32, 0], 
        ['STOP_LAT',          0, 0], 
        ['STOP_LON',          0, 0], 
        ['SOL',               0, 0],
        ['EOL',               0, 0],
        ['ARRIVAL_TIME',      0, 0], 
        ['DEPARTURE_TIME',    0, 0]
        ] 
                


    def processRawData(self, infile, outfile):
        """
        Read GTFS, cleans it, processes it, and writes it to an HDF5 file.
        
        infile  - in GTFS format
        outfile - output file name in h5 format, same as AVL/APC format
        """
        
        print datetime.datetime.now(), 'Converting raw data in file: ', infile
        
        # convert column specs 
        colnames = []   
        stringLengths= {}
        indexColumns = []
        for col in self.COLUMNS: 
            name = col[0]
            stringLength = col[1]
            index = col[2]
            
            colnames.append(name)
            if (stringLength>0): 
                stringLengths[name] = stringLength
            if index==1: 
                indexColumns.append(name)
                
        # create an empty list of dictionaries to store the data
        data = []
        
        # establish the feed
        tfl = transitfeed.Loader(feed_path=infile)
        schedule = tfl.Load()

        # determine the dates
        dateRange = schedule.GetDateRange()
        startDate = dateRange[0]
        endDate = dateRange[1]
        
        # create one record for each trip-stop
        tripList = schedule.GetTripList()
        for trip in tripList:
            
            # determine route attributes
            route = schedule.GetRoute(trip.route_id)
            
            # calculate fare--assume just based on route ID
            fare = 0
            fareAttributeList = schedule.GetFareAttributeList()
            for fareAttribute in fareAttributeList:
                fareRuleList = fareAttribute.GetFareRuleList()
                for fareRule in fareRuleList:
                    if fareRule.route_id == trip.route_id: 
                        fare = fareAttribute.price
            
            # one record for each stop time
            stopTimeList = trip.GetStopTimes()            
            for stopTime in stopTimeList:
                record = {}
                
                # calendar attributes
                record['START_DATE'] = pd.to_datetime(startDate, format='%Y%m%d')
                record['END_DATE']   = pd.to_datetime(endDate,   format='%Y%m%d') 
                record['DOW']        = int(trip.service_id)
                record['TOD']        = 0 
                
                # GTFS index attributes
                record['ROUTE_ID']     = int(trip.route_id)
                record['DIRECTION_ID'] = int(trip.direction_id)
                record['TRIP_ID']      = int(trip.trip_id)
                record['STOP_SEQUENCE']= int(stopTime.stop_sequence)
                record['STOP_ID']      = int(stopTime.stop.stop_id)
                
                # AVL/APC index attributes
                #record['ROUTE']         
                #record['PATTCODE']      
                #record['DIR']           
                record['TRIP']      = 0    # will contain HHMM of departure from first stop
                #record['SEQ']           
                #record['QSTOP']         
                
                
                # route/trip attributes
                record['AGENCY_ID']        = str(route.agency_id)
                record['BLOCK_ID']         = int(trip.block_id)
                record['SHAPE_ID']         = int(trip.shape_id)
                record['ROUTE_SHORT_NAME'] = str(route.route_short_name)
                record['ROUTE_LONG_NAME']  = str(route.route_long_name)
                record['ROUTE_TYPE']       = int(route.route_type)
                record['TRIP_HEADSIGN']    = str(trip.trip_headsign)
                record['FARE']             = float(fare)  
                
                # stop attriutes
                record['STOP_NAME']        = str(stopTime.stop.stop_name)
                record['STOP_LAT']         = float(stopTime.stop.stop_lat)
                record['STOP_LON']         = float(stopTime.stop.stop_lon)
                record['SOL'] = 0   # start of line
                record['EOL'] = 0   # end of line
                
                # stop times, dealing with wrap-around for times past midnight            
                record['ARRIVAL_TIME']   = getWrapAroundTime(startDate, stopTime.arrival_time)
                record['DEPARTURE_TIME'] = getWrapAroundTime(startDate, stopTime.departure_time)
                
                # will be used to calculate TRIP, and start of line and end of line
                # 'DEPTIME' contains string HHMM of departure time from stop
                hr, min, sec = stopTime.departure_time.split(':')
                record['DEPTIME'] = hr + min + sec
                # 'ARRTIME' contains string HHMM of arrival time at stop
                hr, min, sec = stopTime.arrival_time.split(':')
                record['ARRTIME'] = hr + min + sec
                
                data.append(record)
                                
        # convert to data frame
        print "  adding %i trip-stop records" % len(data)
        df = pd.DataFrame(data)
        
        # sort rows 
        df.sort(indexColumns, inplace=True)
        
        # calculate group attributes of the TRIP
        groupby = ['START_DATE', 'END_DATE', 'DOW', 'ROUTE_ID', 'DIRECTION_ID', 'TRIP_ID']
        df = df.groupby(groupby).apply(determineMinDepTime)
        df = df.groupby(groupby).apply(determineMaxArrTime)
        
        for i, row in df.iterrows():
            # trip
            df['TRIP'][i] = int(df['MINDEPTIME'][i])/100
            
            # start of line
            if (df['DEPTIME'][i] == df['MINDEPTIME'][i]): 
                df['SOL'][i] = 1
            # end of line
            if (df['ARRTIME'][i] == df['MAXARRTIME'][i]): 
                df['EOL'][i] = 1
                
        
        # keep only relevant columns, sorted
        df = df[colnames]
        
        # write the data
        store = pd.HDFStore(outfile)
        try: 
            store.append('gtfs', df, data_columns=True, 
                    min_itemsize=stringLengths)
        except ValueError: 
            store = pd.HDFStore(outfile)
            print 'Structure of HDF5 file is: '
            print store.gtfs.dtypes
            store.close()
                
            print 'Structure of current dataframe is: '
            print df.dtypes
                
            raise

        store.close()
