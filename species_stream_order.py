from __future__ import print_function
import datetime
import logging
import geodatabase_tempfile

import arcpy

import env_manager

log = logging.getLogger("fish_species_occurrence")
logging.basicConfig()

log.info('Start\t{}'.format(datetime.datetime.now().time()))


def get_max_stream_order_by_huc(nhd_flowline, huc12s,):
    """
       Attaches the maximum stream order in each huc12 to the hucs on a new output layer
    :param nhd_data_gdb_path: Path to the geodatabase that has the NHD flowline features in it
    :return: None - attaches max stream order to each HUC12
    """

    log.info('Set working directory to NHDPlusV2\t{}'.format(datetime.datetime.now().time()))

    # join nhdFlowline to HUC12's
    log.info('Spatial Join HUC12 to NHD\t{}'.format(datetime.datetime.now().time()))

    flowline_features = geodatabase_tempfile.create_gdb_name("FlowlineSpatialJoin")
    arcpy.SpatialJoin_analysis(nhd_flowline, huc12s, flowline_features, "JOIN_ONE_TO_ONE",
                               match_option="HAVE_THEIR_CENTER_IN")

    # create layers
    huc12_layer = "HUC12_layer"
    arcpy.MakeFeatureLayer_management(huc12s, huc12_layer)
    flowline_layer = "Flowline_layer"
    arcpy.MakeFeatureLayer_management(flowline_features, flowline_layer)
    try:  # start a try block so we can clean up the feature layers no matter whether we exit this block on purpose or with an exception
        # exclude null and coastline from flowlines layer
        arcpy.SelectLayerByAttribute_management(flowline_layer, "NEW_SELECTION",
                                                '"StreamOrde" IS NOT NULL AND "StreamOrde" > 0')

        # Summarize HUC12 to find max stream order for each watershed
        log.info('Run spatial join stats\t{}'.format(datetime.datetime.now().time()))
        arcpy.Statistics_analysis(flowline_layer, "Stats_1", [["StreamOrde", "MAX"]], "HUC_12")

        # join field to HUC12's
        all_fields = [field.name for field in arcpy.ListFields(flowline_features)]

        if "MAX_StreamOrde" in all_fields:
            arcpy.DeleteField_management(flowline_features, "MAX_StreamOrde")

        log.info('Join field to HUC12\'s\t{}'.format(datetime.datetime.now().time()))
        arcpy.JoinField_management(target_features, "HUC_12", "Stats_1", "HUC_12", ["MAX_StreamOrde"])
    finally:
        arcpy.Delete_management(huc12_layer)
        arcpy.Delete_management(flowline_layer)

    return flowline_features


def build_codeblock():

    # set working directory - fish occurence (2)
    arcpy.env.workspace = "C:/Users/15303/Documents/CWS_Programming/species_occurence/species_ranges.gdb"
    arcpy.env.overwriteOutput = True
    log.info('Set working directory to species ranges\t{}'.format(datetime.datetime.now().time()))

    # creates list of all features classes in working directory (watershed level fish species occurence)
    log.info('List feature classes\t{}'.format(datetime.datetime.now().time()))
    features = arcpy.ListFeatureClasses()

    # initiate codeblock string
    codeblock = """def getProbability(species, stream_order, join_count):"""

    # finds minimum of maximum stream orders for every species of fish
    for i in features:

        # Create feature layer for fish
        fish_layer = i + "_layer"
        arcpy.MakeFeatureLayer_management(i, fish_layer)
        # select HUC12's by species occurrence and run (min) stats
        try:
            log.info(i + ' select by location\t{}'.format(datetime.datetime.now().time()))
            arcpy.SelectLayerByLocation_management(huc12_layer, "HAVE_THEIR_CENTER_IN", fish_layer)

            log.info(i + ' summary statistics\t{}'.format(datetime.datetime.now().time()))
            arcpy.Statistics_analysis(huc12_layer, "Stats_" + i, [["MAX_StreamOrde", "MIN"]])
        finally:
            arcpy.Delete_management(fish_layer)

        cursor = arcpy.da.SearchCursor("Stats_" + i, ['MIN_MAX_StreamOrde'])
        for row in cursor:
            log.info(row[0])
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

        log.info(dict)  # copy output as plain text
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

    log.info(codeblock)
    return codeblock


def get_species_feature_classes(workspace):
    """
        Gets all the species feature classes in workspace. Tries to be smart by limiting only
        to polygon feature classes, but doesn't filter GDB results otherwise. Best to use
        a pre-filtered database.
    :param workspace:
    :return:
    """
    with env_manager.EnvManager(workspace=workspace):
        log.info('List feature classes\t{}'.format(datetime.datetime.now().time()))
        features = arcpy.ListFeatureClasses(feature_type="Polygon")  #creates list of all features classes in working directory (watershed level fish species occurence)

    return features


if __name__ == "__main__":  # if this code is being executed, instead of imported

    arcpy.env.workspace = "C:/Users/15303/Documents/CWS_Programming/species_occurence/species_ranges.gdb"
    arcpy.env.overwriteOutput = True
    log.info('Set working directory\t{}'.format(datetime.datetime.now().time()))

    target_features = "C:/Users/15303/Documents/CWS_Programming/species_occurence/NHDPlusV2.gdb/NHDFlowline_Network" #NHD data/streams to join to watersheds
    arcpy.CopyFeatures_management(target_features, "in_memory/FlowlineProbabilities") #copy of nhd data to update with probabilities, to memory


    codeblock = build_codeblock() #gets codeblock (dictionary of dictionaries of probabilities per species)

    features = get_species_feature_classes()

    for join_features in features: #runs spatial join code for every species of fish

        log.info(join_features+' '+'spatial join\t{}'.format(datetime.datetime.now().time()))
        out_feature_class ="in_memory"+ "/" + "SpatialJoin" + "_" + join_features #names output feature class based on species name (join features), output to memory
        #performs spatial join
        arcpy.SpatialJoin_analysis(target_features, join_features, out_feature_class, "JOIN_ONE_TO_ONE", match_option = "HAVE_THEIR_CENTER_IN")


        log.info(join_features+' '+'calculate probability\t{}'.format(datetime.datetime.now().time()))
        #adds probability field
        arcpy.AddField_management(out_feature_class, join_features, "TEXT")

        in_table = out_feature_class
        #expression to be used to fill probability field, calls probability function
        expression = "getProbability(" + "'" + join_features + "'" + ", " + "!StreamOrde!, !Join_Count!)" #concatenation to pass speices name into codeblock, getProbability(i, !StreamOrde!, !Join_Count!)


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
        arcpy.CalculateField_management(in_table, join_features, expression, "Python_9.3", codeblock)


        # arcpy.AddIndex_management(out_feature_class, ["COMID"], "idx_COMID", "NON_UNIQUE") #add indexes to spatial join output
        # arcpy.AddIndex_management(out_feature_class, ["COMID", i], "idx_COMID_prob", "NON_UNIQUE")
        # arcpy.AddIndex_management(out_feature_class, [i], "idx_prob", "NON_UNIQUE")

        #updates flowlineprob table (output)
        log.info(join_features + ' ' + 'update flowlineprob table\t{}'.format(datetime.datetime.now().time()))
        arcpy.JoinField_management("in_memory/FlowlineProbabilities", "COMID", out_feature_class, "COMID", [i])

        arcpy.Delete_management(out_feature_class)  # delete spatial join class from memory (not needed)

    arcpy.CopyFeatures_management("in_memory/FlowlineProbabilities", "FlowlineProbabilites") #copy output back to disk
    arcpy.Delete_management("in_memory") #clear memory

    log.info('End\t{}'.format(datetime.datetime.now().time()))





