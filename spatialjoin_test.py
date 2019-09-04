from __future__ import print_function
import datetime
print('Start', end='\t')
print(datetime.datetime.now().time())
import pandas as pd
import arcpy


#set working directory
arcpy.env.workspace = "C:/Users/15303/Documents/CWS_Programming/species_occurence/species_ranges.gdb"
arcpy.env.overwriteOutput = True
print('Set working directory', end='\t')
print(datetime.datetime.now().time())


features = arcpy.ListFeatureClasses() #creates list of all features classes in working directory (watershed level fish species occurence)
print('List feature classes', end='\t')
print(datetime.datetime.now().time())



target_features = "NHDFlowline" #NHD data/streams to join to watersheds
arcpy.CopyFeatures_management("NHDFlowline", "FlowlineProbabilities") #copy of nhd data to update with probabilities

for i in features: #runs spatial join code for every species of fish

    print(i+' '+'spatial join', end='\t')
    print(datetime.datetime.now().time())
    join_features = i
    out_feature_class = "SpatialJoin" + "_" + join_features #names output feature class based on species name (join features)
    #performs spatial join
    arcpy.SpatialJoin_analysis(target_features, join_features, out_feature_class, "JOIN_ONE_TO_ONE", match_option = "HAVE_THEIR_CENTER_IN")


    print(i+' '+'calculate probability', end='\t')
    print(datetime.datetime.now().time())
    #adds probability field
    arcpy.AddField_management(out_feature_class, i , "TEXT")

    in_table = out_feature_class
    field = i
    #expression to be used to fill probability field, calls probability function
    expression = "getProbability(" + "'" + i + "'" + ", " + "!StreamOrde!, !Join_Count!)" #concatenation to pass speices name into codeblock, getProbability(i, !StreamOrde!, !Join_Count!)


    codeblock = """
def getProbability(species, stream_order, join_count):
    hardhead_dict = {1:10, 2:20, 3:30, 4:40, 5:50, 6:60, 7: 70, 8: 80, 9:90, 10:100}
    rainbow_trout_dict = {1:10, 2:10, 3:10, 4:10, 5:10, 6:10, 7: 10, 8: 10, 9:10, 10:10}
    pdict = {"hardhead" : hardhead_dict, "rainbow_trout": rainbow_trout_dict}
    #if stream segment not in spatial join, set prob to 0    
    if join_count == 0:
        return '0'
    #if stream order is negative (coastline) or does not exist set prob to "NA"
    if stream_order is None or stream_order < 0 or str(stream_order) == 'nan':
        return 'N/A'
    #call stream order/probability dictionary
    else:
        return str(pdict[species][stream_order])"""



#FIXME different probabilities for different species? use dict of dict?



    arcpy.CalculateField_management(in_table, field, expression, "Python_9.3", codeblock)
    #fills out probability field

    arcpy.AddIndex_management(out_feature_class, ["COMID"], "idx_COMID", "NON_UNIQUE") #add indexes to spatial join output
    arcpy.AddIndex_management(out_feature_class, ["COMID", i], "idx_COMID_prob", "NON_UNIQUE")
    arcpy.AddIndex_management(out_feature_class, [i], "idx_prob", "NON_UNIQUE")

    # print(i + ' ' + 'update flowlineprob table', end='\t')
    # print(datetime.datetime.now().time())
    # arcpy.AddField_management("FlowlineProbabilities", i , "DOUBLE") #add field for species
    # arcpy.CalculateField_management("FlowlineProbabilities", i, '!'+out_feature_class+'.Probability!' , "Python_9.3") #fills field with probability
    #FIXME invalid field doesnt exist
    # arcpy.JoinField_management("FlowlineProbabilities", "COMID", out_feature_class, "COMID", [i])





