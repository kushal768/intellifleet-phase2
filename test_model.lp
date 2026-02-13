\* Logistics_Optimization *\
Minimize
Minimize_Cost: 47.5 x_('NYC',_'Philadelphia') + 115 x_('NYC',_'Washington')
 + 70 x_('Philadelphia',_'Washington') + 320 x_('Washington',_'Atlanta')
Subject To
flow_end_Atlanta: x_('Washington',_'Atlanta') = 1
flow_int_Philadelphia: x_('NYC',_'Philadelphia')
 - x_('Philadelphia',_'Washington') = 0
flow_int_Washington: x_('NYC',_'Washington')
 + x_('Philadelphia',_'Washington') - x_('Washington',_'Atlanta') = 0
flow_start_NYC: x_('NYC',_'Philadelphia') + x_('NYC',_'Washington') = 1
Binaries
x_('NYC',_'Philadelphia')
x_('NYC',_'Washington')
x_('Philadelphia',_'Washington')
x_('Washington',_'Atlanta')
End
