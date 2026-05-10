# Template: initialize_floorplan — Mode B (utilization + aspect_ratio + core_space)
# Variables substituted by IFPTclGenerator:
#   @DESIGN@  @LEF@  @DEF_IN@  @UTIL@  @ASPECT@  @CORE_SPACE@  @SITE@  @DEF_OUT@

read_lef  @LEF@
read_def  @DEF_IN@

initialize_floorplan \
    -utilization  @UTIL@ \
    -aspect_ratio @ASPECT@ \
    -core_space   { @CORE_SPACE@ } \
    -site         @SITE@

write_def @DEF_OUT@
exit
