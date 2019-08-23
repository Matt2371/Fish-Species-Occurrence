from __future__ import print_function
import datetime
print('Start', end='\t')
print(datetime.datetime.now().time())
import pandas as pd
import arcpy


#set working directory
arcpy.env.workspace = "C:/Users/15303/Documents/CWS_Programming/species_occurence/species_ranges.gdb"
print('Set working directory', end='\t')
print(datetime.datetime.now().time())


features = arcpy.ListFeatureClasses() #creates list of all features classes in working directory (watershed level fish species occurence)
print('List feature classes', end='\t')
print(datetime.datetime.now().time())



target_features = "NHDFlowline" #NHD data/streams to join to watersheds

for i in features: #runs spatial join code for every species of fish
    print(i+'_'+'spatial join', end='\t')
    print(datetime.datetime.now().time())
    join_features = i
    out_feature_class = "SpatialJoin" + "_" + join_features #names output feature class based on species name (join features)
    #performs spatial join
    arcpy.SpatialJoin_analysis(target_features, join_features, out_feature_class, "JOIN_ONE_TO_ONE", match_option = "HAVE_THEIR_CENTER_IN")


    print(i+'_'+'calculate probability', end='\t')
    print(datetime.datetime.now().time())
    #adds probability field
    arcpy.AddField_management(out_feature_class, "Probability", "TEXT")

    in_table = out_feature_class
    field = "Probability"
    #expression to be used to fill probability field, calls probability function
    expression = "getProbability(!StreamOrde!, !Join_Count!)"
    #defines probability function
    codeblock = """
def getProbability(stream_order, join_count):
    pdict = {1:10, 2:20, 3:30, 4:40, 5:50, 6:60, 7: 70, 8: 80, 9:90, 10:100}
    #if stream segment not in spatial join, set prob to 0    
    if join_count == 0:
        return '0'
    #if stream order is negative (coastline) or does not exist set prob to "NA"
    if stream_order is None or stream_order < 0 or str(stream_order) == 'nan':
        return 'N/A'
    #call stream order/probability dictionary
    else:
        return str(pdict[stream_order])"""

    arcpy.CalculateField_management(in_table, field, expression, "Python_9.3", codeblock)
    #fills out probability field


