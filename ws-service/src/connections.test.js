import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import {
    allSockets,
    clear,
    deliver,
    heartbeatTick,
    register,
    unregister
} from "./connections.js";
import { ORDERS_CHANNEL, ORDER_STATUS_CHANGED, STOCK_CHANGED, STOCK_CHANNEL } from "./events.js";

// A stand-in for a real WebSocket, recording what was done to it. readyState 1
// is OPEN; anything else means the socket is not writable.
const fakeSocket = (readyState = 1) => ({
    readyState,
    isAlive: true,
    sent: [],
    pings: 0,
    terminated: false,
    send(message) {
        this.sent.push(JSON.parse(message));
    },
    ping() {
        this.pings += 1;
    },
    terminate() {
        this.terminated = true;
    },
});

const fakeApp = { log: { info() {}, warn() {}, error() {} } };

const orderEvent = (customerId) => ({
    type: ORDER_STATUS_CHANGED,
    data: { reference: "ORD-TEST", status: "completed", customer_id: customerId },
});

const stockEvent = () => ({
    type: STOCK_CHANGED,
    data: { sku: "WIDGET-01", quantity: 96, delta: -4 },
});

// The registry is module state and outlives a single test case.
beforeEach(clear);

describe("register and unregister", () => {
    it("keeps every socket a user has open", () => {
        const laptop = fakeSocket();
        const phone = fakeSocket();
        register(7, laptop);
        register(7, phone);

        assert.deepEqual([...allSockets()], [laptop, phone]);
    });

    it("forgets a user once their last socket closes", () => {
        const laptop = fakeSocket();
        const phone = fakeSocket();
        register(7, laptop);
        register(7, phone);

        unregister(7, laptop);
        assert.deepEqual([...allSockets()], [phone]);

        unregister(7, phone);
        assert.deepEqual([...allSockets()], []);
    });

    it("ignores an unregister for a user that was never registered", () => {
        assert.doesNotThrow(() => unregister(999, fakeSocket()));
    });
});

describe("delivering order events", () => {
    it("reaches only the customer the event names", () => {
        const alice = fakeSocket();
        const bob = fakeSocket();
        register(7, alice);
        register(8, bob);

        deliver(ORDERS_CHANNEL, orderEvent(7));

        assert.equal(alice.sent.length, 1);
        assert.equal(alice.sent[0].data.reference, "ORD-TEST");
        assert.equal(bob.sent.length, 0);
    });

    it("reaches every socket that customer has open", () => {
        const laptop = fakeSocket();
        const phone = fakeSocket();
        register(7, laptop);
        register(7, phone);

        deliver(ORDERS_CHANNEL, orderEvent(7));

        assert.equal(laptop.sent.length, 1);
        assert.equal(phone.sent.length, 1);
    });

    it("drops an event for a customer with nobody connected", () => {
        const alice = fakeSocket();
        register(7, alice);

        assert.doesNotThrow(() => deliver(ORDERS_CHANNEL, orderEvent(404)));
        assert.equal(alice.sent.length, 0);
    });

    it("does not match a string customer id against a numeric key", () => {
        // SimpleJWT emits user_id as a string and the event carries an int, so
        // server.js coerces with Number(). This is what that guards against.
        const alice = fakeSocket();
        register(7, alice);

        deliver(ORDERS_CHANNEL, orderEvent("7"));

        assert.equal(alice.sent.length, 0);
    });
});

describe("delivering stock events", () => {
    it("broadcasts to everyone regardless of customer", () => {
        const alice = fakeSocket();
        const bob = fakeSocket();
        register(7, alice);
        register(8, bob);

        deliver(STOCK_CHANNEL, stockEvent());

        assert.equal(alice.sent.length, 1);
        assert.equal(bob.sent.length, 1);
        assert.equal(alice.sent[0].data.sku, "WIDGET-01");
    });

    it("skips a socket that is not open", () => {
        const closing = fakeSocket(2); // CLOSING
        register(7, closing);

        deliver(STOCK_CHANNEL, stockEvent());

        assert.equal(closing.sent.length, 0);
    });
});

describe("the heartbeat", () => {
    it("pings a live socket and marks it unanswered", () => {
        const alice = fakeSocket();
        register(7, alice);

        heartbeatTick(fakeApp);

        assert.equal(alice.pings, 1);
        // Set false on the way out; the pong handler in server.js sets it back.
        assert.equal(alice.isAlive, false);
        assert.equal(alice.terminated, false);
    });

    it("leaves a socket alone that answered the previous ping", () => {
        const alice = fakeSocket();
        register(7, alice);

        heartbeatTick(fakeApp);
        alice.isAlive = true; // what the pong handler does
        heartbeatTick(fakeApp);

        assert.equal(alice.pings, 2);
        assert.equal(alice.terminated, false);
    });

    it("terminates a socket that never answered", () => {
        const dead = fakeSocket();
        register(7, dead);

        heartbeatTick(fakeApp); // ping, isAlive -> false
        heartbeatTick(fakeApp); // no pong arrived in between

        assert.equal(dead.terminated, true);
        // Terminated rather than pinged again.
        assert.equal(dead.pings, 1);
    });
});



