
/**
 * Demo-mode sample data — used when no file has been uploaded yet.
 *
 * Mirrors the sample_logicmonitor_export.csv so the dashboard has
 * something meaningful to render on first load.
 */

export const SAMPLE_CSV = `device_name,interface_name,interface_description,in_utilization_percent,out_utilization_percent,in_errors_1h,out_errors_1h,in_discards_1h,out_discards_1h
core-rtr-01,GigabitEthernet0/1,Uplink to ISP-A,78.4,82.1,0,0,12,8
core-rtr-01,GigabitEthernet0/2,Uplink to ISP-B,12.3,15.7,245,3,0,0
core-rtr-01,GigabitEthernet0/3,Backup link to DC2,5.2,4.8,0,0,0,0
core-rtr-02,GigabitEthernet0/1,Primary uplink,65.7,68.2,0,0,5,3
core-rtr-02,GigabitEthernet0/2,Secondary uplink,22.4,18.9,0,0,0,0
dist-sw-01,TenGigE0/0/1,To core-rtr-01,45.2,47.8,0,0,0,0
dist-sw-01,TenGigE0/0/2,To core-rtr-02,38.9,41.2,0,0,2,1
dist-sw-01,GigabitEthernet1/1,To access-sw-01,15.6,12.3,0,0,0,0
dist-sw-02,TenGigE0/0/1,To core-rtr-01,52.1,49.7,0,0,0,0
dist-sw-02,TenGigE0/0/2,To dist-sw-01,91.7,88.3,0,0,340,287
dist-sw-02,TenGigE0/0/3,To dist-sw-03,72.4,69.8,0,0,18,12
dist-sw-03,TenGigE0/0/1,To dist-sw-02,68.4,71.2,12,8,15,11
dist-sw-03,TenGigE0/0/2,To dist-sw-04,34.5,36.7,0,0,0,0
dist-sw-04,TenGigE0/0/1,To dist-sw-03,41.2,38.9,0,0,0,0
dist-sw-04,GigabitEthernet1/1,Server farm uplink,82.4,28.7,0,0,0,0
access-sw-01,GigabitEthernet1/1,User VLAN 100,8.4,6.2,0,0,0,0
access-sw-01,GigabitEthernet1/2,User VLAN 200,12.7,10.3,0,0,0,0
access-sw-01,GigabitEthernet1/3,VoIP VLAN 300,18.4,16.7,0,0,0,0
access-sw-02,GigabitEthernet1/1,Floor 2 users,22.3,19.8,0,0,0,0
access-sw-02,GigabitEthernet1/2,Floor 2 printers,3.4,2.1,0,0,0,0
access-sw-03,GigabitEthernet1/1,Floor 3 users,15.8,13.4,8,5,3,2
access-sw-04,GigabitEthernet1/24,Conference room,45.6,42.3,0,0,0,0
access-sw-05,GigabitEthernet1/1,Lab network,2.1,1.8,0,0,0,0
access-sw-06,GigabitEthernet1/12,Wireless AP-101,38.7,55.4,0,0,0,0
edge-fw-01,Ethernet1,WAN Interface,94.2,91.8,0,0,856,742
edge-fw-01,Ethernet2,DMZ Interface,32.1,28.4,0,0,0,0
edge-fw-01,Ethernet3,Internal Interface,67.3,64.8,0,0,8,5
dc-sw-01,TenGigE0/0/1,To storage cluster,75.6,78.9,0,0,45,38
dc-sw-01,TenGigE0/0/2,To compute cluster,82.4,85.7,0,0,72,58
dc-sw-02,TenGigE0/0/1,To dc-sw-01 trunk,88.9,90.2,0,0,125,98
`

export function sampleFile() {
  return new File([SAMPLE_CSV], 'sample_logicmonitor_export.csv', {
    type: 'text/csv',
  })
}
