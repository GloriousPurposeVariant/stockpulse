import Fastify from 'fastify';
import { config } from './config.js';
import { startSubscriber } from './subscriber.js';
import websocketPlugin from '@fastify/websocket';
import jwt from 'jsonwebtoken';
import { register, unregister, deliver } from './connections.js';


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

        socket.on("close", () => {
            unregister(userId, socket);
            app.log.info({ userId }, "websocket disconnected");
        });
    });

    await app.listen({ port: config.port, host: "0.0.0.0" });
} catch (err) {
    app.log.error(err);
    process.exit(1);
}