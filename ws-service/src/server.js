import Fastify from 'fastify';
import { config } from './config.js';
import { startSubscriber } from './subscriber.js';
import websocketPlugin from '@fastify/websocket';
import jwt from 'jsonwebtoken';
import { register, unregister, deliver, startHeartbeat } from './connections.js';


const app = Fastify({ logger: true });
await app.register(websocketPlugin);

const authenticate = (token) => {
    const payload = jwt.verify(token, config.jwtSigningKey, {
        algorithms: ['HS256'],
    })
    if (payload.token_type !== 'access') {
        throw new Error('not an access token');
    }
    return payload;
};

app.get('/health', async () => {
    return { status: 'ok' };
})

try {
    startSubscriber(app, (channel, event) => {
        deliver(channel, event);
        app.log.info({ channel, type: event.type, data: event.data }, "event received");
    });

    app.get("/ws", { websocket: true }, (socket, req) => {
        let payload;
        try {
            payload = authenticate(req.query.token);
        } catch (err) {
            app.log.warn({ err: err.message }, "rejecting websocket connection");
            socket.close(4401, "unauthorized");
            return;
        }

        const userId = Number(payload.user_id);
        register(userId, socket);
        app.log.info({ userId }, "websocket connected");

        // Browsers answer ping frames in their networking stack, before any
        // JavaScript runs, so the client needs no code for this. The heartbeat
        // reads the flag; the pong resets it.
        socket.isAlive = true;
        socket.on("pong", () => {
            socket.isAlive = true;
        });


        socket.on("close", () => {
            unregister(userId, socket);
            app.log.info({ userId }, "websocket disconnected");
        });
    });

    // Nginx closes an upstream connection that has been silent for too long,
    // and an idle websocket is silent by definition. A ping every thirty
    // seconds keeps it open and reveals peers that have gone away.
    const heartbeat = startHeartbeat(app);

    // Compose sends SIGTERM and gives us ten seconds before SIGKILL. Fastify's
    // close() runs the shutdown hooks and closes open sockets properly, so
    // clients see a clean close frame instead of a severed connection.
    for (const signal of ["SIGTERM", "SIGINT"]) {
        process.on(signal, async () => {
            app.log.info({ signal }, "shutting down");
            // An uncleared interval keeps the event loop alive and the process
            // never exits - which would turn this into a wait for SIGKILL.
            clearInterval(heartbeat);
            await app.close();
            process.exit(0);
        });
    }

    await app.listen({ port: config.port, host: "0.0.0.0" });
} catch (err) {
    app.log.error(err);
    process.exit(1);
}