\* Logistics_Optimization *\
Minimize
Minimize_Time: 10.5 x_('ATL',_'MIA') + 17 x_('ATL',_'NYC')
 + 3.5 x_('BOS',_'MIA') + 2.5 x_('NYC',_'ATL') + 5.5 x_('NYC',_'BOS')
 + 3 x_('NYC',_'MIA') + 2.5 x_('NYC',_'PHI') + 2 x_('PHI',_'ATL')
 + 6.5 x_('PHI',_'BOS')
Subject To
flow_end_MIA: x_('ATL',_'MIA') + x_('BOS',_'MIA') + x_('NYC',_'MIA') = 1
flow_int_ATL: - x_('ATL',_'MIA') - x_('ATL',_'NYC') + x_('NYC',_'ATL')
 + x_('PHI',_'ATL') = 0
flow_int_BOS: - x_('BOS',_'MIA') + x_('NYC',_'BOS') + x_('PHI',_'BOS') = 0
flow_int_PHI: x_('NYC',_'PHI') - x_('PHI',_'ATL') - x_('PHI',_'BOS') = 0
flow_start_NYC: - x_('ATL',_'NYC') + x_('NYC',_'ATL') + x_('NYC',_'BOS')
 + x_('NYC',_'MIA') + x_('NYC',_'PHI') = 1
Binaries
x_('ATL',_'MIA')
x_('ATL',_'NYC')
x_('BOS',_'MIA')
x_('NYC',_'ATL')
x_('NYC',_'BOS')
x_('NYC',_'MIA')
x_('NYC',_'PHI')
x_('PHI',_'ATL')
x_('PHI',_'BOS')
End
