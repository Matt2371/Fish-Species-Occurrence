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
SPECIES_GROUP = "Wide_Ranging"
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

    # join nhdFlowline to HUC12's
    log.info('Spatial Join HUC12 to NHD\t{}'.format(datetime.datetime.now().time()))

    flowline_features = geodatabase_tempfile.create_gdb_name("FlowlineSpatialJoin")
    arcpy.SpatialJoin_analysis(huc12s, nhd_flowline, flowline_features, "JOIN_ONE_TO_ONE",
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


def select_species_range(range_list, species_name, huc12_layer):
    species_range_query = "HUC_12 in ('{}')".format("','".join(range_list))
    log.info(species_name + ' select by attribute for species range\t{}'.format(datetime.datetime.now().time()))
    arcpy.SelectLayerByAttribute_management(huc12_layer, selection_type="NEW_SELECTION", where_clause=species_range_query)


def get_min_max_stream_order_for_species(species_name, species_range, huc12_layer):
    """
        Given a path to a species range and an input feature layer of huc 12s, gets the minimum MAX_StreamOrde in
        the range
    :param species_name:
    :param species_range:
    :param huc12_layer:
    :return:
    """
    # select HUC12's by species occurrence and run (min) stats
    select_species_range(species_range, species_name, huc12_layer)

    stats_table = "Stats_{}".format(species_name)
    log.info(species_name + ' summary statistics\t{}'.format(datetime.datetime.now().time()))
    log.info(stats_table)
    arcpy.Statistics_analysis(huc12_layer, stats_table, [["MAX_StreamOrde", "MIN"]])

    cursor = arcpy.da.SearchCursor(stats_table, ['MIN_MAX_StreamOrde'])
    min_stream = None
    for row in cursor:  # there's only one row, so this method should be OK to get the correct value
        log.info(row[0])
        min_stream = row[0]

    return min_stream


def build_codeblock(huc12s,
                    species_data,
                    rate=RATE,
                    max_probability=MAX_PROBABILITY,
                    above_max_probability=ABOVE_MAX_PROBABILITY):
    """
        Builds the code block with the probabilities for each species by stream order that we'll use when we run field
        calculator.
    :param huc12s:
    :param species_data: dictionary keyed by species code that includes a list a of HUC12 IDs for the species.
    :param rate:
    :param max_probability:
    :param above_max_probability:
    :return:
    """
    huc12_layer = "HUC12_layer"
    arcpy.MakeFeatureLayer_management(huc12s, huc12_layer)
    try:
        # finds minimum of maximum stream orders for every species of fish
        species_dict = {}
        for species in species_data:

            min_stream = get_min_max_stream_order_for_species(species, species_data[species], huc12_layer)

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

    arcpy.env.workspace = geodatabase_tempfile.get_temp_gdb()
    arcpy.env.overwriteOutput = True
    log.info('Set working gdb to {}\t{}'.format(arcpy.env.workspace, datetime.datetime.now().time()))

    initial_target_features = FLOWLINES
    #arcpy.AddIndex_management(target_features, ["COMID"], "idx2_COMID", "NON_UNIQUE") #add indexes to spatial join output

    joined_flow_data = get_max_stream_order_by_huc(nhd_flowline=initial_target_features)
    target_features = "in_memory/FlowlineProbabilities"
    arcpy.CopyFeatures_management(joined_flow_data, target_features)  # copy of nhd data to update with probabilities, to memory

    huc_12_data = "in_memory/HUC12s"
    arcpy.CopyFeatures_management(joined_flow_data, target_features)  # copy of nhd data to update with probabilities, to memory

    min_max_species_ranges, probability_species_ranges = get_species_data(species_group=SPECIES_GROUP,
                     presence_for_min_max=HISTORICAL_PRESENCE_TYPES,
                     presence_for_probabilities=CURRENT_PRESENCE_TYPES)

    codeblock = build_codeblock(HUC12S, min_max_species_ranges)  # gets codeblock (dictionary of dictionaries of probabilities per species)

    huc_12_layer = "SPECIES_RANGE_SELECTION_LAYER"
    arcpy.MakeFeatureLayer_management(HUC12S, huc_12_layer)
    for species_id in min_max_species_ranges:  # runs spatial join code for every species of fish

        select_species_range(min_max_species_ranges[species_id], species_id, huc_12_layer)

        log.info('{} spatial join\t{}'.format(species_id, datetime.datetime.now().time()))
        out_feature_class ="in_memory" + "/" + "SpatialJoin" + "_" + species_id  # names output feature class based on species name (join features), output to memory
        #performs spatial join
        arcpy.SpatialJoin_analysis(target_features, species_id, out_feature_class, "JOIN_ONE_TO_ONE", match_option="HAVE_THEIR_CENTER_IN")


        log.info(species_id + ' ' + 'calculate probability\t{}'.format(datetime.datetime.now().time()))
        #adds probability field
        arcpy.AddField_management(out_feature_class, species_id, "TEXT")

        in_table = out_feature_class
        # expression to be used to fill probability field, calls probability function
        expression = "getProbability(" + "'" + species_id + "'" + ", " + "!StreamOrde!, !Join_Count!)"  # concatenation to pass speices name into codeblock, getProbability(i, !StreamOrde!, !Join_Count!)

        #fills out probability field
        arcpy.CalculateField_management(in_table, species_id, expression, "Python_9.3", codeblock)

        #arcpy.AddIndex_management(target_features, ["COMID", species_id], "idx_COMID_prob", "NON_UNIQUE")
        #arcpy.AddIndex_management(target_features, [species_id], "idx_prob", "NON_UNIQUE")

        # updates flowlineprob table (output)
        log.info(species_id + ' ' + 'update flowlineprob table\t{}'.format(datetime.datetime.now().time()))
        arcpy.JoinField_management("in_memory/FlowlineProbabilities", "COMID", out_feature_class, "COMID", [species_id])

        arcpy.Delete_management(out_feature_class)  # delete spatial join class from memory (not needed)

    output = os.path.join(arcpy.env.workspace, "FlowlineProbabilites")
    arcpy.CopyFeatures_management("in_memory/FlowlineProbabilities", output)  # copy output back to disk

    log.info("Output Written to Disk at {}".format(output))

    log.info('End\t{}'.format(datetime.datetime.now().time()))





