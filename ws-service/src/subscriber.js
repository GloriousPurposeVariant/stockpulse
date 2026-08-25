import Redis from "ioredis";

import { config } from "./config.js";
import { ORDERS_CHANNEL, STOCK_CHANNEL } from "./events.js";



export const startSubscriber = (app, onEvent) => {

    const sub = new Redis(config.redisUrl);

    sub.on("error", (err) => {
        app.log.error({ err }, "redis subscriber error");
    });

    sub.subscribe(ORDERS_CHANNEL, STOCK_CHANNEL, (err, count) => {
        if (err) {
            app.log.error({ err }, "failed to subscribe");
            return;
        }
        app.log.info({ count }, "subscribed to redis channels");
    });

    sub.on("message", (channel, raw) => {
        let event;
        try {
            event = JSON.parse(raw);
        } catch (err) {
            app.log.warn({ err, channel, raw }, "dropping unparseable message");
            return;
        }
        onEvent(channel, event);
    });

    return sub;
};