import { STOCK_CHANNEL } from "./events.js";

const connections = new Map();

export const register = (userId, socket) => {
    if (!connections.has(userId)) {
        connections.set(userId, new Set());
    }
    connections.get(userId).add(socket);
}

export const unregister = (userId, socket) => {
    const sockets = connections.get(userId);
    if (!sockets) return;
    sockets.delete(socket);
    if (sockets.size === 0) {
        connections.delete(userId);
    }
}

// A generator rather than an array: this is walked once per heartbeat and
// never stored.
export function* allSockets() {
    for (const sockets of connections.values()) {
        yield* sockets;
    }
}


const HEARTBEAT_MS = 30_000;

// One pass of the liveness check, separate from the timer that drives it so
// that a test can step it rather than wait thirty seconds.
export const heartbeatTick = (app) => {
    for (const socket of allSockets()) {
        // Nothing answered the previous ping, so the peer is gone even though
        // the socket still looks open. terminate(), not close(): there is
        // nobody left to complete a closing handshake with.
        if (socket.isAlive === false) {
            app.log.info("terminating an unresponsive socket");
            socket.terminate();
            continue;
        }
        socket.isAlive = false;
        socket.ping();
    }
}

export const startHeartbeat = (app) => setInterval(() => heartbeatTick(app), HEARTBEAT_MS);



const send = (socket, message) => {
    if (socket.readyState === 1) {
        socket.send(message);
    }
}

export const deliver = (channel, event) => {
    const message = JSON.stringify(event);

    if (channel === STOCK_CHANNEL) {
        for (const sockets of connections.values()) {
            for (const socket of sockets) send(socket, message);
        }
        return;
    }

    const sockets = connections.get(event.data.customer_id);
    if (!sockets) return;
    for (const socket of sockets) send(socket, message);
}

// Test seam. The server never calls this - module state outlives a single test
// case, and a socket left behind would be delivered to by the next one.
export const clear = () => connections.clear();
