
# Meshtastic logger

This script allows to capture and log into sqlite database all packets
received from meshtastic network. Basically, it maintains following
tables in the database:

```
sqlite> .schema
CREATE TABLE nodes (id INTEGER, name TEXT);
CREATE TABLE log (time INTEGER, src INTEGER, snr REAL, hops INTEGER);
CREATE TABLE geo (node INTEGER, lat INTEGER, lng INTEGER, time INTEGER);
CREATE TABLE msg (time INTEGER, src INTEGER, text TEXT);
```

  1. first table contains node callsigns;
  2. second table stores each packet seen in the air;
  3. third table stores location history for nodes broadcasting their location;
  4. fourth table stores all text messages sent by each node.

Also, as additional feature, this script replies to "QSA" request (in a text
message) with parameters of received message: SNR and TTL (time to live).

This script may be combined with web-frontend to display meshtastic nodes
on the map...

## Connection to meshtastic device

Meshtastic device must be connected via serial port (via USB).


## Links

1. https://meshtastic.org/

