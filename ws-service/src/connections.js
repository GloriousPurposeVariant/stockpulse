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
    if(!sockets) return;
    sockets.delete(socket);
    if (sockets.size === 0) {
        connections.delete(userId);
    }
}

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