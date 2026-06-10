# 2026-06-02 14:37:42 by RouterOS 7.19.6
# software id = M8T2-3189
#
# model = C53UiG+5HPaxD2HPaxD
# serial number = HM50B420CZY
/ip firewall filter
add action=accept chain=input comment="Allow established/related to router" connection-state=established,related
add action=drop chain=input comment="Drop invalid to router" connection-state=invalid
add action=accept chain=forward comment="Allow established/related forward" connection-state=established,related
add action=drop chain=forward comment="Drop invalid forward" connection-state=invalid
add action=accept chain=input comment="Allow ICMP from mgmt" in-interface=vlan10-mgmt protocol=icmp
add action=accept chain=input comment="Allow SSH from mgmt" dst-port=22 in-interface=vlan10-mgmt protocol=tcp
add action=accept chain=input comment="Allow Winbox from mgmt" dst-port=8291 in-interface=vlan10-mgmt protocol=tcp
add action=accept chain=input comment="Allow HTTPS from mgmt" dst-port=443 in-interface=vlan10-mgmt protocol=tcp
add action=accept chain=input comment="Allow DNS from mgmt" dst-port=53 in-interface=vlan10-mgmt protocol=udp
add action=accept chain=input comment="Allow DNS from controller" dst-port=53 in-interface=vlan20-ctrl protocol=udp
add action=accept chain=input comment="Allow DNS from nodes" dst-port=53 in-interface=vlan30-nodes protocol=udp
add action=accept chain=input comment="Allow DNS TCP from mgmt" dst-port=53 in-interface=vlan10-mgmt protocol=tcp
add action=accept chain=input comment="Allow DNS TCP from controller" dst-port=53 in-interface=vlan20-ctrl protocol=tcp
add action=accept chain=input comment="Allow DNS TCP from nodes" dst-port=53 in-interface=vlan30-nodes protocol=tcp
add action=accept chain=input comment="Allow NTP from mgmt" dst-port=123 in-interface=vlan10-mgmt protocol=udp
add action=accept chain=input comment="Allow NTP from controller" dst-port=123 in-interface=vlan20-ctrl protocol=udp
add action=accept chain=input comment="Allow NTP from nodes" dst-port=123 in-interface=vlan30-nodes protocol=udp
add action=drop chain=input comment="Drop everything from WAN to router" in-interface=ether1
add action=accept chain=input comment="Allow ICMP from controller" in-interface=vlan20-ctrl protocol=icmp
add action=accept chain=input comment="Allow ICMP from nodes" in-interface=vlan30-nodes protocol=icmp
add action=drop chain=input comment="Drop all other input - default deny"
add action=accept chain=forward comment="Allow mgmt to internet" in-interface=vlan10-mgmt out-interface=ether1
add action=accept chain=forward comment="Allow controller to internet (dev mode)" in-interface=vlan20-ctrl out-interface=ether1
add action=accept chain=forward comment="PROVISIONING: VLAN 30 to WAN - REMOVE BEFORE DEPLOYMENT" in-interface=vlan30-nodes out-interface=ether1
add action=drop chain=forward comment="DROP nodes to internet (Zero Trust)" in-interface=vlan30-nodes log=yes log-prefix=DROP-NODES-WAN out-interface=ether1
add action=accept chain=forward comment="Allow SSH mgmt to controller" dst-port=22 in-interface=vlan10-mgmt out-interface=vlan20-ctrl protocol=tcp
add action=accept chain=forward comment="Allow HTTPS mgmt to controller" dst-port=443 in-interface=vlan10-mgmt out-interface=vlan20-ctrl protocol=tcp
add action=accept chain=forward comment="Allow ICMP mgmt to controller" in-interface=vlan10-mgmt out-interface=vlan20-ctrl protocol=icmp
add action=accept chain=forward comment="Allow mTLS controller to nodes" dst-port=443 in-interface=vlan20-ctrl out-interface=vlan30-nodes protocol=tcp
add action=accept chain=forward comment="Allow ICMP controller to nodes" in-interface=vlan20-ctrl out-interface=vlan30-nodes protocol=icmp
add action=accept chain=forward comment="Allow mTLS nodes to controller" dst-port=443 in-interface=vlan30-nodes out-interface=vlan20-ctrl protocol=tcp
add action=accept chain=forward comment="Allow enrollment nodes to step-ca" dst-port=9000 in-interface=vlan30-nodes out-interface=vlan20-ctrl protocol=tcp
add action=accept chain=forward comment="Allow SSH controller to nodes" dst-port=22 in-interface=vlan20-ctrl out-interface=vlan30-nodes protocol=tcp
add action=accept chain=forward comment="Allow metrics scraping controller to nodes (8C)" dst-port=9100 in-interface=vlan20-ctrl out-interface=vlan30-nodes protocol=tcp
add action=drop chain=forward comment="Drop all other forward - default deny" log=yes log-prefix=DROP-FORWARD
