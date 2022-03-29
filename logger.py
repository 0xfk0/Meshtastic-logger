#!/usr/bin/python3
import sqlite3
import meshtastic
import time
import math
import os
from datetime import datetime
from pubsub import pub
from serial_interface import SerialInterface
from meshtastic import portnums_pb2

def debug(str):
    if 'DEBUG' in os.environ and os.environ['DEBUG']:
        print(str)

db = None
MaxDist = 150  # meters
MaxDTime = 100 # seconds

# coordinates must be in degrees
def geo_dist(lat1, lng1, lat2, lng2):
    
    cos1 = math.cos(lat1)
    cos2 = math.cos(lat2)
    sin1 = math.sin(lat1)
    sin2 = math.sin(lat2)

    dlng = lng1 - lng2
    cos_dlng = math.cos(dlng)

    y1 = cos2 * math.sin(dlng)
    y2 = cos1*sin2 - sin1*cos2*cos_dlng

    y = math.sqrt(y1*y1 + y2*y2)
    x = sin1*sin2 + cos1*cos2*cos_dlng
   
    earth_radius = 6372795  # meters
    dist = math.atan2(y, x) * earth_radius

    debug(f'geo_dist {lat1}, {lng1}, {lat2}, {lng2}, {dist}')
    return dist


def process_packet(packet, interface):
    # databse must be used in only one thread
    global db
    if db is None:
        db = sqlite3.connect('mesh.db')
        db.execute("CREATE TABLE IF NOT EXISTS nodes (id INTEGER, name TEXT);")
        db.execute("CREATE TABLE IF NOT EXISTS log (time INTEGER, src INTEGER, snr REAL, hops INTEGER)")
        db.execute("CREATE TABLE IF NOT EXISTS geo (node INTEGER, lat INTEGER, lng INTEGER, time INTEGER)")
        db.execute("CREATE TABLE IF NOT EXISTS msg (time INTEGER, src INTEGER, text TEXT)")

    #debug(f'\n\nraw_packet: {packet}\n\n')
    if not 'rxSnr' in packet:
        packet['rxSnr'] = 0

    src = int(packet['from'])
    try:
        name = interface.nodes[packet['fromId']]['user']['longName']
        have_name = 1
    except: 
        name = src
        have_name = 0

    now = datetime.now()
    unixtime = int(time.mktime(now.timetuple()))
    snr = float(packet['rxSnr'])
    debug(f'packet: {src}, {name}, {have_name}, {snr}')

    # update node names in database
    if have_name:
            db.execute('''
                INSERT INTO nodes(id, name)
                SELECT ?, ?
                WHERE NOT EXISTS(SELECT * FROM nodes WHERE id = ? AND name = ?);
                ''', (src, name, src, name));

    # substitute default value for TTL
    if not 'hopLimit' in packet:
        packet['hopLimit'] = 0

    # update database
    hops = int(packet['hopLimit'])
    debug(f'log: {unixtime}, {src}, {snr}, {hops}')
    db.execute("INSERT INTO log VALUES(?, ?, ?, ?)", (unixtime, src, snr, hops))

    # get coordinates from a packet
    lat = None
    lng = None
    if 'decoded' in packet:
        if 'position' in packet['decoded']:
            pos = packet['decoded']['position']
            try:
                lat = pos['latitudeI']
                lng = pos['longitudeI']
            except:
                lat = None
                lng = None

    # update coordinates in database
    debug(f'geo: {lat}, {lng}')
    if lat is not None:
        need_update = True
        res = db.execute("SELECT time, lat, lng FROM geo WHERE node = ? ORDER BY time DESC LIMIT 1", [src])
        for ptime, plat, plng in res:
            debug(f'select {plat}, {plng}')
            dist = geo_dist(lat/1e7, lng/1e7, plat/1e7, plng/1e7)
            dtime = abs(unixtime - ptime)
            global MaxDist
            global MaxDTime
            if dist < MaxDist or dtime < MaxDTime:
                need_update = False

        if need_update:
            debug(f'update_geo: {src}, {lat}, {lng}, {unixtime}')
            db.execute("INSERT INTO geo VALUES(?, ?, ?, ?)", (src, int(lat), int(lng), unixtime))
                        
    # print to the console
    shops = str(hops) + " hops" if hops is not None else ''
    strtime = now.strftime('%Y-%m-%dT%H:%M:%S')
    print("%-16s  %s     % 5.1f dB    %s" % (name, strtime, snr, shops))

    # process messages
    if 'decoded' in packet:
        decoded = packet['decoded']
        if 'portnum' in decoded and 'payload' in decoded and decoded['portnum'] == 'TEXT_MESSAGE_APP':
            # log message
            text = decoded['payload']
            string = text.decode('utf-8')
            print("    %s\n-- " % string)
            db.execute("INSERT INTO msg VALUES(?, ?, ?)", (unixtime, src, text))
            # process automatic replies
            if string == "QSA":
                interface.sendText("SNR %.1f, TTL %u." % (snr, hops))

    db.commit()


def onReceive(packet, interface):
    try:
        process_packet(packet, interface)
    except:
        interface.close()
        exit(1)

interface = SerialInterface()
pub.subscribe(onReceive, "meshtastic.receive")
while True:
        time.sleep(1)

# vim: set sts=4 sw=4 et:
