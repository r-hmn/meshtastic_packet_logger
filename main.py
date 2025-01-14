import time
import meshtastic
import meshtastic.tcp_interface
from pubsub import pub
import sys
import pprint
from nodes_db import NodesDb
import datetime
import traceback 
import json

### GLOBALS
db = None
expectedAcks = {} # requestID's for toNum for which an Ack is requested
resource = {}
with open("text_resource.json", "r") as config_file:
    resource = json.load(config_file)

''' 
WHAT NODES' DICTIONARY-VALUE LOOKS LIKE:

    {'num': 4145982656,
    'user': {'id': '!aaa',
            'longName': 'aaa',
            'shortName': 'aaa',
            'macaddr': 'aaa',
            'hwModel': 'aaa'},
    'position': {'latitudeI': 123,
                'longitudeI': 123,
                'altitude': -17,
                'time': 123,
                'latitude': 123,
                'longitude': 123},
    'snr': 4.75,
    'lastHeard': 1722380238,
    'deviceMetrics': {'batteryLevel': 94,
                    'voltage': 4.096,
                    'channelUtilization': 1.385,
                    'airUtilTx': 0.28486112,
                    'uptimeSeconds': 8150},
    'lastReceived': {'from': aaa,
                    'to': bbb,
                    'decoded': {'portnum': 'TEXT_MESSAGE_APP',
                                'payload': b'F',
                                'text': 'F'},
                    'id': 123,
                    'rxTime': 123,
                    'rxSnr': 4.75,
                    'hopLimit': 3,
                    'wantAck': True,
                    'rxRssi': -77,
                    'hopStart': 3,
                    'raw': from: 123
    to: 123
    decoded {
    portnum: TEXT_MESSAGE_APP
    payload: "F"
    }
    id: 123
    rx_time: 123
    rx_snr: 4.75
    hop_limit: 3
    want_ack: true
    rx_rssi: -77
    hop_start: 3
    ,
                    'fromId': '!aaa',
                    'toId': '!bbb'},
    'hopLimit': 3}

########## sentText( ,wantAck = False)
    returns:
    [to: 123
    decoded {
    portnum: TEXT_MESSAGE_APP
    payload: "BeepBoop. Back at ya: Test"
    }
    id: 123
    hop_limit: 3
    ]
    ########## sentText( ,wantAck = True)
    returns:
    [to: 123
    decoded {
    portnum: TEXT_MESSAGE_APP
    payload: "BeepBoop. Back at ya: Test"
    }
    id: 123
    hop_limit: 3
    want_ack: true
    ]
    ##### START MESSAGE LAYOUT #####
        {'from': 123,
        'to': 123,
        'decoded': {'portnum': 'ROUTING_APP',
                    'payload': b'\x18\x00',
                    'requestId': 123,
                    'routing': {'errorReason': 'NONE', 'raw': error_reason: NONE
        }},
        'id': 123,
        'rxTime': 123,
        'rxSnr': 2.5,
        'hopLimit': 2,
        'rxRssi': -86,
        'hopStart': 2,
        'raw': from: 123
        to: 123
        decoded {
        portnum: ROUTING_APP
        payload: "\030\000"
        request_id: 123
        }
        id: 123
        rx_time: 123
        rx_snr: 2.5
        hop_limit: 2
        rx_rssi: -86
        hop_start: 2
        ,
        'fromId': '!aaa',
        'toId': '!bbb'}
########## 

Overview of all possible portnums
    https://github.com/meshtastic/protobufs/blob/master/meshtastic/portnums.proto

'''


def convertNumTofromId(fromDec):
    '''
    Converts the field 'from' to 'fromId'.
    the from-field is the decimal representation of fromId-field.
    e.g: 123
    is : !aaa
    '''
    return hex(fromDec).replace("0x","!")


def PrettyRelativeTime(time_diff_secs):
    # Each tuple in the sequence gives the name of a unit, and the number of
    # previous units which go into it.
    # source: https://stackoverflow.com/a/18421524
    weeks_per_month = 365.242 / 12 / 7
    intervals = [('minute', 60), ('hour', 60), ('day', 24), ('week', 7),
                 ('month', weeks_per_month), ('year', 12)]
    unit, number = 'second', abs(time_diff_secs)
    for new_unit, ratio in intervals:
        new_number = float(number) / ratio
        # If the new number is too small, don't go to the next unit.
        if new_number < 2:
            break
        unit, number = new_unit, new_number
    shown_num = int(number)
    return '{} {}'.format(shown_num, unit + ('' if shown_num == 1 else 's'))


def sendTextWithReceipt(interface, toNum, text):
    ''' 
    Sends text and wants an Ack
    '''
    toId = convertNumTofromId(toNum)
    retVal = interface.sendText(text, toId, wantResponse = False, wantAck = True)
    print("Sent:[\n" + text + "\n] ack.id=", retVal.id)
    expectedAcks[ retVal.id ] = toNum


def onReceive(packet, interface): # called when a packet arrives
    '''
    Any incoming message will have updated the nodes list.
    So process it, and detect new nodes.
    '''
    global db
    global expectedAcks
    global resource

    now = datetime.datetime.now()
    nowInt = int(time.time())    
    try:
        fromNum = packet['from']
        fromId = convertNumTofromId(fromNum)

        # How long ago, or new node?
        isNewNode = False
        howLongAgoSec = 0
        howLongAgoStr = ""
        dbNode = db.get_node(fromNum)
        if dbNode == None:
            isNewNode = True
        else:
            try:
                before = dbNode[db.COL_LASTUPDATED]
                if before:
                    howLongAgoSec = nowInt - before
                    howLongAgoStr = "last heard " + PrettyRelativeTime(howLongAgoSec) + " ago"
                else:
                    howLongAgoStr = "lastheard info was not available"
            
            except Exception as ke:
                print("\n========== LAST UPDATED ISSUE")
                traceback.print_exception(*sys.exc_info())
                print("---------- packet")
                pprint.pp(packet)
                if dbNode:
                    print("---------- DB record:")
                    pprint.pp(dbNode)
                print("==========\n")
            
        # Update lastUpdated
        db.update_lastUpdated(fromNum, nowInt)
            
        # Create or Update DB with node-info
        if fromNodeObj := interface.nodes.get(fromId, None): # New feature in Python 3.8 https://peps.python.org/pep-0572/
            db.update_nodeNames_by_object(fromNodeObj)
            # Read back
            dbNode = db.get_node(fromNum)
            # Note: If the node sees a new node, i'm told the firmware automatically requests its NODE_INFO. It could be that it doesn't hear
            #       My request. Hence the NODE_INFO info could be missing in the db

        # Exit if encrypted
        if "encrypted" in packet:
            db.update_encrypted(num, True)
            return
        packetDecoded = packet["decoded"]
        portNum = packetDecoded["portnum"]
       
        # Skip printing telemetry of my own station        
        if fromId == resource["MY_ID"] and portNum == 'TELEMETRY_APP':
            print(".", end='')
            return
            
        print()


        if dbNode and dbNode[db.COL_SHORTNAME]:
            # identification from DB
            identification = f"time:[{now}] id:[{fromId}] short:[{dbNode[db.COL_SHORTNAME]}] long:[{dbNode[db.COL_LONGNAME]}] messageType:[{portNum}]"
        else:
            # identification unknown
            print(f"! time:[{now}] Node info (still) unknown for '{fromId}'. Received messageType:[{portNum}]")            
            identification = f"time:[{now}] id:[{fromId}] short:----- long:----- messageType:[{portNum}]"


        if isNewNode:
            print(f"# NEW NODE {identification}")
            text = resource["message.newnode"]
            sendTextWithReceipt(interface, fromNum, text)
        else:
            print(f"# KNOWN NODE {identification } -- {howLongAgoStr}")
            if howLongAgoSec > 60*60*2:
                if howLongAgoSec < 60*60*24:
                    # between 2 and 24 hours
                    greeting_text = resource["message.morninggreeting"] if now.hour < 12 else resource["message.afternoongreeting"]
                    text = resource["message.helloagain<24h"]
                    text = text.format(greeting = greeting_text)
                else:
                    # longer                    
                    ago_hours = int(howLongAgoSec/60/60)
                    text = resource["message.helloagain>=24h"]
                    text = text.format(ago_hours = ago_hours)
                sendTextWithReceipt(interface, fromNum, text)


        if portNum == "POSITION_APP":
            position = packetDecoded['position']
            if 'longitudeI' in position:
                lon = position['longitudeI'] / 10000000.0
                lat = position['latitudeI']  / 10000000.0
                print(f"POSITION: [lat, lon] = [{lat}, {lon}]")  
                print(f"URL     : https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=12/{lat}/{lon}")
                db.update_position(fromNum, lat, lon)
            else:
                print(f"Error: 'longitudeI' not in packet")  
        
        
        if portNum == "TEXT_MESSAGE_APP":
            text = packetDecoded['text']
            print(f"TEXT:[\n{text}\n]\n*******")
            if "test" in text.lower() or "ping" in text.lower():
                reply_text = resource["message.pingmessage"]
                reply_text = reply_text.format(text = text)
                sendTextWithReceipt(interface, fromNum, reply_text)
        

        if portNum == "RANGE_TEST_APP":
            text = packetDecoded['text']
            print(f"RANGE_TEST:[\n{text}\n]\n*******")            
            reply_text = resource["message.rangetest"]
            reply_text = text.format(text = text)
            sendTextWithReceipt(interface, fromNum, reply_text)

        
        if portNum == "TELEMETRY_APP":
            telemetry = packetDecoded['telemetry']
            
            deviceMetrics = telemetry.get("deviceMetrics",{})
            batteryLevel = deviceMetrics.get("batteryLevel","?")
            voltage = deviceMetrics.get("voltage","?")
            uptimeSeconds = deviceMetrics.get("uptimeSeconds","?")
            
            environmentMetrics = telemetry.get("environmentMetrics",{})
            temperature = environmentMetrics.get("temperature","?")
            barometricPressure = deviceMetrics.get("barometricPressure","?")
            if batteryLevel == voltage == temperature == barometricPressure == uptimeSeconds == "?":
                print("##### START UNKNOWN TELEMETRY LAYOUT #####")
                pprint.pp(packet)        
                print("##### END UNKNOWN TELEMETRY LAYOUT #####")
            else:
                print(f"METRICS: batteryLevel:[{batteryLevel}] voltage:[{voltage}] temperature:[{temperature}] barometricPressure:[{barometricPressure}] uptimeSec[{uptimeSeconds}]")

       
        # Processing an Ack
        if portNum == "ROUTING_APP":
            requestId = packetDecoded.get('requestId')
            if requestId:
                if requestId in expectedAcks:
                    # For direct messages there are two types of Ack. One is coming from own-node, which means the message was forwarded by another node.
                    # Only if the Ack is coming from the target node directly you know the packet was received. you can check by testing 
                    # the 'from' of the Ack packet
                    
                    ackedNum = expectedAcks[requestId] #this is the target 'fromId'. But top level 'fromId' may not be the same as the target!
                    ackedId = convertNumTofromId(ackedNum)
                    ackIsDirect = (fromId == ackedId)
                    routing = packetDecoded['routing']
                    errorReason = routing['errorReason']
                    print(f"ACK for text to id:[{ackedId}] -- errorReason:[{errorReason}]  direct:[{ackIsDirect}]")
                    
                    # Only store better results than were recorded..
                    if errorReason != "NONE" and dbNode[db.COL_LASTACKTEXT] == "NONE":
                        print("Didn't save worse Ack info than was saved before")
                    else:
                        db.update_ack(ackedNum, nowInt, errorReason, ackIsDirect)
                        
                    #if errorReason:
                    #    print("======== ACK Packet")
                    #    pprint.pp(packet)
                    #    print("========\n")
                        
                    del expectedAcks[requestId]
                else:
                    print(f"ACK for unknown requestId:[{requestId}]")
            else:
                print("Error: No 'requestId' in packet")
        
        
        # Unexpected 
        known_packets = ("RANGE_TEST_APP", "TELEMETRY_APP", "TEXT_MESSAGE_APP", "NODEINFO_APP", "POSITION_APP", "ROUTING_APP")
        if portNum not in known_packets:
            print("##### START UNKNOWN MESSAGE LAYOUT #####")
            pprint.pp(packet)        
            print("##### END UNKNOWN MESSAGE LAYOUT #####")
        
        
    except Exception as ke:
        print("\n==========")
        traceback.print_exception(*sys.exc_info())
        print("---------- Unknown message format:")
        pprint.pp(packet)
        if dbNode:
            print("---------- DB record:")
            pprint.pp(dbNode)
        print("==========\n")


def onConnection(interface, topic=pub.AUTO_TOPIC): # called when we (re)connect to the radio
    # defaults to broadcast, specify a destination ID if you wish
    # interface.sendText("https://t.me/meshtastic_nl")
    print(f"Connected to the node")


def start():
    global db
    global resource

    db = NodesDb(r"./pythonsqlite.db")
    
    pub.subscribe(onReceive, "meshtastic.receive")
    pub.subscribe(onConnection, "meshtastic.connection.established")

    interface = meshtastic.tcp_interface.TCPInterface(hostname = resource["MY_HOSTNAME"], debugOut = sys.stdout)

    try:
        while True:
            time.sleep(1000)
    except KeyboardInterrupt:
        print("Program terminated by user")
        
    interface.close()
    db.close()


if __name__ == "__main__":
    start()
