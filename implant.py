import netifaces
from netaddr import *
import socket
import struct
import threading
import json

interfaces = netifaces.interfaces()
master_list = {}
num = netifaces.AF_INET

def networked_ips(ip, netmask):
    network = None
    try:
        network = IPNetwork(ip)
    except:
        print('[ERROR] (networked_ips) Invalid IP Address: %s' % ip)
        return

    try:
        subnet = IPAddress(netmask)
        network.prefixlen = subnet.netmask_bits()
    except:
        print('[ERROR] (networked_ips) Invalid IP Netmask: %s' % ip)
        return
    return network
    print(network)


def print_buffer(data_str):
    printed_chars = 0
    line_chars = 0

    line = None
    for c in data_str:
        if line_chars == 0:
            line = u'   \u001b[2m%5d:\u001b[0m  ' % printed_chars
        elif line_chars % 4 == 0:
            line += '  '

        hex_byte = c.encode('hex')
        if hex_byte == '00':
            line += u'\u001b[32m' + hex_byte + u'\u001b[0m '
        elif hex_byte == 'ff':
            line += u'\u001b[31m' + hex_byte + u'\u001b[0m '
        else:
            line += hex_byte + ' '

        printed_chars += 1
        line_chars += 1

        if line_chars == 16:
            print(line)
            line_chars = 0
            line = None

    if line is not None:
        print(line)


checker = True


def threading_send(s1):
    addrs = netifaces.ifaddresses(x)
    local_mac = netifaces.ifaddresses(x)[netifaces.AF_LINK][0]['addr']
    local_mac = local_mac.replace(':', '')
    local_mac = local_mac.decode('hex')

    if 2 in addrs:
        target = addrs[2][0]
        # shoutout my TAs
        # network = networked_ips(target['addr'], target['netmask'])
        for ip in networked_ips(target['addr'], target['netmask']):
            """
            FORMAT IPS INTO ARP PACKET TAILORING HERE
            KEEP IN MIND, IP IS AN OBJECT
            """
            #
            target_mac = '\xff\xff\xff\xff\xff\xff'
            # spoof mac has to be attacker's MAC
            spoof_mac = local_mac
            # ethernet header
            ethernet_header = target_mac  # Destination MAC
            ethernet_header += spoof_mac  # Source MAC
            ethernet_header += '\x08\x06'  # ARP Type: 0x0806

            # build arp packet
            arp_data = '\x00\x01'  # Ethernet type
            arp_data += '\x08\x00'  # IP Protocol
            arp_data += '\x06'  # Addr length
            arp_data += '\x04'  # Protocol Addr length
            arp_data += '\x00\x01'  # operation input, specifies reply is 2,request is 1
            arp_data += spoof_mac  # MAC address of attacker
            arp_data += socket.inet_aton(
                netifaces.ifaddresses(x)[netifaces.AF_INET][0]['addr'])  # sender (attacker) IP address
            arp_data += target_mac  # MAC address of target
            arp_data += str(socket.inet_aton(str(ip)))  # target IP address

            frame = ethernet_header + arp_data

            try:
                s1.sendall(frame)
            except:
                continue
        print('checked')
        global checker
        checker = False


def convert_mac_ntoa(data):
    g = ':'.join(c.encode('hex') for c in data)
    return g


def threading_listen(s1, x):
    addrs = netifaces.ifaddresses(x)
    local_mac = netifaces.ifaddresses(x)[netifaces.AF_LINK][0]['addr']
    local_mac = local_mac.replace(':', '')
    local_mac = local_mac.decode('hex')
    print('thread running')
    s1.settimeout(2)
    while checker == True:
        try:
            data, addr = s1.recvfrom(1024)
        except:
            print('timeout')
            continue
        # look at diagram in slides
        unpacked_data = struct.unpack('!6s6s2s2s2s1s1s2s6s4s6s4s', data[:42])
        if unpacked_data[2] != '\x08\x06':
            continue
        if unpacked_data[7] != '\x00\x02':
            continue
        ipval = socket.inet_ntoa(unpacked_data[9])
        macval = convert_mac_ntoa(unpacked_data[8])
        print_buffer(unpacked_data[8])
        print_buffer(unpacked_data[9])
        master_list['machines'][x][ipval] = {}
        master_list['machines'][x][ipval]['mac'] = macval
        print(master_list)
        string_check = True


master_list['machines'] = {}

# shoutout x for not dying
for x in interfaces:
    try:
        master_list['machines'][x] = {}
        s1 = socket.socket(socket.PF_PACKET, socket.SOCK_RAW, socket.htons(3))
        s1.bind((x, 0))
        if x == 'eth0' or x == 'eth1':
            continue

        t1 = threading.Thread(target=threading_send, args=(s1,))
        t2 = threading.Thread(target=threading_listen, args=(s1, x))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        for b in master_list['machines']:
            for z in master_list['machines'][b]:
                master_list['machines'][x][z] = {}
                ip_scan = z
                print(ip_scan)
                for port in range(1, 65536):
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(1)
                    try:
                        con = s.connect((ip_scan, port))
                        s.send('hello\n')
                        protocol = 'other'
                        proto = s.recv(1024).lower()
                        if 'ssh' in proto:
                            protocol = 'ssh'
                        if proto == 'hello\n':
                            protocol = 'echo'
                        if '\xff\xfd\x25' in proto:
                            protocol = 'telnet'
                        if 'http' in proto:
                            protocol = 'http'
                        if 'ftp' in proto:
                            protocol = 'ftp'
                        if 'smtp' in proto:
                            protocol = 'smtp'
                        master_list['machines'][x][z][port] = protocol
                        print(port, ': open')
                    except:
                        continue

                    s.close()

with open('output.json', 'w') as fp:
    json.dump(master_list, fp)

# json.dump to file, zip into folder, turn in