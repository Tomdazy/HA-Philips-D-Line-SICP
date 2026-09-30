"""Faux moniteur SICP pour les tests : répond comme décrit dans SICP 2.09."""
import asyncio

# get_cmd -> payload ; set_cmd -> get_cmd
STATE = {
    0x19: bytes([0x02]),
    0x45: bytes([30, 20]),
    0x46: bytes([0x00]),
    0xAD: bytes([0x0D, 0x00, 0x01, 0x00]),
    0x33: bytes([55, 50, 45, 5, 50, 50, 3]),
    0x3B: bytes([0x03]),
    0x71: bytes([0x00]),
    0x76: bytes([0x00]),
    0x2F: bytes([31, 29]),
    0x9E: bytes([0x00, 24, 60]),
    0x59: bytes([0x01]),
    0xAB: bytes([4, 0x0D, 0x06, 0x0A, 0x16]),
}
TEXT = {
    (0xA1, 0): b"43BDL4550D/00", (0xA1, 1): b"FB12.34", (0xA1, 3): b"FB02.11",
    (0xA2, 0): b"2.09", (0xA2, 2): b"BDL4550D 3.0", (0x15, None): b"HA1A0917123456",
    (0x0F, 2): bytes([0x09, 0x8D]),
}
SET_TO_GET = {0x18: 0x19, 0x44: 0x45, 0x47: 0x46, 0xAC: 0xAD, 0x32: 0x33,
              0x3A: 0x3B, 0x72: 0x71, 0x77: 0x76, 0x9F: 0x9E}
LOG: list[bytes] = []
# Comportements du 55BDL4511D observés en réel :
# SLEEP : service SICP muet en veille (TCP accepté, aucune réponse)
# PREFIX : octets livrés avant la prochaine réponse (reste de trame, réponses en retard)
SLEEP = False
PREFIX = b""
WRITERS: set = set()


def frame(data: bytes) -> bytes:
    body = bytes([len(data) + 4, 0x01, 0x01]) + data
    chk = 0
    for b in body:
        chk ^= b
    return body + bytes([chk])


def status(code: int) -> bytes:
    return frame(bytes([0x00, code]))


def handle(pkt: bytes) -> bytes:
    LOG.append(pkt)
    cmd, data = pkt[3], pkt[4:-1]
    if (cmd, data[0] if data else None) in TEXT:
        return frame(bytes([cmd]) + TEXT[(cmd, data[0] if data else None)])
    if cmd in STATE:
        if STATE[0x19] == b"\x01" and cmd not in (0x19,):
            return status(0x18)
        return frame(bytes([cmd]) + STATE[cmd])
    if cmd in SET_TO_GET:
        g = SET_TO_GET[cmd]
        if STATE[0x19] == b"\x01" and cmd != 0x18:
            return status(0x18)
        cur = bytearray(STATE[g])
        if cmd == 0x44:
            for i, v in enumerate(data[:2]):
                if v != 0xFF:
                    cur[i] = v
        elif cmd == 0x32:
            for i, v in enumerate(data[:7]):
                if v != 0xFF:
                    cur[i] = v
        else:
            cur[: len(data)] = data
            cur = cur[: max(len(data), len(STATE[g]))]
        STATE[g] = bytes(cur)
        return status(0x06)
    return status(0x15)  # commande inconnue -> NACK


async def client(reader, writer):
    WRITERS.add(writer)
    try:
        while True:
            n = (await reader.readexactly(1))[0]
            pkt = bytes([n]) + await reader.readexactly(n - 1)
            if SLEEP:
                LOG.append(pkt)
                continue
            global PREFIX
            writer.write(PREFIX + handle(pkt))
            PREFIX = b""
            await writer.drain()
    except asyncio.IncompleteReadError:
        pass
    finally:
        WRITERS.discard(writer)
        writer.close()


async def start(port=0):
    server = await asyncio.start_server(client, "127.0.0.1", port)
    return server, server.sockets[0].getsockname()[1]


async def stop(server):
    global SLEEP, PREFIX
    SLEEP, PREFIX = False, b""
    server.close()
    for writer in list(WRITERS):
        writer.close()
    await server.wait_closed()
