from __future__ import print_function
import datetime
print('Start', end='\t')
print(datetime.datetime.now().time())
import pandas as pd
import arcpy

#builds codeblock for calculate field
def probabilities_dict():
    # set working directory - flowlines and huc12 (1)
    arcpy.env.workspace = "C:/Users/15303/Documents/CWS_Programming/species_occurence/NHDPlusV2.gdb/"
    arcpy.env.overwriteOutput = True
    print('Set working directory to NHDPlusV2', end='\t')
    print(datetime.datetime.now().time())

    # join nhdFlowline to HUC12's
    print('Spatial Join HUC12 to NHD', end='\t')
    print(datetime.datetime.now().time())
    arcpy.SpatialJoin_analysis("NHDFlowline_Network", "HUC12FullState", "FlowlineSpatialJoin", "JOIN_ONE_TO_ONE",
                               match_option="HAVE_THEIR_CENTER_IN")

    # create layers
    target_features = "HUC12FullState"  # NHD data/streams to join to watersheds
    target_layer = "HUC12_layer"
    arcpy.MakeFeatureLayer_management(target_features, target_layer)
    # FIXME: error when running select by location with fish occurrence later on

    target_features_1 = "FlowlineSpatialJoin"
    target_layer_1 = "Flowline_layer"
    arcpy.MakeFeatureLayer_management(target_features_1, target_layer_1)

    # exclude null and coastline from flowlines layer
    arcpy.SelectLayerByAttribute_management(target_layer_1, "NEW_SELECTION",
                                            '"StreamOrde" IS NOT NULL AND "StreamOrde" > 0')

    # Summarize HUC12 to find max stream order for each watershed
    print('Run spatial join stats', end='\t')
    print(datetime.datetime.now().time())
    arcpy.Statistics_analysis(target_layer_1, "Stats_1", [["StreamOrde", "MAX"]], "HUC_12")

    # join field to HUC12's
    fields = [field.name for field in arcpy.ListFields(target_features)]

    if "MAX_StreamOrde" in fields:
        arcpy.DeleteField_management(target_features, "MAX_StreamOrde")

    print('Join field to HUC12\'s', end='\t')
    print(datetime.datetime.now().time())
    arcpy.JoinField_management(target_features, "HUC_12", "Stats_1", "HUC_12", ["MAX_StreamOrde"])

    # set working directory - fish occurence (2)
    arcpy.env.workspace = "C:/Users/15303/Documents/CWS_Programming/species_occurence/species_ranges.gdb"
    arcpy.env.overwriteOutput = True
    print('Set working directory to species ranges', end='\t')
    print(datetime.datetime.now().time())

    # creates list of all features classes in working directory (watershed level fish species occurence)
    print('List feature classes', end='\t')
    print(datetime.datetime.now().time())
    features = arcpy.ListFeatureClasses()

    # initiate codeblock string
    codeblock = """
def getProbability(species, stream_order, join_count):"""

    # finds minimum of maximum stream orders for every species of fish
    for i in features:

        # Create feature layer for fish
        fish_layer = i + "_layer"
        arcpy.MakeFeatureLayer_management(i, fish_layer)
        # select HUC12's by species occurrence and run (min) stats
        try:
            print(i + ' select by location', end='\t')
            print(datetime.datetime.now().time())
            arcpy.SelectLayerByLocation_management(target_layer, "HAVE_THEIR_CENTER_IN", fish_layer)

            print(i + ' summary statistics', end='\t')
            print(datetime.datetime.now().time())
            arcpy.Statistics_analysis(target_layer, "Stats_" + i, [["MAX_StreamOrde", "MIN"]])
        finally:
            arcpy.Delete_management(fish_layer)

        cursor = arcpy.da.SearchCursor("Stats_" + i, ['MIN_MAX_StreamOrde'])
        for row in cursor:
            print(row[0])
            min_stream = row[0]

        dict = {}
        stream_list = [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
        iteration = 1
        rate = 0.5  # exponential base
        max_probability = 0.9  # initial probability
        for j in stream_list:  # count down stream orders
            if j > min_stream:
                dict[j] = max_probability
            if j == min_stream:
                dict[j] = max_probability
            if j == 1:
                dict[j] = max_probability * (rate) ** iteration
                break
            if j <= min_stream:
                dict[j] = max_probability * (rate) ** iteration
                iteration += 1  # if i is less than or equal to min stream order, decrease probability per iteration exponentially

        print(dict)  # copy output as plain text
        string_dict = str(dict)  # string to be concacenated to codeblock
        codeblock += ("\n" + "\t" + i + "_dict" + "=" + string_dict)  # add dictionary to codeblock

    # builds dict of dicts
    codeblock += ("\n" + "\t" + "pdict = {")  # initiate dict of dicts
    iteration = 0  # keeps track of number of interations
    for i in features:
        iteration += 1
        if iteration != len(features):
            codeblock += ("\'" + i + "\'" + ":" + i + "_dict" + ",")  # append string with comma at end
        if iteration == len(features):
            codeblock += ("\'" + i + "\'" + ":" + i + "_dict" + ",")  # no comma

    codeblock += "}"  # close dict of dicts

    codeblock += """
#pdict = {"hardhead" : hardhead_dict, "rainbow_trout": rainbow_trout_dict}
#if stream segment not in spatial join, set prob to 0    
\tif join_count == 0:
\t\treturn '0'
\t\t#if stream order is negative (coastline) or does not exist set prob to "NA"
\tif stream_order is None or stream_order < 0 or str(stream_order) == 'nan':
\t\treturn 'N/A'
\t\t#call stream order/probability dictionary
\telse:
\t\treturn str(pdict[species][stream_order])"""

    print(codeblock)

    arcpy.Delete_management(target_layer)
    arcpy.Delete_management(target_layer_1)
    return codeblock


#set working directory
arcpy.env.workspace = "C:/Users/15303/Documents/CWS_Programming/species_occurence/species_ranges.gdb"
arcpy.env.overwriteOutput = True
print('Set working directory', end='\t')
print(datetime.datetime.now().time())


features = arcpy.ListFeatureClasses() #creates list of all features classes in working directory (watershed level fish species occurence)
print('List feature classes', end='\t')
print(datetime.datetime.now().time())



target_features = "C:/Users/15303/Documents/CWS_Programming/species_occurence/NHDPlusV2.gdb/NHDFlowline_Network" #NHD data/streams to join to watersheds
arcpy.CopyFeatures_management(target_features, "in_memory/FlowlineProbabilities") #copy of nhd data to update with probabilities, to memory


codeblock = probabilities_dict() #gets codeblock (dictionary of dictionaries of probabilities per species)

for i in features: #runs spatial join code for every species of fish

    print(i+' '+'spatial join', end='\t')
    print(datetime.datetime.now().time())
    join_features = i
    out_feature_class ="in_memory"+ "/" + "SpatialJoin" + "_" + join_features #names output feature class based on species name (join features), output to memory
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


#     codeblock = """
# def getProbability(species, stream_order, join_count):
#     hardhead_dict = {1:10, 2:20, 3:30, 4:40, 5:50, 6:60, 7: 70, 8: 80, 9:90, 10:100}
#     rainbow_trout_dict = {1:10, 2:10, 3:10, 4:10, 5:10, 6:10, 7: 10, 8: 10, 9:10, 10:10}
#     pdict = {"hardhead" : hardhead_dict, "rainbow_trout": rainbow_trout_dict}
#     #if stream segment not in spatial join, set prob to 0
#     if join_count == 0:
#         return '0'
#     #if stream order is negative (coastline) or does not exist set prob to "NA"
#     if stream_order is None or stream_order < 0 or str(stream_order) == 'nan':
#         return 'N/A'
#     #call stream order/probability dictionary
#     else:
#         return str(pdict[species][stream_order])"""






    #fills out probability field
    arcpy.CalculateField_management(in_table, field, expression, "Python_9.3", codeblock)


    # arcpy.AddIndex_management(out_feature_class, ["COMID"], "idx_COMID", "NON_UNIQUE") #add indexes to spatial join output
    # arcpy.AddIndex_management(out_feature_class, ["COMID", i], "idx_COMID_prob", "NON_UNIQUE")
    # arcpy.AddIndex_management(out_feature_class, [i], "idx_prob", "NON_UNIQUE")

    #updates flowlineprob table (output)
    print(i + ' ' + 'update flowlineprob table', end='\t')
    print(datetime.datetime.now().time())
    arcpy.JoinField_management("in_memory/FlowlineProbabilities", "COMID", out_feature_class, "COMID", [i])

    arcpy.Delete_management(out_feature_class) #delete spatial join class from memory (not needed)

arcpy.CopyFeatures_management("in_memory/FlowlineProbabilities", "FlowlineProbabilites") #copy output back to disk
arcpy.Delete_management("in_memory") #clear memory

print('End', end='\t')
print(datetime.datetime.now().time())





