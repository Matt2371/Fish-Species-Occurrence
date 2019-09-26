from __future__ import print_function
import datetime
import logging
import os

import arcpy

import geodatabase_tempfile
from PISCES import api
from PISCES import local_vars
import env_manager

# Constants and configuration items
FLOWLINES = r"C:\Users\dsx\Code\belleflopt\data\NHDPlusV2\NHDPlusV2.gdb\NHDFlowline_Network"
HUC12S = r"C:\Users\dsx\Code\PISCES\data\PISCES_map_data.gdb\HUC12FullState"
SPECIES_GROUP = "FlowSensitiveV2"
HISTORICAL_PRESENCE_TYPES = local_vars.historic_obs_types
CURRENT_PRESENCE_TYPES = local_vars.current_obs_types
RATE = 0.5  # exponential base for decaying presence probability
MAX_PROBABILITY = 0.9  # Probability to use for the MIN(Max Stream Order) for each species - decays at RATE from there
ABOVE_MAX_PROBABILITY = 1  # Probability to use for stream orders larger than MIN(Max Stream Order)


def get_max_stream_order_by_huc(nhd_flowline=FLOWLINES, huc12s=HUC12S,):
    """
       Attaches the maximum stream order in each huc12 to the hucs on a new output layer
    :param nhd_data_gdb_path: Path to the geodatabase that has the NHD flowline features in it
    :return: geodatabase feature class of huc 12s with max stream order attached
    """

    log.info('Set working directory to NHDPlusV2\t{}'.format(datetime.datetime.now().time()))

    # join nhdFlowline to HUC12's
    log.info('Spatial Join HUC12 to NHD\t{}'.format(datetime.datetime.now().time()))

    flowline_features = geodatabase_tempfile.create_gdb_name("FlowlineSpatialJoin")
    arcpy.SpatialJoin_analysis(nhd_flowline, huc12s, flowline_features, "JOIN_ONE_TO_ONE",
                               match_option="HAVE_THEIR_CENTER_IN")

    # create layers
    flowline_layer = "Flowline_layer"
    arcpy.MakeFeatureLayer_management(flowline_features, flowline_layer)
    try:  # start a try block so we can clean up the feature layers no matter whether we exit this block on purpose or with an exception
        # exclude null and coastline from flowlines layer
        arcpy.SelectLayerByAttribute_management(flowline_layer, "NEW_SELECTION",
                                                '"StreamOrde" IS NOT NULL AND "StreamOrde" > 0')

        # Summarize HUC12 to find max stream order for each watershed
        log.info('Run spatial join stats\t{}'.format(datetime.datetime.now().time()))
        stats_table = geodatabase_tempfile.create_gdb_name("stream_order_stats")
        arcpy.Statistics_analysis(flowline_layer, stats_table, [["StreamOrde", "MAX"]], "HUC_12")

        log.info('Join field to HUC12\'s\t{}'.format(datetime.datetime.now().time()))
        arcpy.JoinField_management(flowline_features, "HUC_12", stats_table, "HUC_12", ["MAX_StreamOrde"])
    finally:
        arcpy.Delete_management(flowline_layer)

    return flowline_features


def get_min_max_stream_order_for_species(species_name, species_range, huc12_layer):
    """
        Given a path to a species range and an input feature layer of huc 12s, gets the minimum MAX_StreamOrde in
        the range
    :param species_range:
    :param huc12_layer:
    :return:
    """
    # select HUC12's by species occurrence and run (min) stats
    species_range_query = "HUC_12 in ('{}')".format("','".join(species_range))
    log.info(species_range + ' select by location\t{}'.format(datetime.datetime.now().time()))
    arcpy.SelectLayerByAttribute_management(huc12_layer, selection_type="NEW_SELECTION", where_clause=species_range_query)

    stats_table = "Stats_{}".format(species_name)
    log.info(species_range + ' summary statistics\t{}'.format(datetime.datetime.now().time()))
    arcpy.Statistics_analysis(huc12_layer, stats_table, [["MAX_StreamOrde", "MIN"]])

    cursor = arcpy.da.SearchCursor(stats_table, ['MIN_MAX_StreamOrde'])
    for row in cursor:  # there's only one row, so this method should be OK to get the correct value
        log.info(row[0])
        min_stream = row[0]

    return min_stream


def build_codeblock(huc12s,
                    species_range_geodatabase=SPECIES_RANGES,
                    rate=RATE,
                    max_probability=MAX_PROBABILITY,
                    above_max_probability=ABOVE_MAX_PROBABILITY):
    """
        Builds the code block with the probabilities for each species by stream order that we'll use when we run field
        calculator.
    :param huc12s:
    :param rate:
    :param max_probability:
    :param above_max_probability:
    :param species_range_geodatabase:
    :return:
    """
    huc12_layer = "HUC12_layer"
    arcpy.MakeFeatureLayer_management(huc12s, huc12_layer)
    try:
        # set working directory - fish occurence (2)
        arcpy.env.workspace = species_range_geodatabase
        log.info('Set working directory to species ranges\t{}'.format(datetime.datetime.now().time()))

        # creates list of all features classes in working directory (watershed level fish species occurence)
        log.info('List feature classes\t{}'.format(datetime.datetime.now().time()))
        species_features = arcpy.ListFeatureClasses()

        # finds minimum of maximum stream orders for every species of fish
        species_dict = {}
        for species in species_features:

            min_stream = get_min_max_stream_order_for_species(os.path.join(species_range_geodatabase, species), huc12_layer)

            individual_dict = {}
            stream_list = [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
            iteration = 1
            for j in stream_list:  # count down stream orders
                if j > min_stream:
                    individual_dict[j] = above_max_probability
                if j == min_stream:
                    individual_dict[j] = max_probability
                if j <= min_stream:
                    individual_dict[j] = max_probability * (rate) ** iteration
                    iteration += 1  # if i is less than or equal to min stream order, decrease probability per iteration exponentially

            log.info(individual_dict)  # copy output as plain text
            species_dict[species] = individual_dict

        # initiate codeblock string with the species dict outside of the function
        codeblock = "pdict = {}".format(str(species_dict))

        codeblock += """def getProbability(species, stream_order, join_count):
\t#if stream segment not in spatial join, set prob to 0    
\tif join_count == 0:
\t\treturn '0'
\t\t#if stream order is negative (coastline) or does not exist set prob to "NA"
\tif stream_order is None or stream_order < 0 or str(stream_order) == 'nan':
\t\treturn 'N/A'
\t\t#call stream order/probability dictionary
\telse:
\t\treturn str(pdict[species][stream_order])"""

        log.info(codeblock)
    finally:
        arcpy.Delete_management(huc12_layer)

    return codeblock


def get_species_data(species_group=SPECIES_GROUP,
                     presence_for_min_max=HISTORICAL_PRESENCE_TYPES,
                     presence_for_probabilities=CURRENT_PRESENCE_TYPES):
    """
        Retrieves the HUC12s in a species range as a list per species
    :param species_group:
    :param presence_for_min_max:
    :param presence_for_probabilities:
    :return:
    """
    min_max_ranges = api.listing.get_hucs_for_species_in_group_as_list(species_group, presence_for_min_max)
    probability_ranges = api.listing.get_hucs_for_species_in_group_as_list(species_group, presence_for_probabilities)

    return min_max_ranges, probability_ranges


if __name__ == "__main__":  # if this code is being executed, instead of imported

    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.basicConfig(format="%(levelname)s - %(message)s", level=logging.DEBUG)
    log = logging.getLogger("species_stream_order")

    consoleLog = logging.StreamHandler()
    consoleLog.setLevel(logging.INFO)
    log.addHandler(consoleLog)

    log.info('Start\t{}'.format(datetime.datetime.now().time()))

    arcpy.env.workspace = "C:/Users/15303/Documents/CWS_Programming/species_occurence/species_ranges.gdb"
    arcpy.env.overwriteOutput = True
    log.info('Set working directory\t{}'.format(datetime.datetime.now().time()))

    target_features = "C:/Users/15303/Documents/CWS_Programming/species_occurence/NHDPlusV2.gdb/NHDFlowline_Network" #NHD data/streams to join to watersheds
    arcpy.CopyFeatures_management(target_features, "in_memory/FlowlineProbabilities") #copy of nhd data to update with probabilities, to memory

    codeblock = build_codeblock() #gets codeblock (dictionary of dictionaries of probabilities per species)

    min_max_species_ranges, probability_species_ranges = get_species_data(species_group=SPECIES_GROUP,
                     presence_for_min_max=HISTORICAL_PRESENCE_TYPES,
                     presence_for_probabilities=CURRENT_PRESENCE_TYPES)

    for species_id in min_max_species_ranges: # runs spatial join code for every species of fish

        log.info(species_id+' '+'spatial join\t{}'.format(datetime.datetime.now().time()))
        out_feature_class ="in_memory"+ "/" + "SpatialJoin" + "_" + join_features #names output feature class based on species name (join features), output to memory
        #performs spatial join
        arcpy.SpatialJoin_analysis(target_features, join_features, out_feature_class, "JOIN_ONE_TO_ONE", match_option = "HAVE_THEIR_CENTER_IN")


        log.info(join_features+' '+'calculate probability\t{}'.format(datetime.datetime.now().time()))
        #adds probability field
        arcpy.AddField_management(out_feature_class, join_features, "TEXT")

        in_table = out_feature_class
        #expression to be used to fill probability field, calls probability function
        expression = "getProbability(" + "'" + join_features + "'" + ", " + "!StreamOrde!, !Join_Count!)" #concatenation to pass speices name into codeblock, getProbability(i, !StreamOrde!, !Join_Count!)

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





