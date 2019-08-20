import pandas as pd
import arcpy


# df = pd.read_csv('Export_Output.csv')

#dictionary for probability/stream order
pdict = {1:10, 2:20, 3:30, 4:40, 5:50, 6:60, 7: 70, 8: 80, 9:90, 10:100}

# for i in range(len(df['OBJECTID'])): #for each stream
# #
# #     streamorder = df.iloc[i, 38]
# #     if df.iloc[i, 1] == 0:
# #         df.iloc[i, 76] = 0
# #     elif streamorder is None or str(streamorder)=='nan': #nan to deal invalid num
# #         df.iloc[i, 76] = 'N/A' #checks for empty data
# #
# #     else:
# #         # print("[{}]".format(streamorder))
# #         df.iloc[i, 76] = pdict[int(streamorder)] #updates prob column
# #
# #     #FIXME: key error, blank spaces in column 38, blank/NA in pdict does not solve issue
# #
# # print(df)

arcpy.env.workspace = "C:/Users/15303/Documents/CWS_Programming/species_occurence/species_ranges.gdb"

#performs spatial join watersheds to rivers

target_features = "NHDFlowline"
join_features = "hardhead"
out_feature_class = "SpatialJoin" + "_" + join_features

arcpy.SpatialJoin_analysis(target_features, join_features, out_feature_class, "JOIN_ONE_TO_ONE", match_option = "HAVE_THEIR_CENTER_IN")


#adds DOUBLE COMID field to join, set equal to PernamentID

arcpy.AddField_management(out_feature_class, "COMID", "DOUBLE")

in_table = out_feature_class
field = "COMID"
expression = "!Permanent_Identifier!"

arcpy.CalculateField_management(in_table, field, expression, "Python_9.3")



#joins NDHPlus data

inFeatures = out_feature_class
joinTable = "C:/Users/15303/Documents/CWS_Programming/species_occurence/NHDPlusCA/NHDPlus18/NHDPlusAttributes/PlusFlowlineVAA.dbf"
inField = "COMID"
joinField = "ComID"


arcpy.JoinField_management(inFeatures, inField, joinTable, joinField)



#adds fields, calculates probability

arcpy.AddField_management(out_feature_class, "Probability", "TEXT")

in_table = out_feature_class
field = "Probability"
expression = "getProbability(!StreamOrde!, !Join_Count!)"
codeblock = """
def getProbability(stream_order, join_count):
    pdict = {1:10, 2:20, 3:30, 4:40, 5:50, 6:60, 7: 70, 8: 80, 9:90, 10:100}

    if join_count == 0:
        return '0'
    if stream_order is None or stream_order < 0 or str(stream_order) == 'nan':
        return 'N/A'
    else:
        return str(pdict[stream_order])"""

arcpy.CalculateField_management(in_table, field, expression, "Python_9.3", codeblock)



