import pandas as pd

# =========================
# DataFrame 1: CAT021
# =========================

columns_021 = ["frn", "item_id", "item_name", "length_str"]

data_021 = [
    [1,  "I021/010", "Data Source Identification",                              "2"],
    [2,  "I021/040", "Target Report Descriptor",                                "1+"],
    [3,  "I021/161", "Track Number",                                            "2"],
    [4,  "I021/015", "Service Identification",                                  "1"],
    [5,  "I021/071", "Time of Applicability for Position",                      "3"],
    [6,  "I021/130", "Position in WGS-84 co-ordinates",                         "6"],
    [7,  "I021/131", "Position in WGS-84 co-ordinates, high res.",              "8"],
    # ["FX", "n.a.",     "Field extension indicator",                               "n.a."],
    [8,  "I021/072", "Time of Applicability for Velocity",                      "3"],
    [9,  "I021/150", "Air Speed",                                               "2"],
    [10, "I021/151", "True Air Speed",                                          "2"],
    [11, "I021/080", "Target Address",                                          "3"],
    [12, "I021/073", "Time of Message Reception of Position",                   "3"],
    [13, "I021/074", "Time of Message Reception of Position-High Precision",    "4"],
    [14, "I021/075", "Time of Message Reception of Velocity",                   "3"],
    # ["FX", "n.a.",     "Field extension indicator",                               "n.a."],
    [15, "I021/076", "Time of Message Reception of Velocity-High Precision",    "4"],
    [16, "I021/140", "Geometric Height",                                        "2"],
    [17, "I021/090", "Quality Indicators",                                      "1+"],
    [18, "I021/210", "MOPS Version",                                            "1"],
    [19, "I021/070", "Mode 3/A Code",                                           "2"],
    [20, "I021/230", "Roll Angle",                                              "2"],
    [21, "I021/145", "Flight Level",                                            "2"],
    # ["FX", "n.a.",     "Field extension indicator",                               "n.a."],
    [22, "I021/152", "Magnetic Heading",                                        "2"],
    [23, "I021/200", "Target Status",                                           "1"],
    [24, "I021/155", "Barometric Vertical Rate",                                "2"],
    [25, "I021/157", "Geometric Vertical Rate",                                 "2"],
    [26, "I021/160", "Airborne Ground Vector",                                  "4"],
    [27, "I021/165", "Track Angle Rate",                                        "2"],
    [28, "I021/077", "Time of Report Transmission",                             "3"],
    # ["FX", "n.a.",     "Field extension indicator",                               "n.a."],
    [29, "I021/170", "Target Identification",                                   "6"],
    [30, "I021/020", "Emitter Category",                                        "1"],
    [31, "I021/220", "Met Information",                                         "1+"],
    [32, "I021/146", "Selected Altitude",                                       "2"],
    [33, "I021/148", "Final State Selected Altitude",                           "2"],
    [34, "I021/110", "Trajectory Intent",                                       "1+"],
    [35, "I021/016", "Service Management",                                      "1"],
    # ["FX", "n.a.",     "Field extension indicator",                               "n.a."],
    [36, "I021/008", "Aircraft Operational Status",                             "1"],
    [37, "I021/271", "Surface Capabilities and Characteristics",                "1+"],
    [38, "I021/132", "Message Amplitude",                                       "1"],
    [39, "I021/250", "Mode S MB Data",                                          "1+N*8"],
    [40, "I021/260", "ACAS Resolution Advisory Report",                         "7"],
    [41, "I021/400", "Receiver ID",                                             "1"],
    [42, "I021/295", "Data Ages",                                               "1+"],
    # ["FX", "n.a.",     "Field extension indicator",                               "n.a."],
    # ["43", "-",        "Not Used",                                                "-"],
    # ["44", "-",        "Not Used",                                                "-"],
    # ["45", "-",        "Not Used",                                                "-"],
    # ["46", "-",        "Not Used",                                                "-"],
    # ["47", "-",        "Not Used",                                                "-"],
    [48, "RE",       "Reserved Expansion Field",                                "1+"],
    [49, "SP",       "Special Purpose Field",                                   "1+"],
    # ["FX", "n.a.",     "Field extension indicator",                               "n.a."],
]

uap021_df = pd.DataFrame(data_021, columns=columns_021)
uap021_df.insert(0, "cat", 21)


# =========================
# DataFrame 2: CAT048
# =========================

columns_048 = ["frn", "item_id", "item_name", "length_str"]

data_048 = [
    [1,  "I048/010",     "Data Source Identifier",                                      "2"],
    [2,  "I048/140",     "Time-of-Day",                                                 "3"],
    [3,  "I048/020",     "Target Report Descriptor",                                    "1+"],
    [4,  "I048/040",     "Measured Position in Slant Polar Coordinates",                "4"],
    [5,  "I048/070",     "Mode-3/A Code in Octal Representation",                       "2"],
    [6,  "I048/090",     "Flight Level in Binary Representation",                       "2"],
    [7,  "I048/130",     "Radar Plot Characteristics",                                  "1+1+"],
    # ["FX", "n.a.",         "Field Extension Indicator",                                   "n.a."],
    [8,  "I048/220",     "Aircraft Address",                                            "3"],
    [9,  "I048/240",     "Aircraft Identification",                                     "6"],
    [10, "I048/250",     "Mode S MB Data",                                              "1+8*n"],
    [11, "I048/161",     "Track Number",                                                "2"],
    [12, "I048/042",     "Calculated Position in Cartesian Coordinates",                "4"],
    [13, "I048/200",     "Calculated Track Velocity in Polar Representation",           "4"],
    [14, "I048/170",     "Track Status",                                                "1+"],
    # ["FX", "n.a.",         "Field Extension Indicator",                                   "n.a."],
    [15, "I048/210",     "Track Quality",                                               "4"],
    [16, "I048/030",     "Warning/Error Conditions/Target Classification",              "1+"],
    [17, "I048/080",     "Mode-3/A Code Confidence Indicator",                          "2"],
    [18, "I048/100",     "Mode-C Code and Confidence Indicator",                        "4"],
    [19, "I048/110",     "Height Measured by 3D Radar",                                 "2"],
    [20, "I048/120",     "Radial Doppler Speed",                                        "1+"],
    [21, "I048/230",     "Communications / ACAS Capability and Flight Status",          "2"],
    # ["FX", "n.a.",         "Field Extension Indicator",                                   "n.a."],
    [22, "I048/260",     "ACAS Resolution Advisory Report",                             "7"],
    [23, "I048/055",     "Mode-1 Code in Octal Representation",                         "1"],
    [24, "I048/050",     "Mode-2 Code in Octal Representation",                         "2"],
    [25, "I048/065",     "Mode-1 Code Confidence Indicator",                            "1"],
    [26, "I048/060",     "Mode-2 Code Confidence Indicator",                            "2"],
    [27, "SP-Data Item", "Special Purpose Field",                                       "1+1+"],
    [28, "RE-Data Item", "Reserved Expansion Field",                                    "1+1+"],
    # ["FX", "n.a.",         "Field Extension Indicator",                                   "n.a."],
]

uap048_df = pd.DataFrame(data_048, columns=columns_048)
uap048_df.insert(0, "cat", 48)