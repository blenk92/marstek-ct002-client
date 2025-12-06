# Marstek CT002 Client
This tool emulates Marstek b2500 client on a ct002 marstek meter reader. It reads the power values (per line and combined) and publishs them to mqtt. It directly connects to the ct002 without any modification needed on the b2500 (well, I currenlty just tested with a ct002 that is already added to my marstek account. So not entirely sure if that is necessary...)

The motivation is to be able to use the marstek ct002 stand-alone and to deal with connection problems that are caused by bad connection and the udp based protocol.

Mqtt topics:
| Topic | Details |
| -------- | ------- |
| `marstek-power-meter/<power meter id>/A` | Value of A phase in Watt |
| `marstek-power-meter/<power meter id>/B` | Value of B phase in Watt |
| `marstek-power-meter/<power meter id>/C` | Value of C phase in Watt |
| `marstek-power-meter/<power meter id>/ALL` | Total value of all phases in Watt |


## Configuration
The following options are available as environment variable

| Option | Details |
| -------- | ------- |
| `MQTT_USER` | User for mqtt broker |
| `MQTT_PASS` | Password for mqtt broker |
| `MQTT_HOST` | Host/IP of mqtt broker |
| `MQTT_PORT` | Port that the mqtt broker listens on (default 1883) |
| `MQTT_CLIENT_ID` | Client id that shall be used for mqtt (default marstek-powermeter-reader)  |
| `MARSTEK_METER_ID` | ID (MAC) of the ct002 (obtained via marstek app)  |
| `MARSTEK_METER_IP` | IP of ct002 in your network |
| `MARSTEK_FAKE_CLIENT_ID` | The fake id that shall be used by the script to obtain data from ct002 (default: cafecafecafe)  |
| `CONNECTION_READ_TIMEOUT` | Read timeout on the connection. If read doesn't succeed in this time, it will be aborted and retried in the next iteration) |
| `MARSTEK_MSG_CHECKSUM` | Checksum of the message send to the ct002. See below for more details |
| `VERBOSE_PRINT` | Print read power values to stdout |


### Docker Compose

The application can be spwaned via docker-compose:
```
services:
  meter-reader:
    build:
      context: .
      dockerfile: Dockerfile
    restart: unless-stopped
    environment:
      - MQTT_USER=<mqtt user>
      - MQTT_PASS=<mqtt pass>
      - MQTT_HOST=<mqtt host>
      - MARSTEK_METER_ID=<ID of meter>
      - MARSTEK_METER_IP=<IP of meter>
      - ...
```

## Some techical details

### Message Checksum
The messages send to the ct002 seem to have some kind of checksum in the very last byte. I didn't want to spent too much time to figure out how exactly this is calculated. This is why i added a brute force mechanism to the script (which just checks values until it finds the correct one if `MARSTEK_MSG_CHECKSUM` is not given in the configuration). It only takes a few minutes to do so. If you have the correct value you can also just set it via `MARSTEK_MSG_CHECKSUM` to avoid the the brute forcing of the value on every start up

## Related work
There is some related repos which its worth looking into:
* https://github.com/tomquist/hm2mqtt
* https://github.com/tomquist/hame-relay
