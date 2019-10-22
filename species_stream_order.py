from __future__ import print_function
import datetime
import logging
import os

import arcpy

import geodatabase_tempfile
from PISCES import api
from PISCES import local_vars
import env_manager

DEBUG = True  # just handles cleanup operations differently when on.

# Constants and configuration items
FLOWLINES = r"C:\Users\dsx\Code\belleflopt\data\NHDPlusV2\NHDPlusV2.gdb\NHDFlowline_Network"
HUC12S = r"C:\Users\dsx\Code\PISCES\data\PISCES_map_data.gdb\HUC12FullState"
SPECIES_GROUP = "Wide_Ranging"
HISTORICAL_PRESENCE_TYPES = local_vars.historic_obs_types
CURRENT_PRESENCE_TYPES = local_vars.current_obs_types
RATE = 0.5  # exponential base for decaying presence probability
MAX_PROBABILITY = 0.9  # Probability to use for the MIN(Max Stream Order) for each species - decays at RATE from there
ABOVE_MAX_PROBABILITY = 1  # Probability to use for stream orders larger than MIN(Max Stream Order)


def _make_field_map(join_features, target_features):
    """
        Make a field map - lets us skip a bunch of steps by having the Spatial Join tool handle the calculation
        of the maximum stream order per HUC.
    :param join_features:
    :param target_features:
    :return:
    """
    fieldmappings = arcpy.FieldMappings()
    fieldmappings.addTable(target_features)
    fieldmappings.addTable(join_features)

    StreamOrdeFieldIndex = fieldmappings.findFieldMapIndex("StreamOrde")
    fieldmap = fieldmappings.getFieldMap(StreamOrdeFieldIndex)

    # Get the output field's properties as a field object
    field = fieldmap.outputField

    # Rename the field and pass the updated field object back into the field map
    field.name = "max_stream_order"
    field.aliasName = "max_stream_order"
    fieldmap.outputField = field

    # Set the merge rule to mean and then replace the old fieldmap in the mappings object
    # with the updated one
    fieldmap.mergeRule = "max"
    fieldmappings.replaceFieldMap(StreamOrdeFieldIndex, fieldmap)

    return fieldmappings


def get_max_stream_order_by_huc(nhd_flowline=FLOWLINES, huc12s=HUC12S,):
    """
       Attaches the maximum stream order in each huc12 to the hucs on a new output layer
    :param nhd_data_gdb_path: Path to the geodatabase that has the NHD flowline features in it
    :return: geodatabase feature class of huc 12s with max stream order attached
    """

    # join nhdFlowline to HUC12's
    log.info('Getting Maximum Stream Order by HUC\t{}'.format(datetime.datetime.now().time()))

    # we'll make a field map that lets us get the max of the flowline stream orders for each HUC
    field_map = _make_field_map(nhd_flowline, huc12s)

    hucs_with_stream_order = geodatabase_tempfile.create_fast_name("huc12s_with_stream_order")

    flowline_layer = "NHD_FLOWLINES_GT_ZERO"  # we want to remove any stream orders that are -9, which throws everything off
    arcpy.MakeFeatureLayer_management(nhd_flowline, flowline_layer, where_clause="StreamOrde > 0")
    try:
        arcpy.SpatialJoin_analysis(huc12s, flowline_layer, hucs_with_stream_order, "JOIN_ONE_TO_ONE", field_mapping=field_map)
    finally:
        arcpy.Delete_management(flowline_layer)  # cleanup

    return hucs_with_stream_order


def select_species_range(range_list, species_name, huc12_layer):
    log.info("Selecting range for species {}".format(species_name))
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
    log.info(species_name + ' min(max(stream order)) summary statistics\t{}'.format(datetime.datetime.now().time()))
    arcpy.Statistics_analysis(huc12_layer, stats_table, [["max_stream_order", "MIN"]])

    cursor = arcpy.da.SearchCursor(stats_table, ['MIN_max_stream_order'])
    min_stream = None
    for row in cursor:  # there's only one row, so this method should be OK to get the correct value
        min_stream = row[0]

    log.info("Min Stream Order for {} is {}".format(species_name, min_stream))
    if min_stream < 1:
        raise ValueError("Min Stream for {} is {}, which is not a valid stream order - This likely means the stream data"
                         "hasn't been filtered properly (to only real streams), or the join is misconfigured and streams"
                         "outside of the species range are being included.".format(species_id, min_stream))
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

    log.info("Building codeblock")

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
                elif j == min_stream:
                    individual_dict[j] = max_probability
                elif j < min_stream:
                    individual_dict[j] = max_probability * (rate) ** iteration
                    iteration += 1  # if i is less than or equal to min stream order, decrease probability per iteration exponentially

            log.info(individual_dict)  # copy output as plain text
            species_dict[species] = individual_dict

        # initiate codeblock string with the species dict outside of the function
        codeblock = "pdict = {}".format(str(species_dict))

        codeblock += """\n\ndef getProbability(species, stream_order, join_count):
\t#if stream segment not in spatial join, set prob to 0    
\tif join_count is None or join_count == 0:
\t\treturn '0'
\tif stream_order is None or stream_order < 0 or str(stream_order) == 'nan': #if stream order is negative (coastline) or does not exist set prob to None
\t\treturn None
\telse: #call stream order/probability dictionary
\t\treturn pdict[species][stream_order]"""

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
    log.info("Getting species data from PISCES")
    min_max_ranges = api.listing.get_hucs_for_species_in_group_as_list(species_group, presence_for_min_max)
    probability_ranges = api.listing.get_hucs_for_species_in_group_as_list(species_group, presence_for_probabilities)

    return min_max_ranges, probability_ranges


def get_species_data_TEST(species_group="IGNORED_TEST_FUNCTION",
                     presence_for_min_max=HISTORICAL_PRESENCE_TYPES,
                     presence_for_probabilities=CURRENT_PRESENCE_TYPES,
                        species_code="CMC01",):
    """
        Retrieves the HUC12s in a species range as a list per species
    :param species_group:
    :param presence_for_min_max:
    :param presence_for_probabilities:
    :return:
    """
    log.info("Getting species data from PISCES")
    min_max_ranges = api.listing.get_hucs_for_species_as_list(species_code, presence_for_min_max)
    probability_ranges = api.listing.get_hucs_for_species_as_list(species_code, presence_for_probabilities)

    return {species_code: min_max_ranges}, {species_code: probability_ranges}



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

    joined_flow_data = get_max_stream_order_by_huc(nhd_flowline=FLOWLINES, huc12s=HUC12S)
    target_features = "in_memory/FlowlineProbabilities"
    arcpy.CopyFeatures_management(FLOWLINES, target_features)  # copy of nhd data to update with probabilities, to memory

    min_max_species_ranges, probability_species_ranges = get_species_data(species_group=SPECIES_GROUP,
                     presence_for_min_max=HISTORICAL_PRESENCE_TYPES,
                     presence_for_probabilities=CURRENT_PRESENCE_TYPES)

    codeblock = build_codeblock(joined_flow_data, min_max_species_ranges)  # gets codeblock (dictionary of dictionaries of probabilities per species)

    huc_12_layer = "SPECIES_RANGE_SELECTION_LAYER"
    arcpy.MakeFeatureLayer_management(joined_flow_data, huc_12_layer)
    for species_id in probability_species_ranges:  # runs spatial join code for every species of fish

        select_species_range(probability_species_ranges[species_id], species_id, huc_12_layer)

        log.info('{} spatial join\t{}'.format(species_id, datetime.datetime.now().time()))

        # this was much faster when using in_memory datasets, but it was failing randomly after many iterations
        # decided to try it on disk and it appears more stable
        out_feature_class = geodatabase_tempfile.create_gdb_name("SpatialJoin_{}".format(species_id))  #  "in_memory/SpatialJoin_{}".format(species_id)  # names output feature class based on species name (join features), output to memory
        if DEBUG:  # we'll only log this if the flag is set - better strategy would be to log.debug, but we're not setting up logging handlers to separate right now.
            log.info(out_feature_class)

        # performs spatial join - the species range is selected in the huc 12 layer, so only that part should be joined to the target
        arcpy.SpatialJoin_analysis(target_features, huc_12_layer, out_feature_class, "JOIN_ONE_TO_ONE", match_option="HAVE_THEIR_CENTER_IN")

        log.info(species_id + ' ' + 'calculate probability\t{}'.format(datetime.datetime.now().time()))
        #adds probability field
        arcpy.AddField_management(out_feature_class, species_id, "FLOAT")

        in_table = out_feature_class
        # expression to be used to fill probability field, calls probability function
        expression = "getProbability('{}', !StreamOrde!, !Join_Count!)".format(species_id)  # concatenation to pass speices name into codeblock, getProbability(species_id, !StreamOrde!, !Join_Count!)

        #fills out probability field
        arcpy.CalculateField_management(in_table, species_id, expression, "Python_9.3", codeblock)

        #arcpy.AddIndex_management(target_features, ["COMID", species_id], "idx_COMID_prob", "NON_UNIQUE")
        #arcpy.AddIndex_management(target_features, [species_id], "idx_prob", "NON_UNIQUE")

        # updates flowlineprob table (output)
        log.info(species_id + ' ' + 'update flowlineprob table\t{}'.format(datetime.datetime.now().time()))
        arcpy.JoinField_management("in_memory/FlowlineProbabilities", "COMID", out_feature_class, "COMID", [species_id])

        if not DEBUG:
            arcpy.Delete_management(out_feature_class)  # delete spatial join class from memory (not needed)

    output = os.path.join(arcpy.env.workspace, "FlowlineProbabilites")
    arcpy.CopyFeatures_management("in_memory/FlowlineProbabilities", output)  # copy output back to disk

    log.info("Output Written to Disk at {}".format(output))

    log.info('End\t{}'.format(datetime.datetime.now().time()))





