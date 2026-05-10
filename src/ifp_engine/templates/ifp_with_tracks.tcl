# Template: initialize_floorplan + make_tracks (ASAP7 / PDK-aware)
# Variables:  @LEF@  @DEF_IN@  @UTIL@  @ASPECT@  @CORE_SPACE@  @SITE@
#             @TRACK_CMDS@  @DEF_OUT@

read_lef  @LEF@
read_def  @DEF_IN@

initialize_floorplan \
    -utilization  @UTIL@ \
    -aspect_ratio @ASPECT@ \
    -core_space   { @CORE_SPACE@ } \
    -site         @SITE@

@TRACK_CMDS@

write_def @DEF_OUT@
exit
