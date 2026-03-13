\* Logistics_Optimization *\
Minimize
Minimize_Time: 0.3 x_('A',_'B') + 0.5 x_('A',_'C') + 0.4 x_('B',_'C')
Subject To
flow_end_C: x_('A',_'C') + x_('B',_'C') = 1
flow_int_B: x_('A',_'B') - x_('B',_'C') = 0
flow_start_A: x_('A',_'B') + x_('A',_'C') = 1
Binaries
x_('A',_'B')
x_('A',_'C')
x_('B',_'C')
End
