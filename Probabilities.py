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

# join nhdFlowline to HUC12's
print('Spatial Join HUC12 to NHD', end='\t')
print(datetime.datetime.now().time())
arcpy.SpatialJoin_analysis("NHDFlowline_Network", "HUC12FullState", "FlowlineSpatialJoin", "JOIN_ONE_TO_ONE", match_option = "HAVE_THEIR_CENTER_IN")


#create layers
target_features = "HUC12FullState" #NHD data/streams to join to watersheds
target_layer = "HUC12_layer"
arcpy.MakeFeatureLayer_management(target_features, target_layer)

target_features_1 = "FlowlineSpatialJoin"
target_layer_1 = "Flowline_layer"
arcpy.MakeFeatureLayer_management(target_features_1, target_layer_1)

#exclude null and coastline from flowlines layer
arcpy.SelectLayerByAttribute_management(target_layer_1, "NEW_SELECTION", '"StreamOrde" IS NOT NULL AND "StreamOrde" > 0')


#Summarize HUC12 to find max stream order for each watershed
print('Run spatial join stats', end='\t')
print(datetime.datetime.now().time())
arcpy.Statistics_analysis(target_layer_1, "Stats_1", [["StreamOrde", "MAX"]], "HUC_12")





#creates list of all features classes in working directory (watershed level fish species occurence)
print('List feature classes', end='\t')
print(datetime.datetime.now().time())
features = arcpy.ListFeatureClasses()


# join field to HUC12's
print('Join field to HUC12\'s', end='\t')
print(datetime.datetime.now().time())
arcpy.JoinField_management("HUC12FullState", "HUC_12", "Stats_1", "HUC_12", ["MAX_StreamOrde"])





#finds minimum of maximum stream orders for every species of fish
for i in features:
    if i != "HUC12FullState" and i != "NHDFlowline_Network" and i != "FlowlineProbabilities" and i != "FlowlineSpatialJoin":


        #Create feature layer for fish
        fish_layer = i +"_layer"
        arcpy.MakeFeatureLayer_management(i, fish_layer)

        try:
            print(i + ' select by location', end='\t')
            print(datetime.datetime.now().time())
            arcpy.SelectLayerByLocation_management(target_layer, "HAVE_THEIR_CENTER_IN", fish_layer)

            print(i + ' summary statistics', end='\t')
            print(datetime.datetime.now().time())
            arcpy.Statistics_analysis(target_layer, "Stats_" + i, [["MAX_StreamOrde", "MIN"]])
        finally:
            arcpy.Delete_management(fish_layer)


arcpy.Delete_management(target_layer)
arcpy.Delete_management(target_layer_1)


