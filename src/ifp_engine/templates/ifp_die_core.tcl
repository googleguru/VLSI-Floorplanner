# Template: initialize_floorplan — Mode A (explicit die/core area)
# Variables substituted by IFPTclGenerator:
#   @DESIGN@  @LEF@  @DEF_IN@  @DIE_AREA@  @CORE_AREA@  @SITE@  @DEF_OUT@

read_lef   @LEF@
read_def   @DEF_IN@

initialize_floorplan \
    -die_area  { @DIE_AREA@ } \
    -core_area { @CORE_AREA@ } \
    -site      @SITE@

write_def @DEF_OUT@
exit
